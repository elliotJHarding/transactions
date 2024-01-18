import datetime
import logging

from requests import get, post, delete
from dotenv import dotenv_values, find_dotenv
import json
from dataclasses import dataclass

secrets = dotenv_values(find_dotenv())


class Token:
    def __init__(self, token: str, expires_in_seconds: int):
        self.token = token
        self.expires = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in_seconds)

    def is_valid(self):
        if datetime.datetime.now() > self.expires:
            return False
        else:
            return True

    def __repr__(self):
        return self.token

    def __str__(self):
        return self.token


class Endpoint:
    protocol, domain, api = "https", "ob.nordigen.com", "api/v2"
    url = f"{protocol}://{domain}/{api}"
    ACCESS_TOKEN =          f"{url}/token/new/"
    REFRESH_TOKEN =         f"{url}/token/refresh/"
    INSTITUTIONS =          f"{url}/institutions/"
    END_USER_AGREEMENT =    f"{url}/agreements/enduser/"
    REQUISITIONS =          f"{url}/requisitions/"
    ACCOUNTS =              f"{url}/accounts/"
    @classmethod
    def ACCOUNT_DETAILS(cls, account_id): return f"{cls.ACCOUNTS}{account_id}/details/"
    @classmethod
    def TRANSACTIONS(cls, account_id): return f"{cls.ACCOUNTS}{account_id}/transactions/"
    @classmethod
    def ACCOUNT_BALANCE(cls, account_id): return f"{cls.ACCOUNTS}{account_id}/balances/"


@dataclass
class InstitutionData:
    id: str
    name: str
    bic: str
    transaction_total_days: int
    countries: list
    logo: str

@dataclass
class EndUserAgreement:
    id: str
    created: str
    max_historical_days: int
    access_valid_for_days: int
    access_scope: list
    accepted: bool
    institution_id: str

@dataclass
class Requisition:
    id: str
    redirect: str
    status: dict
    agreements: str
    accounts: list
    reference: int
    link: str

@dataclass
class Account:
    resource_id: str
    iban: str
    bban: str
    currency: str
    owner_name: str
    name: str
    cash_account_type: str


class InstitutionList(list):
    def __init__(self, institutions: list):
        super(InstitutionList, self).__init__(self.create_institution(obj) for obj in institutions)

    @staticmethod
    def create_institution(obj):
        if type(obj) is dict:
            institution = InstitutionData(
            obj["id"],
            obj["name"],
            obj["bic"],
            int(obj["transaction_total_days"]),
            obj["countries"],
            obj["logo"]
            )
        elif type(obj) is InstitutionData:
            institution = obj

        return institution

    def get_by_name(self, name: str):
        institutions = InstitutionList(filter(lambda institution: name.lower() in institution.name.lower(), self))
        if len(institutions) == 0:
            raise LookupError
        elif len(institutions) > 1:
            raise OverflowError
        else:
            return institutions[0]


class Auth:
    _access_token: Token = None
    _refresh_token: Token = None

    @classmethod
    def get_access_token(cls):
        if cls._access_token is None:
            cls._access_token, cls._refresh_token = cls.request_tokens()
        elif not cls._access_token.is_valid():
            if cls._refresh_token.is_valid():
                cls._access_token = cls.refresh_access_token()
            else:
                cls._access_token, cls._refresh_token = cls.request_tokens()

        return cls._access_token

    @classmethod
    def refresh_access_token(cls):
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "refresh": cls._refresh_token.token
        }

        response = post(Endpoint.REFRESH_TOKEN, json=data, headers=headers)
        response_data = json.loads(response.text)

        return Token(response_data['access'], response_data['access_expires'])

    @classmethod
    def request_tokens(cls):
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        data = {
            "secret_id": secrets["NORDIGEN_ID"],
            "secret_key": secrets["NORDIGEN_KEY"]
        }
        response = post(Endpoint.ACCESS_TOKEN, json=data, headers=headers)

        if response.status_code != 200:
            raise ConnectionError

        response_data = json.loads(response.text)

        access_token = Token(response_data['access'], response_data['access_expires'])
        refresh_token = Token(response_data['refresh'], response_data['refresh_expires'])

        return access_token, refresh_token

    @classmethod
    def get_headers(cls):
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {cls.get_access_token()}"
        }
        return headers


