import json


def user(user):
    return {
        "userId": user.id,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "email": user.email
    }


def transaction(transaction):
    return {
        "transactionId": transaction.id,
        "bookingDate": transaction.booking_date,
        "bookingDateTime": transaction.booking_date_time,
        "value": {
            "amount": transaction.amount,
            "currency": transaction.currency
        },
        "reference": transaction.reference,
        "transactions_code": transaction.transactions_code
    }


def transaction_link(transaction_link):
    from_transaction = transaction_link.from_transaction
    to_transaction = transaction_link.to_transaction
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


def transactions(accounts, transactions, institutions, links):
    data = {
        'accounts': [],
        'links': [],
    }
    for account in accounts:
        institution = next((ins for ins in institutions if ins.id == account.institution.id), None)
        account_data = {
            'accountId': account.id,
            'name': account.name,
            'bankName': institution.name,
            'logo': institution.logo_url,
            'balance': account.balance,
            'transactions': []
        }
        for t in transactions[account.id]:
            account_data['transactions'].append(transaction(t))

        data['accounts'].append(account_data)

    for link in links:
        data['links'].append(transaction_link(link))

    return data
