import logging

from requests import get, post, delete
from dotenv import dotenv_values, find_dotenv
import json
from dataclasses import dataclass

secrets = dotenv_values(find_dotenv())
access_token = None


class Endpoint:
    ACCESS_TOKEN = "https://ob.nordigen.com/api/v2/token/new/"
    INSTITUTIONS = "https://ob.nordigen.com/api/v2/institutions/"
    END_USER_AGREEMENT = "https://ob.nordigen.com/api/v2/agreements/enduser/"
    REQUISITIONS = "https://ob.nordigen.com/api/v2/requisitions/"
    ACCOUNTS = "https://ob.nordigen.com/api/v2/accounts/"
    @classmethod
    def ACCOUNT_DETAILS(cls, account_id): return f"{cls.ACCOUNTS}{account_id}/details"
    @staticmethod
    def TRANSACTIONS(account_id): return f"https://ob.nordigen.com/api/v2/accounts/{account_id}/transactions/"


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
    _access_token: str = None

    @classmethod
    def get_access_token(cls):
        if cls._access_token is None:
            cls._access_token = cls.request_access_token()
        return cls._access_token

    @classmethod
    def request_access_token(cls):
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

        if "access" not in response_data:
            raise LookupError

        return response_data['access']

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
        response_data["bban"],
        response_data["currency"],
        response_data["ownerName"],
        None,
        response_data["cashAccountType"]
    )
    if 'iban' in response_data:
        account.iban = response_data['iban']

    if 'name' in response_data:
        account.name = response_data['name']

    return account


def get_transactions(account_id: str):
    headers = Auth.get_headers()

    response = get(Endpoint.TRANSACTIONS(account_id), headers=headers)

    response_data = json.loads(response.text)

    return response_data


def delete_requisition(requisition_id):
    headers = Auth.get_headers()

    response = delete(Endpoint.REQUISITIONS + requisition_id, headers=headers)

    if str(response.status_code)[0] != '2':
        logging.log(logging.ERROR, response.text)
        return False
    else:
        return True
