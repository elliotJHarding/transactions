from requests import get, post
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


def get_institutions(code: str):
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {Auth.get_access_token()}"
    }
    params = {
        "country": code
    }

    response = get(Endpoint.INSTITUTIONS, params=params, headers=headers)

    if response.status_code != 200:
        raise ConnectionError

    response_data = json.loads(response.text)

    return InstitutionList(response_data)


def get_end_user_agreement(institution: InstitutionData):
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {Auth.get_access_token()}"
    }
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


def get_requisition(agreement: EndUserAgreement, reference: int, institution: InstitutionData, redirect: str):
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {Auth.get_access_token()}"
    }
    data = {
        "agreement": agreement.id,
        "redirect": redirect,
        "institution_id": institution.id,
        "reference": reference,
    }

    response = post(Endpoint.REQUISITIONS, data=data, headers=headers)

    if response.status_code != 201:
        raise ConnectionError

    response_data = json.loads(response.text)

    link = Requisition(
        response_data["id"],
        response_data["redirect"],
        response_data["status"],
        response_data["agreements"],
        response_data["accounts"],
        response_data["reference"],
        response_data["link"]
    )

    return link


def get_transactions(account_id: str):
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {Auth.get_access_token()}"
    }

    response = get(Endpoint.TRANSACTIONS(account_id), headers=headers)

    response_data = json.loads(response.text)

    return response_data
