import datetime

from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.views import Response
from rest_framework.exceptions import bad_request, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.authtoken.models import Token
import tx_app.nordigen as nordigen
import tx_app.TransactionHelper as TransactionHelper
from datetime import timedelta

import tx_app.Serialize as serialize
import tx_app.models as models
# import tx_service.tx_app.models as models

MIN_USERNAME_LENGTH = 5
MIN_PASSWORD_LENGTH = 5

def get_user_from_token(token):
    user_id = Token.objects.get(key__exact=token).user_id
    return User.objects.get(id=user_id)


# Create your views here.

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
        token = request.auth.key
        user=get_user_from_token(token)

        requisitions = models.Requisition.objects.filter(user=user, status__exact='ACTIVE')

        for requisition in requisitions:
            link = nordigen.get_requisition(requisition.external_id)
            for account_id in link.accounts:
                account_details = nordigen.get_account(account_id)
                account, created = models.Account.objects.get_or_create(
                    resource_id=account_id, user=user, name=account_details.owner_name, institution=requisition.institution)
                account.account_name = account_details.owner_name
                account.iban = account_details.iban
                account.bban = account_details.bban
                account.save()

        return Response(status=200)


class GetTransactions(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        token = request.auth.key

        user_id = Token.objects.get(key__exact=token).user_id
        user = models.User.objects.get(id=user_id)

        accounts = models.Account.objects.filter(user=user)

        transactions_collected = False

        for account in accounts:
            should_collect_transactions = account.last_collected_transactions is None or account.last_collected_transactions < datetime.datetime.now(tz=datetime.timezone.utc) - timedelta(hours=6)
            if should_collect_transactions:
                transactions_collected = True
                transactions = nordigen.get_transactions(account.resource_id)
                account.save_transactions(transactions['transactions']['booked'])

        if transactions_collected:
            TransactionHelper.find_links(user)

        institution_ids = [account.institution.id for account in accounts]
        institutions = [models.Institution.objects.get(id=id) for id in institution_ids]

        transactions = {account.id: models.Transaction.objects.filter(account=account) for account in accounts}

        links = models.TransactionLink.objects.filter(from_transaction__account__user=user)

        tags = list(models.Tag.objects.filter(user=None, parent=None)) + list(models.Tag.objects.filter(user=user, parent=None))
        sub_tags = []

        for tag in tags:
            sub_tags += list(models.Tag.objects.filter(parent=tag))

        return JsonResponse(data=serialize.transactions(accounts, transactions, institutions, links, tags, sub_tags))


class SetTransactionTag(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        token = request.auth.key
        user_id = Token.objects.get(key__exact=token).user_id
        user = models.User.objects.get(id=user_id)

        try:
            transactionId = request.data['transactionId']
            tagId = request.data['tagId']
        except KeyError as e:
            return Response(status=400, data={"error": str(e)})

        transaction = models.Transaction.objects.get(id=transactionId)
        tag = models.Tag.objects.get(id=tagId)

        if transaction.account.user != user or tag.user != user:
            return Response(status=403)

        transaction.tag = tag
        models.Transaction.save(transaction)

        return Response(status=200)


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
        user = get_user_from_token(request.auth.key)

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
