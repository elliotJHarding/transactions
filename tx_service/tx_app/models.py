import datetime

from django.db import models
from django.contrib.auth.models import User


class Institution(models.Model):
    name = models.CharField(max_length=200)
    logo_url = models.CharField(max_length=1000)
    code = models.CharField(max_length=200)

    def serialize(self):
        return {
            'name': self.name,
            'logo': self.logo_url,
            'code': self.code,
        }


class Requisition(models.Model):
    user = models.ForeignKey(User, models.CASCADE)
    institution = models.ForeignKey(Institution, models.CASCADE)
    external_id = models.CharField(max_length=200)
    status = models.CharField(max_length=50)
    expires = models.DateField(null=True)


class Account(models.Model):
    resource_id = models.CharField(max_length=200)
    name = models.CharField(max_length=200, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bban = models.BigIntegerField(null=True)
    iban = models.CharField(max_length=200, null=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    balance = models.FloatField(null=True)
    account_name = models.CharField(max_length=200, null=True)
    last_collected_transactions = models.DateTimeField(null=True)
    requisition = models.ForeignKey(Requisition, on_delete=models.SET_NULL, null=True)

    def get_bank_number(self):
        if self.iban is not None:
            return str(self.iban)
        elif self.bban is not None:
            return str(self.bban)
        else:
            return None

    def serialize(self):
        account_data = {
            'accountId': self.id,
            'name': self.name,
            'bankName': self.institution.name,
            'bankCode': self.institution.code,
            'logo': self.institution.logo_url,
            'expires': self.requisition.expires,
            'expired': self.has_requisition_expired()
        }
        return account_data

    def update_balance(self, amount):
        self.balance = amount
        self.save()

    def save_transactions(self, booked_transactions):
        transactions_to_commit = []
        for transaction in booked_transactions:
            keys = transaction.keys()
            transactionObject = Transaction()
            transactionObject.account = Account.objects.get(id__exact=self.id)
            transactionObject.internal_transaction_id = transaction['internalTransactionId']
            transactionObject.booking_date = transaction['bookingDate']
            transactionObject.value_date = transaction['valueDate'] if 'valueDate' in keys else None
            transactionObject.booking_date_time = transaction['bookingDateTime']
            transactionObject.value_date_time = transaction['valueDateTime'] if 'valueDateTime' in keys else None

            transactionObject.amount = transaction['transactionAmount']['amount']
            transactionObject.currency = transaction['transactionAmount']['currency']
            transactionObject.reference = transaction['remittanceInformationUnstructured']

            if "transactionId" in transaction.keys():
                transactionObject.transaction_id = transaction['transactionId']

            if "creditorName" in transaction.keys():
                transactionObject.creditorName = transaction["creditorName"]
            if "creditorAccount" in transaction.keys():
                transactionObject.creditorAccount = transaction["creditorAccount"]["bban"]

            if "debtorName" in transaction.keys():
                transactionObject.debtorName = transaction["debtorName"]
                transactionObject.debtorAccount = transaction["debtorAccount"]["bban"]

            if float(transactionObject.amount) < 0 and 'proprietaryBankTransactionCode' in transaction.keys():
                transactionObject.transactions_code = transaction['proprietaryBankTransactionCode']

            transactions_to_commit.append(transactionObject)
        for transaction in transactions_to_commit:
            try:
                transaction.save()
            except Exception as exception:
                print("Transaction skipped: " + str(exception))

        self.last_collected_transactions = datetime.datetime.now()
        self.save()

    def has_requisition_expired(self):
        today = datetime.date.today()
        return self.requisition.expires <= today



class Category(models.Model):
    code = models.CharField(max_length=200)
    name = models.CharField(max_length=200)

    def serialize(self):
        return {
            "code": self.code,
            "name": self.name
        }

class Tag(models.Model):
    name = models.CharField(max_length=99)
    user = models.ForeignKey(User, models.CASCADE, null=True)
    icon = models.CharField(max_length=199, null=True)
    parent = models.ForeignKey('self', models.CASCADE, null=True, unique=False)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)

    def serialize(self):
        data = {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
        }

        if self.category is not None:
            data["category"] = self.category.serialize()

        return data


class Holiday(models.Model):
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    img_url = models.CharField(max_length=1000, null=True)

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "img": self.img_url
        }

    def serialize_with_financial_summary(self):
        holiday_data = self.serialize()
        holiday_transactions = Transaction.objects.filter(account__user=self.user, holiday=self)
        holiday_data['total'] = round(sum([t.amount for t in holiday_transactions]), 2)
        holiday_data['travel'] = round(sum([t.amount for t in holiday_transactions if t.tag is not None and t.tag.parent is not None and t.tag.parent.name == 'Travel' and t.tag.name != 'Hotels']), 2)
        holiday_data['hotels'] = round(sum([t.amount for t in holiday_transactions if t.tag is not None and t.tag.name == 'Hotels']), 2)
        holiday_data['food'] = round(sum([t.amount for t in holiday_transactions if t.tag is not None and t.tag.name == 'Eating Out']), 2)

        return holiday_data


