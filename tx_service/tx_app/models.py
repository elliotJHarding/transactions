from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Account(models.Model):
    resource_id = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Transaction(models.Model):
    transaction_id = models.CharField(max_length=200)
    internal_transaction_id = models.CharField(max_length=200)

    booking_date = models.DateField()
    value_date = models.DateField()
    booking_date_time = models.DateTimeField()
    value_date_time = models.DateTimeField()

    amount = models.FloatField()
    currency = models.CharField(max_length=10)

    creditorName = models.CharField(max_length=200)
    transactions_code = models.CharField(max_length=10)
    
    account = models.ForeignKey(Account, models.CASCADE)


