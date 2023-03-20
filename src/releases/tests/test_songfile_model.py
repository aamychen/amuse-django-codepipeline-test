from django.test import TestCase, override_settings
from unittest import mock
from simple_history.manager import HistoryManager
from releases.tests.factories import SongFactory
from releases.models import SongFile


class SongFileTestCase(TestCase):
    def test_songfile_history(self):
        """SongFile model history is enabled."""
        songfile = SongFile()
        self.assertTrue(isinstance(songfile.history, HistoryManager))
        self.assertEqual(songfile.history.count(), 0)

        songfile = SongFactory()
        # 2 because https://github.com/FactoryBoy/factory_boy/issues/316
        self.assertEqual(songfile.history.count(), 2)
