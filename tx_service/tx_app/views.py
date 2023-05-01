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

import tx_app.Serialize as serialize
import tx_app.models as models
# import tx_service.tx_app.models as models

MIN_USERNAME_LENGTH = 5
MIN_PASSWORD_LENGTH = 5


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

        json_response = serialize.user(user)

        return JsonResponse(json_response)


class GetTransactions(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        token = request.auth.key

        user_id = Token.objects.get(key__exact=token).user_id
        user = models.User.objects.get(id=user_id)

        accounts = models.Account.objects.filter(user=user)
        institution_ids = [account.institution.id for account in accounts]
        institutions = [models.Institution.objects.get(id=id) for id in institution_ids]

        transactions = {account.id: models.Transaction.objects.filter(account=account) for account in accounts}

        links = models.TransactionLink.objects.filter(from_transaction__account__user=user)

        return JsonResponse(data=serialize.transactions(accounts, transactions, institutions, links))


class UploadTransactions(APIView):

    def post(self, request):
        data = request.data
        account_id = data['account_id']
        request_transactions = data['transactions']
        booked_transactions = request_transactions['booked']

        transactions_to_commit = []
        try:
            for transaction in booked_transactions:
                keys = transaction.keys()
                transactionObject = models.Transaction()
                transactionObject.account = models.Account.objects.get(id__exact=account_id)
                transactionObject.transaction_id = transaction['transactionId']
                transactionObject.internal_transaction_id = transaction['internalTransactionId']
                transactionObject.booking_date = transaction['bookingDate']
                transactionObject.value_date = transaction['valueDate'] if 'valueDate' in keys else None
                transactionObject.booking_date_time = transaction['bookingDateTime']
                transactionObject.value_date_time = transaction['valueDateTime'] if 'valueDateTime' in keys else None

                transactionObject.amount = transaction['transactionAmount']['amount']
                transactionObject.currency = transaction['transactionAmount']['currency']
                transactionObject.reference = transaction['remittanceInformationUnstructured']

                if "creditorName" in transaction.keys():
                    transactionObject.creditorName = transaction["creditorName"]
                if "creditorAccount" in transaction.keys():
                    transactionObject.creditorAccount = transaction["creditorAccount"]["bban"]

                if "debtorName" in transaction.keys():
                    transactionObject.debtorName = transaction["debtorName"]
                    transactionObject.debtorAccount = transaction["debtorAccount"]["bban"]

                if float(transactionObject.amount) < 0:
                    transactionObject.transactions_code = transaction['proprietaryBankTransactionCode']

                transactions_to_commit.append(transactionObject)

        except KeyError as e:
            return JsonResponse(status=400, data={'error': f"{e} not in transaction with id: {transaction['transactionId']}"})

        for transaction in transactions_to_commit:
            try:
                transaction.save()
            except Exception as exception:
                print("Transaction skipped: " + str(exception))

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
        TransactionHelper.find_links(User.objects.get(id=8))

        return Response(status=200)
