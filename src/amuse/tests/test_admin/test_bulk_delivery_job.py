from datetime import date, datetime, timedelta
from unittest import mock

import pytest
import responses
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, RequestFactory
from django.urls import reverse_lazy as reverse
from rest_framework import status

from amuse.admin import (
    AddMultipleBulkDeliveryJobsForm,
    BulkDeliveryJobAdmin,
    BulkDeliveryJobForm,
)
from amuse.models.bulk_delivery_job import BulkDeliveryJob
from amuse.tests.factories import BulkDeliveryJobFactory
from amuse.tests.test_api.base import AmuseAPITestCase
from codes.tests.factories import ISRCFactory
from releases.tests.factories import StoreFactory, SongFactory, ReleaseFactory
from users.tests.factories import UserFactory
from users.models import User


@pytest.mark.parametrize(
    'delta_minutes,expected_errors',
    [(-10, {'start_at': ['This field value has to be in the future.']}), (10, {})],
)
@pytest.mark.django_db
def test_start_at_field(delta_minutes, expected_errors):
    form = AddMultipleBulkDeliveryJobsForm(
        data={'start_at': datetime.utcnow() + timedelta(minutes=delta_minutes)}
    )

    assert not form.is_valid()

    for k, v in expected_errors.items():
        assert form.has_error(k)
        assert form.errors[k] == v


class AddMultipleBulkDeliveryJobsTestCase(TestCase):
    @responses.activate
    def setUp(self):
        super().setUp()
        self.url = reverse('admin:amuse_bulkdeliveryjob_add_multiple')
        self.client.force_login(UserFactory(is_staff=True))
        self.store = StoreFactory()

    @responses.activate
    def test_multiple_bulk_delivery_job(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(
            response,
            'admin/amuse/bulkdeliveryjob/add_multiple_bulk_delivery_jobs_form.html',
        )

        self.assertContains(response, "chunk_size")
        self.assertContains(response, "start_at")
        self.assertContains(response, "delay_between_chunks")

        file = SimpleUploadedFile(
            name='simple.csv', content=b'release_id\n1\n2\n', content_type='text/csv'
        )
        data = {
            'input_file': file,
            'type': BulkDeliveryJob.JOB_TYPE_UPDATE,
            'mode': BulkDeliveryJob.MODE_ADD_RELEASE_STORES,
            'stores': [self.store.pk],
            'chunk_size': 200,
            'start_at': datetime.utcnow() + timedelta(days=2),
            'delay_between_chunks': 10,
        }
        self.assertEqual(0, BulkDeliveryJob.objects.count())
        response = self.client.post(self.url, data=data)
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            response.url, reverse('admin:amuse_bulkdeliveryjob_changelist')
        )
        self.assertEqual(1, BulkDeliveryJob.objects.count())


