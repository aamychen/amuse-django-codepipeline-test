from django.test import TestCase
from codes.tests.factories import UPCFactory
from codes.models import UPC


class UPCTestCase(TestCase):
    def setUp(self):
        self.used_upc = UPCFactory()
        self.unused_upc = UPCFactory(status=UPC.STATUS_UNUSED)

    def test_count_created_upc(self):
        """Test that both UPC were created."""
        self.assertEqual(UPC.objects.count(), 2)

    def test_create_upc_with_status_unused_as_default(self):
        """Test UPC is created with STATUS_UNUSED as default status"""
        self.assertTrue(isinstance(self.used_upc, UPC))
        self.assertEqual(self.used_upc.status, UPC.STATUS_USED)

    def test_first_unused_method(self):
        """
        Test that first_unused method picks up the first UPC with status
        unused.
        """
        first_unused_upc = UPC.objects.first_unused()
        self.assertEqual(first_unused_upc.status, UPC.STATUS_UNUSED)
        # The first unused UPC should be the one that we created it the setUp.
        self.assertEqual(self.unused_upc, first_unused_upc)

    def test_use_method_with_none_as_an_argument(self):
        """
        Test that the use method picks up the first unused UPC and returns
        it after updating its status to used.
        """
        self.assertEqual(self.unused_upc.status, UPC.STATUS_UNUSED)
        updated_upc = UPC.objects.use(None)
        # The first unused UPC should be the one that we created it the setUp.
        self.assertEqual(self.unused_upc.id, updated_upc.id)
        self.assertEqual(updated_upc.status, UPC.STATUS_USED)

    def test_use_method_with_upc_code_as_argument(self):
        """
        Test that use method creates a new UPC with same code provided as
        an argument and with a status used.
        """
        upc_code = 'new_upc'
        # No UPC with same code should exist from the start
        self.assertEqual(UPC.objects.filter(code=upc_code).count(), 0)
        new_upc = UPC.objects.use(upc_code)
        # Only one UPC with the provided code should exist.
        self.assertEqual(UPC.objects.filter(code=upc_code).count(), 1)
        # Now we should have 3 UPC in total.
        self.assertEqual(UPC.objects.count(), 3)
        # The newly created UPC should have used as status.
        self.assertEqual(new_upc.status, UPC.STATUS_USED)
