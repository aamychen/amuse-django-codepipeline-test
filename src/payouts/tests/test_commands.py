from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from hyperwallet.models import Program
from django.core.management import call_command


class SetUnusablePassCommandTestCase(TestCase):
    @patch("hyperwallet.Api.getProgram")
    def test_hw_integration_smoke_command(self, mock):
        mock.return_value = Program(
            {
                "createdOn": "2021-06-28",
                "name": "Amuse - Direct - World",
                "parentToken": "prg-33569045-d0ad-42c7-88ae-222dbb2fb806",
                "token": "prg-19d7ef5e-e01e-43bc-b271-79eef1062832",
            }
        )
        call_command("hw_direct_integration_test")