class BulkDeliveryJobAdminTestCase(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.admin_user = UserFactory(is_staff=True, category=User.CATEGORY_DEFAULT)
        self.client.force_login(user=self.admin_user)
        self.url = reverse("admin:amuse_bulkdeliveryjob_add")
        self.file = SimpleUploadedFile(
            name="simple.csv", content=b"release_id\n1\n2\n", content_type="text/csv"
        )
        self.store = StoreFactory()
        self.youtube_content_id = StoreFactory(internal_name='youtube_content_id')

        self.isrc_1 = ISRCFactory(code="123abc")
        self.isrc_2 = ISRCFactory(code="abc123")
        self.isrc_file = SimpleUploadedFile(
            name="isrcs.csv", content=b"isrc\n123abc\nabc321\n", content_type="text/csv"
        )

    @mock.patch("amuse.tasks.bulk_delivery_job_command.delay")
    def test_non_scheduled_task_is_executed(self, task_delay_mock):
        data = {"input_file": self.file, "type": 0, "store": self.store.pk, "mode": 1}
        self.client.post(self.url, data, format="json")
        job = BulkDeliveryJob.objects.last()
        task_delay_mock.assert_called_once_with(job.pk)

    @mock.patch("amuse.tasks.bulk_delivery_job_command.delay")
    def test_scheduled_task_is_not_executed(self, task_delay_mock):
        data = {
            "input_file": self.file,
            "type": 0,
            "store": self.store.pk,
            "mode": 1,
            "execute_at_0": (date.today() + timedelta(days=10)).isoformat(),
            "execute_at_1": "00:00:00",
        }
        self.client.post(self.url, data, format="json")
        task_delay_mock.assert_not_called()

    @mock.patch("amuse.tasks.bulk_delivery_job_command.delay")
    def test_add_bulk_delivery_job_saves_stores(self, task_delay_mock):
        data = {"input_file": self.file, "type": 0, "store": self.store.pk, "mode": 1}
        response = self.client.post(self.url, data, format="json")
        job = BulkDeliveryJob.objects.last()

        assert response.status_code == status.HTTP_302_FOUND
        task_delay_mock.assert_called_once_with(job.pk)
        assert job.store == self.store

    @mock.patch("amuse.tasks.bulk_delivery_job_command.delay")
    def test_youtube_content_id_updates(self, task_delay_mock):
        data = {
            "input_file": self.file,
            "type": 0,
            "mode": 0,
            "store": self.youtube_content_id.pk,
            "youtube_content_id": 2,
        }
        response = self.client.post(self.url, data, format="json")
        job = BulkDeliveryJob.objects.last()

        assert response.status_code == status.HTTP_302_FOUND
        task_delay_mock.assert_called_once_with(job.pk)
        assert job.youtube_content_id == data['youtube_content_id']
        assert job.store == self.youtube_content_id

    def test_update_youtube_content_id_no_store(self):
        job = BulkDeliveryJobFactory(youtube_content_id=1, mode=0)
        job.execute()
        assert job.status == BulkDeliveryJob.STATUS_FAILED

    def test_update_youtube_content_id_no_content_id(self):
        job = BulkDeliveryJobFactory(
            store=StoreFactory(name='youtube_content_id'), mode=0
        )
        job.execute()
        assert job.status == BulkDeliveryJob.STATUS_FAILED

    def test_has_delete_permissions(self):
        request = RequestFactory().get('/admin')
        request.user = self.admin_user

        admin = BulkDeliveryJobAdmin(BulkDeliveryJob, AdminSite())

        # has permissions by default (no objects selected)
        self.assertTrue(admin.has_delete_permission(request, None))

        # has no permissions for non-scheduled object
        job = BulkDeliveryJobFactory()
        self.assertFalse(admin.has_delete_permission(request, job))

        # has no permissions for object with status different from CREATED
        for status in [
            BulkDeliveryJob.STATUS_PROCESSING,
            BulkDeliveryJob.STATUS_COMPLETED,
            BulkDeliveryJob.STATUS_FAILED,
        ]:
            job = BulkDeliveryJobFactory(status=status)
            self.assertFalse(admin.has_delete_permission(request, job))

        # has permissions for scheduled object
        job = BulkDeliveryJobFactory(execute_at=datetime.utcnow())
        self.assertTrue(admin.has_delete_permission(request, job))

    @mock.patch("amuse.tasks.bulk_delivery_job_command.delay")
    def test_update_with_isrc(self, task_delay_mock):
        data = {
            "input_file": self.isrc_file,
            "type": 0,
            "store": self.store.pk,
            "mode": 0,
        }
        response = self.client.post(self.url, data, format="json")
        job = BulkDeliveryJob.objects.last()

        assert response.status_code == status.HTTP_302_FOUND
        task_delay_mock.assert_called_once_with(job.pk)
        assert job.store == self.store

    def test_get_song_and_release_ids_with_isrc(self):
        release_1 = ReleaseFactory()
        song_1 = SongFactory(isrc=self.isrc_1, release=release_1)

        job = BulkDeliveryJobFactory(
            input_file=self.isrc_file, type=0, mode=0, store=self.store
        )
        song_ids, release_ids = job.get_release_and_song_ids()
        assert release_ids == [release_1.id]
        assert song_ids == [song_1.id]
