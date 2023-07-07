import json


def user(user):
    return {
        "userId": user.id,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "email": user.email
    }


def accounts(accounts):
    account_data = []
    for account in accounts:
        account_data.append(account.serialize())

    return account_data


def transactions(accounts, transactions, institutions, links, tags, sub_tags):
    data = {
        'accounts': [],
        'links': [],
        'tags': [],
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
        for transaction in transactions[account.id]:
            account_data['transactions'].append(transaction.serialize())

        data['accounts'].append(account_data)

    for link in links:
        data['links'].append(link.serialize())

    for tag in tags:
        tag_data = tag.serialize()
        tag_data['childTags'] = [sub_tag.serialize() for sub_tag in sub_tags if sub_tag.parent.id == tag.id]
        data['tags'].append(tag_data)

    return data