class Transaction(models.Model):
    transaction_id = models.CharField(max_length=200, null=True)
    internal_transaction_id = models.CharField(max_length=200, unique=True)

    booking_date = models.DateField()
    value_date = models.DateField(null=True)
    booking_date_time = models.DateTimeField()
    value_date_time = models.DateTimeField(null=True)

    amount = models.FloatField()
    currency = models.CharField(max_length=10)
    reference = models.CharField(max_length=200)

    creditorName = models.CharField(max_length=200)
    creditorAccount = models.CharField(max_length=200, null=True)
    transactions_code = models.CharField(max_length=200)

    debtorName = models.CharField(max_length=200, null=True)
    debtorAccount = models.CharField(max_length=200, null=True)
    
    account = models.ForeignKey(Account, models.CASCADE)

    tag = models.ForeignKey(Tag, models.CASCADE, null=True)

    holiday = models.ForeignKey(Holiday, models.DO_NOTHING, null=True)

    def serialize(self):
        return {
            "transactionId": self.id,
            "bookingDate": self.booking_date,
            "bookingDateTime": self.booking_date_time,
            "tag": self.tag.serialize() if self.tag is not None else None,
            "holiday": self.holiday.serialize() if self.holiday is not None else None,
            "value": {
                "amount": self.amount,
                "currency": self.currency
            },
            "reference": self.reference,
            "transactions_code": self.transactions_code
        }

    # def find_active_requisition(self, )

    @staticmethod
    def getByUser(user):
        return [transaction
                for account in Account.objects.filter(user=user)
                for transaction in Transaction.objects.filter(account=account)]


class TransactionLink(models.Model):
    from_transaction = models.OneToOneField(Transaction, related_name="from_transaction", on_delete=models.CASCADE)
    to_transaction = models.OneToOneField(Transaction, related_name="to_transaction", on_delete=models.CASCADE)

    def serialize(self):
        from_transaction = self.from_transaction
        to_transaction = self.to_transaction
        return {
            "fromTransactionId": from_transaction.id,
            "toTransactionId": to_transaction.id,
            "fromAccountId": from_transaction.account.id,
            "toAccountId": to_transaction.account.id,
            "amount": to_transaction.amount,
            "bookingDate": to_transaction.booking_date,
            "bookingDateTime": to_transaction.booking_date_time,
            "reference": to_transaction.reference
        }


class TagRule(models.Model):
    user = models.ForeignKey(User, models.CASCADE)
    tag = models.ForeignKey(Tag, models.CASCADE)
    expression = models.CharField(max_length=200)

    def serialize(self):
        return {
            "id": self.id,
            "expression": self.expression
        }
