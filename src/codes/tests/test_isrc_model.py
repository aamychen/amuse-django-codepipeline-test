from django.test import TestCase
from codes.tests.factories import ISRCFactory
from codes.models import ISRC


class ISRCTestCase(TestCase):
    def setUp(self):
        self.used_isrc = ISRCFactory()
        self.unused_isrc = ISRCFactory(status=ISRC.STATUS_UNUSED)

    def test_count_created_isrc(self):
        """Test that both ISRC were created."""
        self.assertEqual(ISRC.objects.count(), 2)

    def test_create_isrc_with_status_unused_as_default(self):
        """Test ISRC is created with STATUS_UNUSED as default status"""
        self.assertTrue(isinstance(self.used_isrc, ISRC))
        self.assertEqual(self.used_isrc.status, ISRC.STATUS_USED)

    def test_first_unused_method(self):
        """
        Test that first_unused method picks up the first ISRC with status
        unused.
        """
        first_unused_isrc = ISRC.objects.first_unused()
        self.assertEqual(first_unused_isrc.status, ISRC.STATUS_UNUSED)
        # The first unused ISRC should be the one that we created it the setUp.
        self.assertEqual(self.unused_isrc, first_unused_isrc)

    def test_use_method_with_none_as_an_argument(self):
        """
        Test that the use method picks up the first unused ISRC and returns
        it after updating its status to used.
        """
        self.assertEqual(self.unused_isrc.status, ISRC.STATUS_UNUSED)
        updated_isrc = ISRC.objects.use(None)
        # The first unused ISRC should be the one that we created it the setUp.
        self.assertEqual(self.unused_isrc.id, updated_isrc.id)
        self.assertEqual(updated_isrc.status, ISRC.STATUS_USED)

    def test_use_method_with_isrc_code_as_argument(self):
        """
        Test that use method creates a new ISRC with same code provided as
        an argument and with a status used.
        """
        isrc_code = 'new_isrc'
        # No ISRC with same code should exist from the start
        self.assertEqual(ISRC.objects.filter(code=isrc_code).count(), 0)
        new_isrc = ISRC.objects.use(isrc_code)
        # Only one ISRC with the provided code should exist.
        self.assertEqual(ISRC.objects.filter(code=isrc_code).count(), 1)
        # Now we should have 3 ISRC in total.
        self.assertEqual(ISRC.objects.count(), 3)
        # The newly created ISRC should have used as status.
        self.assertEqual(new_isrc.status, ISRC.STATUS_USED)
