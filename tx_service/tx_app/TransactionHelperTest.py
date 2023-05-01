from django.test import TestCase
from tx_app import TransactionHelper
from tx_app.models import User


class TransactionHelperTestCase(TestCase):

    def test_find_linked_transactions(self):
        user = User.objects.all()
        TransactionHelper.find_links(User.objects.all())
