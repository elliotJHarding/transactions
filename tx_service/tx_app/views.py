import datetime
import logging

from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.views import Response
from rest_framework.exceptions import bad_request, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
import tx_app.nordigen as nordigen
import tx_app.TransactionHelper as TransactionHelper
from datetime import timedelta

import tx_app.Serialize as serialize
import tx_app.models as models

MIN_USERNAME_LENGTH = 5
MIN_PASSWORD_LENGTH = 5

# Create your views here.


def validate_ownership(resource, requesting_user):
    if resource.user is not None and resource.user != requesting_user:
        error = f"Resource {resource} does not belong to user"
        logging.log(logging.ERROR, error)
        return False, Response(status=403, data={'error': error})
    else:
        return True, None


class CreateUser(APIView):
    def post(self, request):

        try:
            username = request.data['username']
            password = request.data['password']
        except KeyError:
            return bad_request()

        if len(username) < MIN_USERNAME_LENGTH:
            raise ValidationError("username too short")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError("password too short")

        User.objects.create_user(username, None, password)

        return Response(status=201)


class GetProfile(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        token = request.auth.key

        user_id = Token.objects.get(key__exact=token).user_id
        user = User.objects.get(id=user_id)

        linked_accounts = models.Account.objects.filter(user_id=user_id)

        institution_ids = [account.institution.id for account in linked_accounts]
        institutions = [models.Institution.objects.get(id=id) for id in institution_ids]

        json_response = {
            'user': serialize.user(user),
            'accounts': serialize.accounts(linked_accounts)
        }

        return JsonResponse(json_response)


class UpdateAccounts(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):

        user = request.user

        requisitions = models.Requisition.objects.filter(user=user, status__exact='ACTIVE')

        for requisition in requisitions:
            if requisition.expires > datetime.date.today():
                link = nordigen.get_requisition(requisition.external_id)
                for account_id in link.accounts:
                    account_details = nordigen.get_account(account_id)
                    account, created = models.Account.objects.get_or_create(
                        resource_id=account_id, user=user, institution=requisition.institution)

                    if account.name is None:
                        account.name = requisition.institution.name
                    account.account_name = account_details.owner_name
                    account.iban = account_details.iban
                    account.bban = account_details.bban
                    account.requisition = requisition
                    account.save()
            else:
                requisition.status = 'EXPIRED'
                requisition.save()

        return Response(status=200)


class Transactions(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user

        accounts = models.Account.objects.filter(user=user)

        institution_ids = [account.institution.id for account in accounts]
        institutions = [models.Institution.objects.get(id=id) for id in institution_ids]

        transactions = {account.id: models.Transaction.objects.filter(account=account) for account in accounts}

        links = models.TransactionLink.objects.filter(from_transaction__account__user=user)

        tags = list(models.Tag.objects.filter(user=None, parent=None)) + list(
            models.Tag.objects.filter(user=user, parent=None))
        sub_tags = []

        for tag in tags:
            sub_tags += list(models.Tag.objects.filter(parent=tag))

        rules = models.TagRule.objects.filter(user=user)
        for rule in rules:
            for account in transactions:
                for transaction in transactions[account]:
                    if rule.expression.lower() in transaction.reference.lower():
                        if transaction.tag is None:
                            transaction.tag = rule.tag
                            transaction.save()

        return JsonResponse(data=serialize.transactions(accounts, transactions, institutions, links, tags, sub_tags))

    def post(self, request):

        user = request.user

        try:
            transaction_updates = request.data['transactionUpdates']
        except KeyError as e:
            return Response(status=400, data={"error": str(e)})

        for transaction_update in transaction_updates:
            try:
                transaction_id = transaction_update['transactionId']
            except KeyError as e:
                return Response(status=400, data={"error": str(e)})

            transaction = models.Transaction.objects.get(id=transaction_id)

            if 'tagId' in transaction_update:
                tag_id = transaction_update['tagId']
                tag = models.Tag.objects.get(id=tag_id) if tag_id is not None else None

                valid, response = validate_ownership(tag, user)
                if not valid:
                    return response

                transaction.tag = tag

            if 'holidayId' in transaction_update:
                holiday_id = transaction_update['holidayId']
                holiday = models.Holiday.objects.get(id=holiday_id) if holiday_id is not None else None

                valid, response = validate_ownership(holiday, user)
                if not valid:
                    return response

                transaction.holiday = holiday

            models.Transaction.save(transaction)

        return Response(status=200)

def construct_empty_report(categories, tags, sub_tags):
    report = {
        "untagged": 0
    }

    for category in categories:
        report[category.code] = {}
        report[category.code]["total"] = 0
        report[category.code]["categories"] = {}

    for tag in tags:
        if tag.category is not None:
            report[tag.category.code]["categories"][tag.name] = {"tag": tag.serialize(), "total": 0, "categories": {}}

    for sub_tag in sub_tags:
        parent = sub_tag.parent
        if parent.category is not None:
            report[parent.category.code]["categories"][parent.name]["categories"][sub_tag.name] = {"tag": sub_tag.serialize(), "total": 0}

    return report


class Reports(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        reports = {}

        user = request.user

        transactions = models.Transaction.getByUser(user)

        tags = list(models.Tag.objects.filter(user=None, parent=None)) + list(
            models.Tag.objects.filter(user=user, parent=None))
        sub_tags = []

        for tag in tags:
            sub_tags += list(models.Tag.objects.filter(parent=tag))

        categories = models.Category.objects.all()

        def add_transaction_to_report(report, transaction):
            if transaction.tag.category is None and transaction.tag.parent is not None:
                report[transaction.tag.parent.category.code]["categories"][transaction.tag.parent.name]["categories"][transaction.tag.name]["total"] += transaction.amount
                report[transaction.tag.parent.category.code]["categories"][transaction.tag.parent.name]["total"] += transaction.amount
                report[transaction.tag.parent.category.code]["total"] += transaction.amount
            elif transaction.tag.category is not None:
                report[transaction.tag.category.code]["categories"][transaction.tag.name][
                    "total"] += transaction.amount
                report[transaction.tag.category.code]["total"] += transaction.amount

        for transaction in transactions:
            date: datetime = transaction.booking_date
            month = date.strftime('%B')
            if date.year not in reports.keys():
                reports[date.year] = construct_empty_report(categories, tags, sub_tags)
            if month not in reports[date.year].keys():
                reports[date.year][month] = construct_empty_report(categories, tags, sub_tags)
            if transaction.tag is None or transaction.holiday is not None:
                if transaction.holiday is None and transaction.is_unlinked():
                    reports[date.year][month]["untagged"] += 1
                if transaction.account.type.code == "SAVINGS":
                    reports[date.year][month]['SAVINGS']['total'] += transaction.amount
                    reports[date.year]['SAVINGS']['total'] += transaction.amount
            else:
                add_transaction_to_report(reports[date.year][month], transaction)
                add_transaction_to_report(reports[date.year], transaction)

        return JsonResponse(status=200, data=reports)


class Tags(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):

        user = request.user

        tags = list(models.Tag.objects.filter(user=None, parent=None)) + list(
            models.Tag.objects.filter(user=user, parent=None))
        sub_tags = []

        for tag in tags:
            sub_tags += list(models.Tag.objects.filter(parent=tag))

        rules = models.TagRule.objects.filter(user=user)

        categories = models.Category.objects.all()

        return JsonResponse(data=serialize.tags(tags, sub_tags, rules, categories))

    def put(self, request):
        user = request.user

        data = request.data

        try:
            parent_tag_id = data['parentTag'] if 'parentTag' in data else None
            name = data['name']
            icon = data['icon']
        except KeyError as error:
            return JsonResponse(status=500, data={'error': str(error)})

        tag = models.Tag()
        tag.user = user
        tag.name = name
        tag.icon = icon
        if parent_tag_id != None:
            parentTag = models.Tag.objects.get(id=parent_tag_id)
            tag.parent = parentTag

        tag.save()

        return Response(status=201)

    def patch(self, request):
        user = request.user

        try:
            tag_id = request.data['tagId']
        except KeyError as error:
            return JsonResponse(status=500, data={'error': str(error)})

        tag = models.Tag.objects.get(id=tag_id)

        if tag.user is not None and tag.user != user:
            return JsonResponse(status=403, data={'error': 'You are not authorized to edit this tag'})

        if 'name' in request.data:
            name = request.data['name']
            tag.name = name

        if 'icon' in request.data:
            icon = request.data['icon']
            tag.icon = icon

        if 'categoryCode' in request.data:
            categoryCode = request.data['categoryCode']
            tag.category = models.Category.objects.get(code=categoryCode)

        tag.save()

        return Response(status=201)


class UpdateTransaction(APIView):
    permission_classes = (IsAuthenticated,)




class GetInstitutions(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        institutions = models.Institution.objects.all()

        institution_data = {
            'institutions': [ins.serialize() for ins in institutions]
        }

        return JsonResponse(data=institution_data)


class Requisition(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        user = request.user

        try:
            institution_id = request.data['bankCode']

            requisition = models.Requisition()
            requisition.user = user
            requisition.institution = models.Institution.objects.get(code=institution_id)
            requisition.status = 'SENT'
            models.Requisition.save(requisition)

            try:
                link = nordigen.create_requisition(requisition.id, institution_id, 'http://localhost:3000/user')
            except ConnectionError:
                return Response(status=500)

            requisition.external_id = link.id
            requisition.status = link.status

            models.Requisition.save(requisition)

            external_url = link.link

            data = {'link': external_url}
            return JsonResponse(data=data)
        except KeyError as e:
            return Response(status=500, data={'error': str(e)})

    def delete(self, request):

        requisition_id = request.data['clientRef']
        requisition = models.Requisition.objects.get(id=requisition_id)

        success = nordigen.delete_requisition(requisition.external_id)

        if success:
            requisition.delete()
            return Response(status=200)
        else:
            return Response(status=500)

    def patch(self, request):
        requisition_id = request.data['clientRef']
        requisition = models.Requisition.objects.get(id=requisition_id)

        status = request.data['status']

        if status == 'ACTIVE':
            requisition.expires = datetime.date.today() + datetime.timedelta(days=89)

        requisition.status = status
        requisition.save()

        return Response(status=200)


class UploadTransactions(APIView):

    def post(self, request):
        data = request.data
        account_id = data['account_id']
        account = models.Account.objects.get(id=account_id)
        request_transactions = data['transactions']
        booked_transactions = request_transactions['booked']

        account.save_transactions(booked_transactions)

        return Response(status=200)


class UploadTags(APIView):
    def post(self, request):
        data = request.data
        try:
            tags = data['tags']

            for tag in tags:
                tag_object, created = models.Tag.objects.get_or_create(name=tag['name'])
                tag_object.name = tag['name']
                tag_object.icon = tag['icon']
                tag_object.user = None
                models.Tag.save(tag_object)

                for child in tag['childTags']:
                    sub_tag, created = models.Tag.objects.get_or_create(name=child['name'])
                    sub_tag.name = child['name']
                    sub_tag.icon = child['icon']
                    sub_tag.parent = tag_object
                    sub_tag.user = None
                    models.Tag.save(sub_tag)

        except KeyError:
            return Response(status=400)

        return Response(status=200)


class UpdateInstitutions(APIView):
    def get(self, request):
        institutions = nordigen.get_institutions('gb')

        for institutionData in institutions:
            institution, created = models.Institution.objects.get_or_create(code=institutionData.id)
            institution.name = institutionData.name
            institution.logo_url = institutionData.logo
            institution.code = institutionData.id
            institution.save()

        return Response(status=200)


class FindLinks(APIView):
    def get(self, request):
        TransactionHelper.find_links(User.objects.get(id=9))

        return Response(status=200)


class TagRules(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user

        rules = models.TagRule.filter(user=user)

        return JsonResponse(status=200, data=serialize.rules(rules))

    def put(self, request):
        user = request.user

        data = request.data

        try:
            tag_id = data['tagId']
            expression = data['expression']
        except KeyError as e:
            return JsonResponse(status=400, data={"error": str(e)})

        rule = models.TagRule()
        rule.user = user
        rule.tag = models.Tag.objects.get(id=tag_id)
        rule.expression = expression

        rule.save()

        return Response(status=201)

    def delete(self, request):
        user = request.user

        data = request.data

        try:
            ruleId = data['ruleId']
        except KeyError as e:
            return JsonResponse(status=400, data={"error": str(e)})

        rule = models.TagRule.objects.get(id=ruleId)

        if rule.user.id != user.id:
            return JsonResponse(status=403, data={"error": "Unauthorised to edit this rule"})

        models.TagRule.delete(rule)

        return Response(status=200)

class Holidays(APIView):
    def get(self, request):
        user = request.user

        holidays = models.Holiday.objects.filter(user=user)

        return JsonResponse(data={'holidays': serialize.holidays(holidays)})



