from django.db import models
from django.contrib.auth.models import User


class Institution(models.Model):
    name = models.CharField(max_length=200)
    logo_url = models.CharField(max_length=1000)
    code = models.CharField(max_length=200)


# Create your models here.
class Account(models.Model):
    resource_id = models.CharField(max_length=200)
    name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bban = models.BigIntegerField(null=True)
    iban = models.BigIntegerField(null=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    balance = models.FloatField(null=True)
    account_name = models.CharField(max_length=200, null=True)

    def get_bank_number(self):
        if self.iban is not None:
            return str(self.iban)
        elif self.bban is not None:
            return str(self.bban)
        else:
            return None


class Transaction(models.Model):
    transaction_id = models.CharField(max_length=200, unique=True)
    internal_transaction_id = models.CharField(max_length=200)

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


class TransactionLink(models.Model):
    from_transaction = models.OneToOneField(Transaction, related_name="from_transaction", on_delete=models.CASCADE)
    to_transaction = models.OneToOneField(Transaction, related_name="to_transaction", on_delete=models.CASCADE)


