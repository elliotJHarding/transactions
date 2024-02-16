import django.db.utils

from tx_app.models import *


def find_links(user):
    transactions = Transaction.objects.filter(account__user=user)

    for transaction in transactions:
        linked, link = find_link(transaction, transactions)
        if linked:
            print(f"Found Link: {link.from_transaction.reference} : {link.from_transaction.amount} -> {link.to_transaction.reference} : {link.to_transaction.amount}")


def find_link(transaction_a, transactions):
    NO_LINK_CREATED = False, None

    transactions = transactions.exclude(account=transaction_a.account).filter(booking_date=transaction_a.booking_date)

    for transaction_b in transactions:
        if has_link(transaction_a, transaction_b):
            from_transaction = transaction_a if transaction_a.amount < 0 < transaction_b.amount else transaction_b
            to_transaction = transaction_a if transaction_a.amount > 0 > transaction_b.amount else transaction_b

            link = TransactionLink()
            link.from_transaction = from_transaction
            link.to_transaction = to_transaction

            try:
                link.save()
            except django.db.utils.IntegrityError:
                return NO_LINK_CREATED

            return True, link

    return NO_LINK_CREATED


def has_link(transaction_a, transaction_b):
    if not (transaction_a.is_unlinked() and transaction_b.is_unlinked()):
        return False

    if transaction_a.amount + transaction_b.amount == 0:
        return True

    return False
