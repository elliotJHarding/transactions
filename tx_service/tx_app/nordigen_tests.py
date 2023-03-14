from django.test import TestCase
from tx_app import nordigen
from dotenv import dotenv_values, find_dotenv

secrets = dotenv_values(find_dotenv())
access_token = None

class NordigenTestCase(TestCase):

    def test_get_institutions(self):
        code = "gb"
        institutions: nordigen.InstitutionList = nordigen.get_institutions(code)
        self.assertIsNotNone(institutions)
        self.assertTrue(len(institutions) > 0)

    def test_get_access_token(self):
        access_token = nordigen.Auth.get_access_token()
        self.assertIsNotNone(access_token)
        self.assertTrue(len(access_token) > 0)

    def test_get_end_user_agreement(self):
        code = "gb"
        institutions: nordigen.InstitutionList = nordigen.get_institutions(code)
        monzo = institutions.get_by_name('monzo')
        user_agreement = nordigen.get_end_user_agreement(monzo)

        self.assertIsNotNone(user_agreement)
        self.assertEqual(user_agreement.institution_id, monzo.id)

    def test_get_link(self):
        code = "gb"
        institutions: nordigen.InstitutionList = nordigen.get_institutions(code)
        monzo = institutions.get_by_name('monzo')
        user_agreement = nordigen.get_end_user_agreement(monzo)

        link = nordigen.get_requisition(user_agreement, 123, monzo, "http://localhost:8000/redirect")

        self.assertIsNotNone(link)

