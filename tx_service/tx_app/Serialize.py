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


def holidays(holidays):
    holiday_data = []
    for holiday in holidays:
        year = holiday.start_date.year
        if year not in [hol['year'] for hol in holiday_data]:
            holiday_data.append({'year': year, 'holidays': []})

        holiday_data[[hol['year'] for hol in holiday_data].index(year)]['holidays'].append(holiday.serialize_with_financial_summary())


    return holiday_data

def tags(tags, sub_tags, rules, categories):
    data = {
        'tags': [],
        'categories': [category.serialize() for category in categories]
    }

    for tag in tags:
        tag_data = tag.serialize()

        tag_data['childTags'] = [sub_tag.serialize() for sub_tag in sub_tags if sub_tag.parent.id == tag.id]
        for childTag in tag_data['childTags']:
            childTag['rules'] = [rule.serialize() for rule in rules if rule.tag.id == childTag['id']]

        data['tags'].append(tag_data)
        tag_data['rules'] = [rule.serialize() for rule in rules if rule.tag.id == tag.id]

    return data


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


def rules(rules):
    return {"rules": [rule.serialize() for rule in rules]}
