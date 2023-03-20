from unittest import mock
from unittest.mock import MagicMock

import pytest
from django.test import TestCase

from subscriptions.vendor.google.duplicate_notification_checker import (
    DuplicateNotificationChecker,
    check_duplicate_notifications,
)
from subscriptions.vendor.google.enums import ProcessingResult


class MockNotificationProcessor(object):
    def __init__(self):
        self._event_id = '123'


PROCESSING = 1
PROCESSED = 2


class TestDuplicateNotificationChecker(TestCase):
    def setUp(self):
        self.payload = {'message': {'message_id': '123'}}
        checker = DuplicateNotificationChecker({'message': {'message_id': '123'}})

    @mock.patch('django.core.cache.cache.get', return_value=None)
    @mock.patch('django.core.cache.cache.set')
    def test_set_processed(self, mock_set, __):
        checker = DuplicateNotificationChecker(self.payload)
        checker.set_processed()

        mock_set.assert_called_once()
        self.assertTrue(checker.is_processed())
        self.assertFalse(checker.is_processing())

    @mock.patch('django.core.cache.cache.get', return_value=None)
    @mock.patch('django.core.cache.cache.set')
    def test_set_processing(self, mock_set, __):
        checker = DuplicateNotificationChecker(self.payload)
        checker.set_processing()

        mock_set.assert_called_once()
        self.assertTrue(checker.is_processing())
        self.assertFalse(checker.is_processed())

    @mock.patch('django.core.cache.cache.get', return_value=None)
    @mock.patch('django.core.cache.cache.delete')
    def test_clear(self, mock_delete, __):
        checker = DuplicateNotificationChecker(self.payload)
        checker.clear()

        mock_delete.assert_called_once()
        self.assertFalse(checker.is_processing())
        self.assertFalse(checker.is_processed())


class TestNonCachedNotification(TestCase):
    def setUp(self):
        self.mock = MagicMock()
        self.decorated = check_duplicate_notifications(self.mock)

        self.processor = MockNotificationProcessor()
        self.payload = {'message': {'message_id': '123'}}

    @mock.patch('django.core.cache.cache.get', return_value=None)
    @mock.patch('django.core.cache.cache.set')
    @mock.patch.object(DuplicateNotificationChecker, 'set_processing')
    def test_noncached_notification_return_decorated_value(
        self, mock_set_processing, _, __
    ):
        self.mock.return_value = 'result'
        actual = self.decorated(self.processor, self.payload)

        self.assertEqual('result', actual)
        mock_set_processing.assert_called_once()

    @mock.patch('django.core.cache.cache.get', return_value=None)
    @mock.patch('django.core.cache.cache.set')
    @mock.patch.object(DuplicateNotificationChecker, 'set_processing')
    @mock.patch.object(DuplicateNotificationChecker, 'set_processed')
    def test_noncached_notification_return_success(
        self, mock_set_processed, mock_set_processing, _, __
    ):
        self.mock.return_value = ProcessingResult.SUCCESS
        actual = self.decorated(self.processor, self.payload)

        self.assertEqual(ProcessingResult.SUCCESS, actual)
        mock_set_processing.assert_called_once()
        mock_set_processed.assert_called_once()

    @mock.patch('django.core.cache.cache.get', return_value=None)
    @mock.patch('django.core.cache.cache.set')
    @mock.patch.object(DuplicateNotificationChecker, 'set_processing')
    @mock.patch.object(DuplicateNotificationChecker, 'clear')
    def test_noncached_notification_return_fail(
        self, mock_clear, mock_set_processing, _, __
    ):
        self.mock.return_value = ProcessingResult.FAIL
        actual = self.decorated(self.processor, self.payload)

        self.assertEqual(ProcessingResult.FAIL, actual)
        mock_set_processing.assert_called_once()
        mock_clear.assert_called_once()

    @mock.patch('django.core.cache.cache.get', return_value=None)
    @mock.patch('django.core.cache.cache.set')
    @mock.patch.object(DuplicateNotificationChecker, 'set_processing')
    @mock.patch.object(DuplicateNotificationChecker, 'clear')
    def test_noncached_notification_raise_exception(
        self, mock_clear, mock_set_processing, _, __
    ):
        self.mock.side_effect = Exception('oh no!')
        with pytest.raises(Exception):
            self.decorated(self.processor, self.payload)

        mock_set_processing.assert_called_once()
        mock_clear.assert_called_once()

    @mock.patch('django.core.cache.cache.get', return_value=PROCESSING)
    def test_processing_notification_return_fail(self, _):
        actual = self.decorated(self.processor, self.payload)
        self.assertEqual(ProcessingResult.FAIL, actual)

    @mock.patch('django.core.cache.cache.get', return_value=PROCESSED)
    def test_processed_notification_return_success(self, _):
        actual = self.decorated(self.processor, self.payload)
        self.assertEqual(ProcessingResult.SUCCESS, actual)