def get_institutions(code: str):
    headers = Auth.get_headers()
    params = {
        "country": code
    }

    response = get(Endpoint.INSTITUTIONS, params=params, headers=headers)

    if response.status_code != 200:
        raise ConnectionError

    response_data = json.loads(response.text)

    return InstitutionList(response_data)


def get_end_user_agreement(institution: InstitutionData):
    headers = Auth.get_headers()
    data = {
        "institution_id": institution.id
    }

    response = post(Endpoint.END_USER_AGREEMENT, data=data, headers=headers)

    if response.status_code != 201:
        raise ConnectionError

    response_data = json.loads(response.text)

    end_user_agreement = EndUserAgreement(
        response_data["id"],
        response_data["created"],
        response_data["max_historical_days"],
        response_data["access_valid_for_days"],
        response_data["access_scope"],
        False if response_data["accepted"] == 'null' else True,
        response_data["institution_id"]
    )

    return end_user_agreement


def create_requisition(reference: int, institution_id: str, redirect: str, agreement: EndUserAgreement = None):
    headers = Auth.get_headers()
    data = {
        "redirect": redirect,
        "institution_id": institution_id,
        "reference": reference,
    }

    if agreement is not None:
        data["agreement"] = agreement.id

    response = post(Endpoint.REQUISITIONS, data=data, headers=headers)

    if response.status_code != 201:
        logging.log(logging.ERROR, response.text)
        print(response.text)
        raise ConnectionError

    response_data = json.loads(response.text)

    link = Requisition(
        response_data["id"],
        response_data["redirect"],
        response_data["status"],
        None,
        response_data["accounts"],
        response_data["reference"],
        response_data["link"]
    )

    if 'agreements' in response_data:
        link.agreements = response_data['agreements']

    return link


def get_requisition(id: str):
    headers = Auth.get_headers()

    response = get(Endpoint.REQUISITIONS + id, headers=headers)
    response_data = json.loads(response.text)

    requisition = Requisition(
        response_data["id"],
        response_data["redirect"],
        response_data["status"],
        None,
        response_data["accounts"],
        response_data["reference"],
        response_data["link"]
    )

    if 'agreements' in response_data:
        requisition.agreements = response_data['agreements']

    return requisition


def get_account(account_id: str):
    headers = Auth.get_headers()

    response = get(Endpoint.ACCOUNT_DETAILS(account_id), headers=headers)
    response_data = json.loads(response.text)
    response_data = response_data['account']

    account = Account(
        response_data["resourceId"],
        None,
        None,
        response_data["currency"],
        None,
        None,
        response_data["cashAccountType"]
    )
    if 'iban' in response_data:
        account.iban = response_data['iban']

    if 'bban' in response_data:
        account.bban = response_data['bban']

    if 'name' in response_data:
        account.name = response_data['name']
    elif 'details' in response_data:
        account.name = response_data['details']

    if 'ownerName' in response_data:
        account.owner_name = response_data['ownerName']

    return account


def get_account_balance(account_id):
    headers = Auth.get_headers()

    response = get(Endpoint.ACCOUNT_BALANCE(account_id), headers=headers)
    response_data = json.loads(response.text)
    balances = response_data['balances']
    balance_amount = balances[0]['balanceAmount']
    amount = balance_amount['amount']

    return amount


def get_transactions(account_id: str):
    headers = Auth.get_headers()

    response = get(Endpoint.TRANSACTIONS(account_id), headers=headers)

    response_data = json.loads(response.text)

    if response.status_code == 400 and 'expired' in response_data['summary']:
        raise ValueError(f"EUA has expired for account with id: {account_id}")

    return response_data


def delete_requisition(requisition_id):
    headers = Auth.get_headers()

    response = delete(Endpoint.REQUISITIONS + requisition_id, headers=headers)

    if str(response.status_code)[0] != '2':
        logging.log(logging.ERROR, response.text)
        return False
    else:
        return True
