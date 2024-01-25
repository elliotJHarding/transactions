from datetime import datetime, timedelta, timezone

from django.core.management import BaseCommand

from tx_app import models, nordigen, TransactionHelper

class Command(BaseCommand):
    help = "Fetch transactions job"

    def handle(self, *args, **options):

        username = 'hardings'
        user = models.User.objects.get(username=username)

        accounts = models.Account.objects.filter(user=user)

        transactions_collected = False

        for account in accounts:
            should_collect_transactions = account.last_collected_transactions is None or account.last_collected_transactions < datetime.now(
                tz=timezone.utc) - timedelta(hours=6)
            if should_collect_transactions:
                transactions_collected = True
                try:
                    transactions = nordigen.get_transactions(account.resource_id)
                    account.save_transactions(transactions['transactions']['booked'])
                    account.update_balance(nordigen.get_account_balance(account.resource_id))
                except ValueError as e:
                    print(e)

        if transactions_collected:
            TransactionHelper.find_links(user)
