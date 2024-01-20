import django.db.utils

from tx_app.models import *


def find_links(user):
    accounts = Account.objects.filter(user=user)

    institutions = [account.institution for account in accounts]

    for account in accounts:
        transactions = Transaction.objects.filter(account=account)
        for transaction in transactions:
            linked, link = find_link(accounts, transaction, institutions)
            if linked:
                print(link)


def find_link(accounts, transaction_a, institutions):

    NO_LINK_CREATED = False, None

    if has_possible_link(transaction_a, institutions):
        transaction_ban = transaction_a.debtorAccount if transaction_a.debtorAccount is not None else transaction_a.creditorAccount

        if transaction_ban in [account.get_bank_number() for account in accounts]:
            try:
                account = next(filter(lambda account: account.get_bank_number() == transaction_ban, accounts))
            except StopIteration:
                return NO_LINK_CREATED
            transactions = Transaction.objects.filter(account=account, booking_date=transaction_a.booking_date)
            transactions = filter(lambda account_transaction: abs(transaction_a.amount) == abs(account_transaction.amount), transactions)
            transactions = list(filter(lambda to_transaction: has_link(to_transaction, transaction_a), transactions))

            if len(transactions) != 1:
                return NO_LINK_CREATED

            transaction_b = transactions[0]

            if transaction_a.id == transaction_b.id:
                return NO_LINK_CREATED

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

    return False, None


def has_possible_link(transaction, institutions, from_account=None):

    if transaction.reference.lower() in [institution.name.lower() for institution in institutions]:
        return True

    if transaction.debtorAccount is not None or transaction.creditorAccount is not None:
        return True
    elif from_account is not None:
        user_fullname = from_account.account_name.lower()
        user_shortname = user_fullname.split(' ')[-1]
        reference = transaction.reference.lower()

        if user_fullname in reference or user_shortname in reference:
            return True
        else:
            return False
    else:
        return False

def has_link(transaction_a, transaction_b):
    linked = True

    linked = False if transaction_a.booking_date != transaction_b.booking_date else linked
    linked = False if transaction_a.amount + transaction_b.amount != 0 else linked

    return linked
