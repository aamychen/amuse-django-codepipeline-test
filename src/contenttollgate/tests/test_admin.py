from datetime import date, datetime, timedelta
from unittest.mock import call, patch, Mock
from unittest import skip

from django.contrib.admin.sites import AdminSite
from django.forms import ModelForm, BaseFormSet
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from amuse.models.support import SupportEvent, SupportRelease
from amuse.tests.factories import SupportEventFactory, SupportReleaseFactory
from contenttollgate.admin import ReleaseAdmin
from contenttollgate.models import GenericRelease
from releases.models import Release, Song
from releases.tests.factories import (
    ReleaseArtistRoleFactory,
    ReleaseFactory,
    SongFactory,
    StoreFactory,
    MetadataLanguageFactory,
    SongArtistRoleFactory,
    FugaMetadataFactory,
)
from subscriptions.tests.factories import SubscriptionFactory
from users.models import SongArtistInvitation
from users.tests.factories import Artistv2Factory, UserArtistRoleFactory, UserFactory


MINUTE_AGO = timezone.now() - timedelta(minutes=1)


class MockSuperUser:
    email = "fa@test.mail"

    def has_perm(self, perm):
        return True


class MockForm(ModelForm):
    class Meta:
        model = Release
        fields = ("status",)


class ReleaseAdminTest(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        self.client.force_login(user=self.user)
        self.artist_1 = Artistv2Factory()
        UserArtistRoleFactory(user=self.user, artist=self.artist_1)

        self.artist_2 = Artistv2Factory()
        self.release = ReleaseFactory(user=self.user, status=Release.STATUS_PENDING)
        ReleaseArtistRoleFactory(
            release=self.release, artist=self.artist_2, main_primary_artist=True
        )

        self.lang_en = MetadataLanguageFactory(iso_639_1="en")
        self.lang_sv = MetadataLanguageFactory(iso_639_1="sv")
        self.lang_fi = MetadataLanguageFactory(iso_639_1="fi")

    def test_disable_yt_cid(self):
        url = reverse(
            'admin:contenttollgate_genericrelease_disable_yt_content_id',
            kwargs={'object_id': self.release.id},
        )

        song = SongFactory(
            release=self.release, youtube_content_id=Song.YT_CONTENT_ID_MONETIZE
        )

        response = self.client.post(url)

        song.refresh_from_db()

        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_NONE)

    def test_disable_yt_cid_removes_yt_cid_store(self):
        store = StoreFactory(name='YouTube Content ID')
        self.release.stores.add(store)

        url = reverse(
            'admin:contenttollgate_genericrelease_disable_yt_content_id',
            kwargs={'object_id': self.release.id},
        )

        song = SongFactory(
            release=self.release, youtube_content_id=Song.YT_CONTENT_ID_MONETIZE
        )

        response = self.client.post(url)

        song.refresh_from_db()

        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_NONE)
        self.assertNotIn(store, self.release.stores.all())

    def test_enable_yt_cid(self):
        url = reverse(
            'admin:contenttollgate_genericrelease_enable_yt_content_id',
            kwargs={'object_id': self.release.id},
        )

        song = SongFactory(
            release=self.release, youtube_content_id=Song.YT_CONTENT_ID_BLOCK
        )

        response = self.client.post(url)

        song.refresh_from_db()

        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_MONETIZE)

    def test_enable_yt_cid_adds_yt_cid_store(self):
        store = StoreFactory(name='YouTube Content ID')

        url = reverse(
            'admin:contenttollgate_genericrelease_enable_yt_content_id',
            kwargs={'object_id': self.release.id},
        )

        song = SongFactory(
            release=self.release, youtube_content_id=Song.YT_CONTENT_ID_NONE
        )

        response = self.client.post(url)

        song.refresh_from_db()

        self.assertEqual(song.youtube_content_id, Song.YT_CONTENT_ID_MONETIZE)
        self.assertIn(store, self.release.stores.all())

    def test_generic_release_shows_the_correct_artist_name(self):
        url = reverse('admin:contenttollgate_genericrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 generic release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )

    def test_approved_release_shows_the_correct_artist_name(self):
        self.release.status = Release.STATUS_APPROVED
        self.release.save()
        url = reverse('admin:contenttollgate_approvedrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 approved release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )

    def test_assigned_pending_release_shows_the_correct_artist_name(self):
        SupportRelease.objects.create(assignee=self.user, release=self.release)
        url = reverse('admin:contenttollgate_assignedpendingrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 assigned pending release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )

    def test_assigned_prepared_release_shows_the_correct_artist_name(self):
        SupportRelease.objects.create(
            assignee=self.user, release=self.release, prepared=True
        )
        url = reverse('admin:contenttollgate_assignedpreparedrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )

    def test_delivered_release_shows_the_correct_artist_name(self):
        self.release.status = Release.STATUS_DELIVERED
        self.release.save()
        url = reverse('admin:contenttollgate_deliveredrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 delivered release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )

    def test_not_approved_release_shows_the_correct_artist_name(self):
        self.release.status = Release.STATUS_NOT_APPROVED
        self.release.save()
        url = reverse('admin:contenttollgate_notapprovedrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 not approved release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )

    def test_pending_release_shows_the_correct_artist_name(self):
        self.release.status = Release.STATUS_PENDING
        self.release.save()
        url = reverse('admin:contenttollgate_pendingrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 pending release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )

    def test_rejected_release_shows_the_correct_artist_name(self):
        self.release.status = Release.STATUS_REJECTED
        self.release.save()
        url = reverse('admin:contenttollgate_rejectedrelease_changelist')
        response = self.client.get(url)

        self.assertInHTML('1 rejected release', response.rendered_content)
        self.assertInHTML(
            f'<td class="field-get_artist_name">{self.artist_2}</td>',
            response.rendered_content,
        )


class DeliveryTest(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        self.client.force_login(user=self.user)
        self.artist_1 = Artistv2Factory()
        UserArtistRoleFactory(user=self.user, artist=self.artist_1)

        self.artist_2 = Artistv2Factory()
        self.release = ReleaseFactory(user=self.user, status=Release.STATUS_PENDING)
        ReleaseArtistRoleFactory(
            release=self.release, artist=self.artist_2, main_primary_artist=True
        )

        self.lang_en = MetadataLanguageFactory(iso_639_1="en")
        self.lang_sv = MetadataLanguageFactory(iso_639_1="sv")
        self.lang_fi = MetadataLanguageFactory(iso_639_1="fi")

    @patch('contenttollgate.admin.trigger_batch_delivery')
    @patch('contenttollgate.admin.create_batch_delivery_releases_list')
    @patch('contenttollgate.admin.ReleaseDeliveryInfo', autospec=True)
    def test_direct_deliver_single_dsp(
        self, mock_info, mock_create_batch, mock_trigger_batch
    ):
        mock_create_batch.return_value = ['mock']

        url = reverse(
            'admin:contenttollgate_genericrelease_direct_deliver',
            kwargs={'object_id': self.release.id},
        )

        response = self.client.post(url, data={'deliver_single': 'tiktok:insert'})

        assert mock_create_batch.mock_calls == [
            call('insert', [self.release], stores=['tiktok'])
        ]

        assert mock_trigger_batch.call_args_list == [
            call(mock_create_batch.return_value, self.user)
        ]

    @patch('amuse.vendor.fuga.helpers.perform_fuga_delete')
    @patch('contenttollgate.admin.trigger_batch_delivery')
    @patch('contenttollgate.admin.create_batch_delivery_releases_list')
    @patch('contenttollgate.admin.ReleaseDeliveryInfo', autospec=True)
    def test_fuga_delivery_single(
        self, mock_info, mock_create_batch, mock_trigger_batch, mock_fuga_delete
    ):
        FugaMetadataFactory(release=self.release)
        mock_info.return_value.get_fuga_delivery_channels.return_value = [
            "fuga_spotify",
            "fuga_tiktok",
        ]
        mock_create_batch.return_value = ['mock']

        url = reverse(
            'admin:contenttollgate_genericrelease_direct_deliver',
            kwargs={'object_id': self.release.id},
        )

        response = self.client.post(url, data={'deliver_single': 'fuga:takedown'})

        assert mock_create_batch.not_called()
        assert mock_fuga_delete.called_once()

    @patch('contenttollgate.admin.trigger_batch_delivery')
    @patch('contenttollgate.admin.create_batch_delivery_releases_list')
    @patch('contenttollgate.admin.ReleaseDeliveryInfo', autospec=True)
    def test_deliver_all_insert(self, mock_info, mock_create_batch, mock_trigger_batch):
        mock_info.return_value.get_fuga_delivery_channels.return_value = [
            "fuga_spotify",
            "fuga_tiktok",
            "fuga_anghami",
        ]
        mock_info.return_value.get_direct_delivery_channels.return_value = [
            "napster",
            "facebook",
            "tencent",
        ]
        mock_create_batch.return_value = ['mock']

        url = reverse(
            'admin:contenttollgate_genericrelease_direct_deliver',
            kwargs={'object_id': self.release.id},
        )

        response = self.client.post(url, data={'deliver_all': 'insert'})

        assert mock_create_batch.mock_calls == [
            call('insert', [self.release], stores=["napster", "facebook", "tencent"])
        ]

        assert mock_trigger_batch.call_args_list == [
            call(mock_create_batch.return_value, self.user)
        ]

    @patch('contenttollgate.admin.trigger_batch_delivery')
    @patch('contenttollgate.admin.create_batch_delivery_releases_list')
    @patch('contenttollgate.admin.ReleaseDeliveryInfo', autospec=True)
    def test_deliver_all_full_update(
        self, mock_info, mock_create_batch, mock_trigger_batch
    ):
        mock_info.return_value.get_fuga_delivery_channels.return_value = [
            "fuga_spotify",
            "fuga_tiktok",
            "fuga_anghami",
        ]
        mock_info.return_value.get_direct_delivery_channels.return_value = [
            "napster",
            "facebook",
            "tencent",
        ]
        mock_create_batch.return_value = ['mock']

        url = reverse(
            'admin:contenttollgate_genericrelease_direct_deliver',
            kwargs={'object_id': self.release.id},
        )

        response = self.client.post(url, data={'deliver_all': 'full_update'})

        assert mock_create_batch.mock_calls == [
            call(
                'update',
                [self.release],
                stores=["fuga_spotify", "fuga_tiktok", "fuga_anghami"],
            ),
            call('insert', [self.release], stores=["napster", "facebook", "tencent"]),
        ]

        assert mock_trigger_batch.call_args_list == [
            call(mock_create_batch.return_value, self.user),
            call(mock_create_batch.return_value, self.user),
        ]

    @patch('contenttollgate.admin.trigger_batch_delivery')
    @patch('contenttollgate.admin.create_batch_delivery_releases_list')
    @patch('contenttollgate.admin.ReleaseDeliveryInfo', autospec=True)
    def test_deliver_all_update(self, mock_info, mock_create_batch, mock_trigger_batch):
        mock_info.return_value.get_fuga_delivery_channels.return_value = []
        mock_info.return_value.get_direct_delivery_channels.return_value = [
            "napster",
            "facebook",
            "tencent",
        ]
        mock_create_batch.return_value = ['mock']

        url = reverse(
            'admin:contenttollgate_genericrelease_direct_deliver',
            kwargs={'object_id': self.release.id},
        )

        response = self.client.post(url, data={'deliver_all': 'update'})

        assert mock_create_batch.mock_calls == [
            call('update', [self.release], stores=["napster", "facebook", "tencent"])
        ]

        assert mock_trigger_batch.call_args_list == [
            call(mock_create_batch.return_value, self.user)
        ]

    @patch('amuse.vendor.fuga.helpers.perform_fuga_delete')
    @patch('contenttollgate.admin.trigger_batch_delivery')
    @patch('contenttollgate.admin.create_batch_delivery_releases_list')
    @patch('contenttollgate.admin.ReleaseDeliveryInfo', autospec=True)
    def test_deliver_all_takedown(
        self, mock_info, mock_create_batch, mock_trigger_batch, mock_fuga_delete
    ):
        FugaMetadataFactory(release=self.release)

        mock_info.return_value.get_fuga_delivery_channels.return_value = [
            "fuga_spotify",
            "fuga_tiktok",
            "fuga_anghami",
        ]
        mock_info.return_value.get_direct_delivery_channels.return_value = [
            "napster",
            "facebook",
            "tencent",
        ]
        mock_create_batch.return_value = ['mock']

        url = reverse(
            'admin:contenttollgate_genericrelease_direct_deliver',
            kwargs={'object_id': self.release.id},
        )

        response = self.client.post(url, data={'deliver_all': 'takedown'})

        assert mock_create_batch.mock_calls == [
            call('takedown', [self.release], stores=["napster", "facebook", "tencent"])
        ]

        assert mock_trigger_batch.call_args_list == [
            call(mock_create_batch.return_value, self.user)
        ]

        assert mock_fuga_delete.called_once()


class PendingReleaseAdminTest(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        self.client.force_login(user=self.user)
        self.release = ReleaseFactory(
            user=self.user, status=Release.STATUS_PENDING, created_by=self.user
        )

    def test_user_has_no_pending_free_releases_assigned(self):
        url = reverse('admin:contenttollgate_assignedpendingrelease_changelist')
        response = self.client.get(url)
        self.assertTemplateUsed(
            response, 'admin/contenttollgate/assignedpendingrelease/change_list.html'
        )
        self.assertTemplateUsed(
            response, 'admin/contenttollgate/assigned_release_change_form.html'
        )
        self.assertInHTML('0 assigned pending releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(release=self.release, user=self.user).count(), 0
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_pending_free_releases_sorted_by_created(self, mocked_logger):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?sort=created_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'pending free releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned pending releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(release=self.release, user=self.user).count(), 0
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_pending_free_releases_sorted_by_created(self, mocked_logger):
        url = '{}?sort=created_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'1 pending free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned pending release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=False
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            1,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_pending_free_releases_sorted_by_created(
        self, _, mocked_logger
    ):
        url = '{}?sort=created_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        releases = [
            ReleaseFactory(status=Release.STATUS_PENDING, user=user, created_by=user)
            for user in UserFactory.create_batch(10)
        ]
        self.release.created = timezone.now()
        self.release.save()
        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'10 pending free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned pending releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=False
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                1,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_pending_free_releases_sorted_by_updated(self, mocked_logger):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?sort=updated_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'pending free releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned pending releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=False
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_pending_free_releases_sorted_by_updated(self, mocked_logger):
        url = '{}?sort=updated_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'1 pending free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned pending release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=False
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            1,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_pending_free_releases_sorted_by_updated(
        self, _, mocked_logger
    ):
        url = '{}?sort=updated_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        releases = [
            ReleaseFactory(status=Release.STATUS_PENDING, user=user, created_by=user)
            for user in UserFactory.create_batch(10)
        ]
        self.release.updated = timezone.now()
        self.release.save()
        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'10 pending free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned pending releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=False
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                1,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_pending_free_releases_sorted_by_release_date(
        self, mocked_logger
    ):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?sort=release_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'pending free releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned pending releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(release=self.release, user=self.user).count(), 0
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_pending_free_releases_sorted_by_release_date(
        self, mocked_logger
    ):
        url = '{}?sort=release_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'1 pending free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned pending release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=False
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            1,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_pending_free_releases_sorted_by_release_date(
        self, _, mocked_logger
    ):
        url = '{}?sort=release_date&subscription=free'.format(
            reverse('admin:assign_pending_releases')
        )
        releases = [
            ReleaseFactory(status=Release.STATUS_PENDING, user=user, created_by=user)
            for user in UserFactory.create_batch(10)
        ]
        self.release.release_date = timezone.now().date()
        self.release.save()
        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending free releases to user {self.user.id}'),
                call(
                    f'10 pending free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned pending releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=False
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                1,
            )


class PendingProReleaseAdminTest(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        self.client.force_login(user=self.user)
        SubscriptionFactory(user=self.user)
        self.release = ReleaseFactory(
            user=self.user, status=Release.STATUS_PENDING, created_by=self.user
        )
        self.release.created = MINUTE_AGO
        self.release.save()

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_pending_pro_releases_sorted_by_created(self, mocked_logger):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?sort=created_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'pending pro releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned pending releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(release=self.release, user=self.user).count(), 0
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_pending_pro_releases_sorted_by_created(self, mocked_logger):
        url = '{}?sort=created_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'1 pending pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned pending release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=False
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            1,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_pending_pro_releases_sorted_by_created(
        self, _, mocked_logger
    ):
        url = '{}?sort=created_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        releases = []
        for user in UserFactory.create_batch(10):
            SubscriptionFactory(user=user)
            release = ReleaseFactory(
                user=user, status=Release.STATUS_PENDING, created_by=user
            )
            release.created = MINUTE_AGO
            release.save()
            releases.append(release)
        self.release.created = timezone.now()
        self.release.save()
        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'10 pending pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned pending releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=False
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                1,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_pending_pro_releases_sorted_by_updated(self, mocked_logger):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?sort=updated_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'pending pro releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned pending releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(release=self.release, user=self.user).count(), 0
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_pending_pro_releases_sorted_by_updated(self, mocked_logger):
        url = '{}?sort=updated_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'1 pending pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned pending release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=False
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            1,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_pending_pro_releases_sorted_by_updated(
        self, _, mocked_logger
    ):
        url = '{}?sort=updated_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        releases = []
        for user in UserFactory.create_batch(10):
            SubscriptionFactory(user=user)
            release = ReleaseFactory(
                user=user, status=Release.STATUS_PENDING, created_by=user
            )
            release.created = MINUTE_AGO
            release.save()
            releases.append(release)
        self.release.updated = timezone.now()
        self.release.save()

        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'10 pending pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned pending releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=False
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                1,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_pending_pro_releases_sorted_by_release_date(
        self, mocked_logger
    ):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?sort=release_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'pending pro releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned pending releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(release=self.release, user=self.user).count(), 0
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_pending_pro_releases_sorted_by_release_date(
        self, mocked_logger
    ):
        url = '{}?sort=release_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'1 pending pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned pending release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=False
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            1,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_pending_pro_releases_sorted_by_release_date(
        self, _, mocked_logger
    ):
        url = '{}?sort=release_date&subscription=pro'.format(
            reverse('admin:assign_pending_releases')
        )
        releases = []
        for user in UserFactory.create_batch(10):
            SubscriptionFactory(user=user)
            release = ReleaseFactory(
                user=user, status=Release.STATUS_PENDING, created_by=user
            )
            release.created = MINUTE_AGO
            release.save()
            releases.append(release)
        self.release.release_date = timezone.now().date()
        self.release.save()

        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning pending pro releases to user {self.user.id}'),
                call(
                    f'10 pending pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned pending releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=False
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                1,
            )


class PreparedReleaseAdminTest(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        self.client.force_login(user=self.user)
        self.release = ReleaseFactory(
            user=self.user, status=Release.STATUS_PENDING, created_by=self.user
        )

    def test_user_has_no_prepared_free_releases_assigned(self):
        url = reverse('admin:contenttollgate_assignedpreparedrelease_changelist')
        response = self.client.get(url)
        self.assertTemplateUsed(
            response, 'admin/contenttollgate/assignedpreparedrelease/change_list.html'
        )
        self.assertTemplateUsed(
            response, 'admin/contenttollgate/assigned_release_change_form.html'
        )
        self.assertInHTML('0 assigned prepared releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_prepared_free_releases_sorted_by_created(
        self, mocked_logger
    ):
        url = '{}?prepared=1&sort=created_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'prepared free releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned prepared releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_prepared_release_sorted_by_created(self, mocked_logger):
        SupportReleaseFactory(release=self.release, assignee=self.user, prepared=True)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED, release=self.release, user=self.user
        )

        url = '{}?prepared=1&sort=created_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'1 prepared free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            2,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_prepared_free_releases_sorted_by_created(
        self, _, mocked_logger
    ):
        releases = [
            ReleaseFactory(status=Release.STATUS_PENDING, created_by=user, user=user)
            for user in UserFactory.create_batch(10)
        ]
        [
            (
                SupportReleaseFactory(
                    release=release, assignee=self.user, prepared=True
                ),
                SupportEventFactory(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ),
            )
            for release in releases
        ]
        self.release.created = timezone.now()
        self.release.save()
        url = '{}?prepared=1&sort=created_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'10 prepared free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned prepared releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=True
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                2,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_prepared_free_releases_sorted_by_updated(
        self, mocked_logger
    ):
        url = '{}?prepared=1&sort=updated_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'prepared free releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned prepared releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_prepared_release_sorted_by_updated(self, mocked_logger):
        SupportReleaseFactory(release=self.release, assignee=self.user, prepared=True)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED, release=self.release, user=self.user
        )

        url = '{}?prepared=1&sort=updated_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'1 prepared free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            1,
        )
        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            2,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_prepared_free_releases_sorted_by_updated(
        self, _, mocked_logger
    ):
        releases = [
            ReleaseFactory(status=Release.STATUS_PENDING, created_by=user)
            for user in UserFactory.create_batch(10)
        ]
        [
            (
                SupportReleaseFactory(
                    release=release, assignee=self.user, prepared=True
                ),
                SupportEventFactory(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ),
            )
            for release in releases
        ]
        self.release.updated = timezone.now()
        self.release.save()
        url = '{}?prepared=1&sort=updated_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'10 prepared free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned prepared releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=True
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                2,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_prepared_free_releases_sorted_by_release_date(
        self, mocked_logger
    ):
        url = '{}?prepared=1&sort=release_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'prepared free releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned prepared releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_prepared_release_sorted_by_release_date(self, mocked_logger):
        SupportReleaseFactory(release=self.release, assignee=self.user, prepared=True)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED, release=self.release, user=self.user
        )

        url = '{}?prepared=1&sort=release_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'1 prepared free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            2,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_prepared_free_releases_assigned_sorted_by_release_date(
        self, _, mocked_logger
    ):
        releases = [
            ReleaseFactory(status=Release.STATUS_PENDING, created_by=user)
            for user in UserFactory.create_batch(10)
        ]
        [
            (
                SupportReleaseFactory(
                    release=release, assignee=self.user, prepared=True
                ),
                SupportEventFactory(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ),
            )
            for release in releases
        ]
        self.release.release_date = timezone.now().date()
        self.release.save()
        url = '{}?prepared=1&sort=release_date&subscription=free'.format(
            reverse('admin:assign_prepared_releases')
        )
        self.assertEqual(Release.objects.count(), 11)
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared free releases to user {self.user.id}'),
                call(
                    f'10 prepared free releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned prepared releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Free Tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=True
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                2,
            )


class PreparedProReleaseAdminTest(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        SubscriptionFactory(user=self.user)
        self.client.force_login(user=self.user)
        self.release = ReleaseFactory(
            user=self.user, status=Release.STATUS_PENDING, created_by=self.user
        )
        self.release.created = MINUTE_AGO
        self.release.save()

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_prepared_pro_releases_sorted_by_created(self, mocked_logger):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?prepared=1&sort=created_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'prepared pro releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned prepared releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_prepared_pro_releases_sorted_by_created(self, mocked_logger):
        SupportReleaseFactory(release=self.release, assignee=self.user, prepared=True)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED, release=self.release, user=self.user
        )
        url = '{}?prepared=1&sort=created_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'1 prepared pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            2,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_prepared_pro_releases_sorted_by_created(
        self, _, mocked_logger
    ):
        releases = []
        for user in UserFactory.create_batch(10):
            SubscriptionFactory(user=user)
            release = ReleaseFactory(
                status=Release.STATUS_PENDING, user=user, created_by=user
            )
            release.created = MINUTE_AGO
            release.save()
            SupportReleaseFactory(release=release, assignee=self.user, prepared=True),
            SupportEventFactory(
                event=SupportEvent.ASSIGNED, release=release, user=self.user
            )
            releases.append(release)
        self.release.created = timezone.now()
        self.release.save()

        self.assertEqual(Release.objects.count(), 11)
        url = '{}?prepared=1&sort=created_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'10 prepared pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned prepared releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=True
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                2,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_prepared_pro_releases_sorted_by_updated(self, mocked_logger):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?prepared=1&sort=updated_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'prepared pro releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned prepared releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_prepared_pro_releases_sorted_by_updated(self, mocked_logger):
        SupportReleaseFactory(release=self.release, assignee=self.user, prepared=True)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED, release=self.release, user=self.user
        )
        url = '{}?prepared=1&sort=updated_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'1 prepared pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            2,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_prepared_pro_releases_sorted_by_updated(
        self, _, mocked_logger
    ):
        releases = []
        for user in UserFactory.create_batch(10):
            SubscriptionFactory(user=user)
            release = ReleaseFactory(
                status=Release.STATUS_PENDING, user=user, created_by=user
            )
            release.created = MINUTE_AGO
            release.save()
            SupportReleaseFactory(release=release, assignee=self.user, prepared=True),
            SupportEventFactory(
                event=SupportEvent.ASSIGNED, release=release, user=self.user
            )
            releases.append(release)
        self.release.updated = timezone.now()
        self.release.save()

        self.assertEqual(Release.objects.count(), 11)
        url = '{}?prepared=1&sort=updated_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'10 prepared pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned prepared releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=True
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                2,
            )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_0_prepared_pro_releases_sorted_by_release_date(
        self, mocked_logger
    ):
        self.release.status = Release.STATUS_SUBMITTED
        self.release.save()
        url = '{}?prepared=1&sort=release_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'prepared pro releases failed to be assigned to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('0 assigned prepared releases', response.rendered_content)
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            0,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            0,
        )

    @patch('contenttollgate.admin.logger')
    def test_user_assign_1_prepared_pro_releases_sorted_by_release_date(
        self, mocked_logger
    ):
        SupportReleaseFactory(release=self.release, assignee=self.user, prepared=True)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED, release=self.release, user=self.user
        )
        url = '{}?prepared=1&sort=release_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'1 prepared pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('1 assigned prepared release', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            1,
        )
        self.assertEqual(
            SupportRelease.objects.filter(
                release=self.release, assignee=self.user, prepared=True
            ).count(),
            1,
        )
        self.assertEqual(
            SupportEvent.objects.filter(
                event=SupportEvent.ASSIGNED, release=self.release, user=self.user
            ).count(),
            2,
        )

    @patch('contenttollgate.admin.logger')
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def test_user_assign_10_prepared_pro_releases_sorted_by_release_date(
        self, _, mocked_logger
    ):
        releases = []
        for user in UserFactory.create_batch(10):
            SubscriptionFactory(user=user)
            release = ReleaseFactory(
                status=Release.STATUS_PENDING, user=user, created_by=user
            )
            release.created = MINUTE_AGO
            release.save()
            SupportReleaseFactory(release=release, assignee=self.user, prepared=True),
            SupportEventFactory(
                event=SupportEvent.ASSIGNED, release=release, user=self.user
            )
            releases.append(release)
        self.release.release_date = timezone.now().date()
        self.release.save()

        self.assertEqual(Release.objects.count(), 11)
        url = '{}?prepared=1&sort=release_date&subscription=pro'.format(
            reverse('admin:assign_prepared_releases')
        )
        response = self.client.get(url, follow=True)
        self.assertEqual(
            mocked_logger.info.call_args_list,
            [
                call(f'Assigning prepared pro releases to user {self.user.id}'),
                call(
                    f'10 prepared pro releases were assigned successfully to user {self.user.id}'
                ),
            ],
        )
        self.assertInHTML('10 assigned prepared releases', response.rendered_content)
        self.assertInHTML(
            '<td class="field-get_subscription_tier">Amuse PRO subscription tier</td>',
            response.rendered_content,
            10,
        )
        for release in releases:
            self.assertEqual(
                SupportRelease.objects.filter(
                    release=release, assignee=self.user, prepared=True
                ).count(),
                1,
            )
            self.assertEqual(
                SupportEvent.objects.filter(
                    event=SupportEvent.ASSIGNED, release=release, user=self.user
                ).count(),
                2,
            )


class BaseReleaseAdminTest:
    @classmethod
    def setUpTestData(cls):
        created = datetime(2020, 2, 10, 0, 0, tzinfo=timezone.utc)
        with patch('amuse.tasks.zendesk_create_or_update_user'):
            cls.user_1 = UserFactory()
            cls.user_2 = UserFactory()
            cls.admin = UserFactory(is_staff=True)
        cls.release_1 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_1.release_date = date(2020, 5, 10)
        cls.release_1.created = created
        cls.release_1.save()
        cls.release_2 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_2.release_date = date(2021, 3, 10)
        cls.release_2.created = created
        cls.release_2.save()
        cls.release_3 = ReleaseFactory(
            user=cls.user_2, created_by=cls.user_2, status=Release.STATUS_PENDING
        )
        cls.release_3.release_date = date(2021, 7, 10)
        cls.release_3.created = created
        cls.release_3.save()

    def setUp(self):
        self.client.force_login(user=self.admin)
        self.response = self.client.get(reverse(self.url))

    @skip("Static files changed in Djanog3.2")
    def test_releases_will_showup_sorted_by_release_date(self):
        self.assertRegex(
            self.response.rendered_content,
            '<tr class="row1">.*</td><td class="field-release_date nowrap">'
            f'{self.release_1.release_date:%B %d, %Y}</td>',
        )
        self.assertRegex(
            self.response.rendered_content,
            '<tr class="row2">.*</td><td class="field-release_date nowrap">'
            f'{self.release_2.release_date:%B %d, %Y}</td>',
        )
        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            self.response.rendered_content,
            2,
        )

        self.assertNotIn(
            '</td><td class="field-release_date nowrap">'
            f'{self.release_3.release_date:%B %d, %Y}</td>',
            self.response.rendered_content,
        )
        self.assertNotContains(
            self.response,
            f'<td class="field-get_subscription_tier">{"Free Tier" if self.is_pro else "Amuse PRO subscription tier"}</td>',
        )

    def test_releases_list_will_show_the_default_fields(self):
        self.assertInHTML(
            '<div class="text"><a href="?o=1">Name</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=2">Status</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=3">Artist</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=4">E-mail</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=5">User category</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><span>Subscription Tier</span></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=8">Release date</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=9">Updated</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=7">Schedule type</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=10">Created</a></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><span>Assignee</span></div>',
            self.response.rendered_content,
        )
        self.assertInHTML(
            '<div class="text"><a href="?o=12">Comments</a></div>',
            self.response.rendered_content,
        )


class ProReleaseAdminTest(BaseReleaseAdminTest, TestCase):
    url = 'admin:contenttollgate_prorelease_changelist'
    is_pro = True

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        SubscriptionFactory(user=cls.user_1, valid_from=date(2020, 1, 10))


class FreeReleaseAdminTest(BaseReleaseAdminTest, TestCase):
    url = 'admin:contenttollgate_freerelease_changelist'
    is_pro = False

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        SubscriptionFactory(user=cls.user_2, valid_from=date(2020, 1, 10))


class BaseReleaseAdminFilterTest:
    @classmethod
    def setUpTestData(cls):
        created = datetime(2020, 2, 10, 0, 0, tzinfo=timezone.utc)
        with patch('amuse.tasks.zendesk_create_or_update_user'):
            cls.user_1 = UserFactory()
            cls.user_2 = UserFactory()
            cls.admin = UserFactory(is_staff=True)

        cls.release_1 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_1.release_date = date(2020, 8, 1)
        cls.release_1.created = created
        cls.release_1.save()

        cls.release_2 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_2.release_date = date(2020, 9, 4)
        cls.release_2.created = created
        cls.release_2.save()

        cls.release_3 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_3.release_date = date(2020, 9, 7)
        cls.release_3.created = created
        cls.release_3.save()

        cls.release_4 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_4.release_date = date(2020, 9, 14)
        cls.release_4.created = created
        cls.release_4.save()

        cls.release_5 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_5.release_date = date(2020, 9, 30)
        cls.release_5.created = created
        cls.release_5.save()

        cls.release_6 = ReleaseFactory(
            user=cls.user_2, created_by=cls.user_2, status=Release.STATUS_PENDING
        )
        cls.release_6.release_date = date(2021, 7, 10)
        cls.release_6.created = created
        cls.release_6.save()

    def setUp(self):
        self.client.force_login(user=self.admin)

    @freeze_time("2020-09-01")
    def test_get_releases_default_page(self):
        response = self.client.get(reverse(self.url))
        self.assertIn(
            f'5 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )
        self.assertInHTML(
            '<li class="selected"><a href="?" title="All">All</a></li>',
            response.rendered_content,
        )
        self.assertInHTML(
            '<li><a href="?release_date=4" title="4 days">4 days</a></li>',
            response.rendered_content,
        )
        self.assertInHTML(
            '<li><a href="?release_date=7" title="7 days">7 days</a></li>',
            response.rendered_content,
        )
        self.assertInHTML(
            '<li><a href="?release_date=14" title="14 days">14 days</a></li>',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_4.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_5.id}/change/',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            5,
        )
        self.assertNotContains(
            response,
            f'<td class="field-get_subscription_tier">{"Free Tier" if self.is_pro else "Amuse PRO subscription tier"}</td>',
        )

    @freeze_time("2020-09-01")
    def test_get_releases_when_release_date_in_1_day_is_selected(self):
        response = self.client.get(reverse(self.url), {'release_date': '4'})
        self.assertInHTML(
            '<li class="selected"><a href="?release_date=4" title="4 days">4 days</a>'
            '</li>',
            response.rendered_content,
        )
        self.assertIn(
            f'2 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/?_changelist_filters=release_date%3D4',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/?_changelist_filters=release_date%3D4',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            2,
        )
        self.assertNotContains(
            response,
            f'<td class="field-get_subscription_tier">{"Free Tier" if self.is_pro else "Amuse PRO subscription tier"}</td>',
        )

    @freeze_time("2020-09-01")
    def test_get_releases_when_release_date_in_7_days_is_selected(self):
        response = self.client.get(reverse(self.url), {'release_date': '7'})
        self.assertInHTML(
            '<li class="selected"><a href="?release_date=7" title="7 days">7 days</a>'
            '</li>',
            response.rendered_content,
        )
        self.assertIn(
            f'3 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/'
            '?_changelist_filters=release_date%3D7',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/'
            '?_changelist_filters=release_date%3D7',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/'
            '?_changelist_filters=release_date%3D7',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            3,
        )
        self.assertNotContains(
            response,
            f'<td class="field-get_subscription_tier">{"Free Tier" if self.is_pro else "Amuse PRO subscription tier"}</td>',
        )

    @freeze_time("2020-09-01")
    def test_get_releases_when_release_date_in_14_days_is_selected(self):
        response = self.client.get(reverse(self.url), {'release_date': '14'})
        self.assertInHTML(
            '<li class="selected"><a href="?release_date=14" title="14 days">14 days'
            '</a></li>',
            response.rendered_content,
        )
        self.assertIn(
            f'4 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/'
            '?_changelist_filters=release_date%3D14',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/'
            '?_changelist_filters=release_date%3D14',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/'
            '?_changelist_filters=release_date%3D14',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_4.id}/change/'
            '?_changelist_filters=release_date%3D14',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            4,
        )
        self.assertNotContains(
            response,
            f'<td class="field-get_subscription_tier">{"Free Tier" if self.is_pro else "Amuse PRO subscription tier"}</td>',
        )


class ProReleaseAdminFilterTest(BaseReleaseAdminFilterTest, TestCase):
    url = 'admin:contenttollgate_prorelease_changelist'
    is_pro = True

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        SubscriptionFactory(user=cls.user_1, valid_from=date(2020, 1, 10))


class FreeReleaseAdminFilterTest(BaseReleaseAdminFilterTest, TestCase):
    url = 'admin:contenttollgate_freerelease_changelist'
    is_pro = False

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        SubscriptionFactory(user=cls.user_2, valid_from=date(2020, 1, 10))


class ReleaseAssignToMeActionTest:
    @classmethod
    def setUpTestData(cls):
        created = datetime(2020, 2, 10, 0, 0, tzinfo=timezone.utc)
        with patch('amuse.tasks.zendesk_create_or_update_user'):
            cls.user_1 = UserFactory()
            cls.admin = UserFactory(is_staff=True)
            cls.content_ops_agent = UserFactory(is_staff=True)

        cls.release_1 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_1.release_date = date(2020, 8, 1)
        cls.release_1.created = created
        cls.release_1.save()

        cls.release_2 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_2.release_date = date(2020, 9, 4)
        cls.release_2.created = created
        cls.release_2.save()

        cls.release_3 = ReleaseFactory(
            user=cls.user_1, created_by=cls.user_1, status=Release.STATUS_PENDING
        )
        cls.release_3.release_date = date(2020, 9, 7)
        cls.release_3.created = created
        cls.release_3.save()
        SupportReleaseFactory(release=cls.release_3, assignee=cls.content_ops_agent)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED,
            release=cls.release_3,
            user=cls.content_ops_agent,
        )

    def setUp(self):
        self.client.force_login(user=self.admin)

    def test_assign_pro_releases_to_me_default_page(self):
        response = self.client.get(reverse(self.url))
        self.assertIn(
            f'3 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )
        self.assertInHTML(
            '<option value="assign_to_me">Assign to me</option>',
            response.rendered_content,
        )
        self.assertNotIn(
            '<option value="delete_selected">Delete selected  '
            '{"pro" if self.is_pro else "free"} releases</option>',
            response.rendered_content,
        )

        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/',
            response.rendered_content,
        )
        self.assertInHTML(
            '<td class="field-get_assignee">-</td>', response.rendered_content, 2
        )
        self.assertInHTML(
            f'<td class="field-get_assignee">{self.content_ops_agent}</td>',
            response.rendered_content,
        )

        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            3,
        )
        self.assertNotContains(
            response,
            f'<td class="field-get_subscription_tier">{"Free Tier" if self.is_pro else "Amuse PRO subscription tier"}</td>',
        )

    def test_assign_one_pro_release_to_me(self):
        data = {
            'csrfmiddlewaretoken': 'H3Z2pQPvj8ihzKVC5JY0QA10UgnuZCjXmVhExMpzZY7k',
            'action': 'assign_to_me',
            '_selected_action': self.release_1.id,
        }
        self.assertEqual(SupportRelease.objects.count(), 1)
        self.assertEqual(SupportEvent.objects.count(), 1)
        response = self.client.post(reverse(self.url), follow=True, data=data)
        self.assertIn(
            f'1 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )

        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/',
            response.rendered_content,
        )
        self.assertInHTML(
            '<td class="field-get_assignee">-</td>', response.rendered_content
        )
        self.assertInHTML(
            f'<td class="field-get_assignee">{self.content_ops_agent}</td>',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_assignee">{self.admin}</td>',
            response.rendered_content,
        )

        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            3,
        )
        self.assertEqual(SupportRelease.objects.count(), 2)
        self.assertEqual(SupportEvent.objects.count(), 2)

    def test_re_assign_one_pro_release_to_me(self):
        data = {
            'csrfmiddlewaretoken': 'H3Z2pQPvj8ihzKVC5JY0QA10UgnuZCjXmVhExMpzZY7k',
            'action': 'assign_to_me',
            '_selected_action': self.release_3.id,
        }
        self.assertEqual(SupportRelease.objects.count(), 1)
        self.assertEqual(SupportEvent.objects.count(), 1)
        response = self.client.post(reverse(self.url), follow=True, data=data)
        self.assertIn(
            f'1 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )

        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/',
            response.rendered_content,
        )
        self.assertInHTML(
            '<td class="field-get_assignee">-</td>', response.rendered_content, 2
        )
        self.assertInHTML(
            f'<td class="field-get_assignee">{self.admin}</td>',
            response.rendered_content,
        )

        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            3,
        )
        self.assertEqual(SupportRelease.objects.count(), 1)
        self.assertEqual(SupportEvent.objects.count(), 2)

    def test_assign_multiple_pro_release_to_me(self):
        data = {
            'csrfmiddlewaretoken': 'H3Z2pQPvj8ihzKVC5JY0QA10UgnuZCjXmVhExMpzZY7k',
            'action': 'assign_to_me',
            '_selected_action': [self.release_1.id, self.release_2.id],
        }
        self.assertEqual(SupportRelease.objects.count(), 1)
        self.assertEqual(SupportEvent.objects.count(), 1)
        response = self.client.post(reverse(self.url), follow=True, data=data)
        self.assertIn(
            f'3 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_assignee">{self.content_ops_agent}</td>',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_assignee">{self.admin}</td>',
            response.rendered_content,
            2,
        )

        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            3,
        )
        self.assertEqual(SupportRelease.objects.count(), 3)
        self.assertEqual(SupportEvent.objects.count(), 3)

    def test_re_assign_all_pro_release_to_me(self):
        data = {
            'csrfmiddlewaretoken': 'H3Z2pQPvj8ihzKVC5JY0QA10UgnuZCjXmVhExMpzZY7k',
            'action': 'assign_to_me',
            '_selected_action': [
                self.release_1.id,
                self.release_2.id,
                self.release_3.id,
            ],
        }
        SupportReleaseFactory(release=self.release_2, assignee=self.content_ops_agent)
        SupportEventFactory(
            event=SupportEvent.ASSIGNED,
            release=self.release_2,
            user=self.content_ops_agent,
        )
        self.assertEqual(SupportRelease.objects.count(), 2)
        self.assertEqual(SupportEvent.objects.count(), 2)
        response = self.client.post(reverse(self.url), follow=True, data=data)
        self.assertIn(
            f'3 {"pro" if self.is_pro else "free"} releases', response.rendered_content
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_1.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_2.id}/change/',
            response.rendered_content,
        )
        self.assertIn(
            f'/admin/contenttollgate/{"pro" if self.is_pro else "free"}release/'
            f'{self.release_3.id}/change/',
            response.rendered_content,
        )
        self.assertInHTML(
            f'<td class="field-get_assignee">{self.admin}</td>',
            response.rendered_content,
            3,
        )

        self.assertInHTML(
            f'<td class="field-get_subscription_tier">{"Amuse PRO subscription tier" if self.is_pro else "Free Tier"}</td>',
            response.rendered_content,
            3,
        )
        self.assertEqual(SupportRelease.objects.count(), 3)
        self.assertEqual(SupportEvent.objects.count(), 5)


class ProReleaseAssignToMeActionTest(ReleaseAssignToMeActionTest, TestCase):
    url = 'admin:contenttollgate_prorelease_changelist'
    is_pro = True

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        SubscriptionFactory(user=cls.user_1, valid_from=date(2020, 1, 10))


class ProReleaseAssignToMeActionTest(ReleaseAssignToMeActionTest, TestCase):
    url = 'admin:contenttollgate_freerelease_changelist'
    is_pro = False


class ReleaseViewAdminTest(TestCase):
    @patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        self.client.force_login(user=self.user)
        self.artist_1 = Artistv2Factory()
        UserArtistRoleFactory(user=self.user, artist=self.artist_1)

        self.artist_2 = Artistv2Factory()
        self.release = ReleaseFactory(user=self.user, status=Release.STATUS_PENDING)
        ReleaseArtistRoleFactory(
            release=self.release, artist=self.artist_2, main_primary_artist=True
        )
        self.song_1 = SongFactory(release=self.release)
        SongArtistRoleFactory(song=self.song_1, artist=self.artist_2)
        self.song_2 = SongFactory(release=self.release)
        SongArtistRoleFactory(song=self.song_2, artist=self.artist_2)

        self.stores = []
        self.stores.append(StoreFactory(name='spotify'))
        self.stores.append(StoreFactory(name='apple_music'))
        self.stores.append(StoreFactory(name='audiomack'))

    @patch('releases.models.release.Release.has_licensed_tracks', return_value=True)
    def test_page_shows_release_metadata(self, mocked_response):
        url = reverse(
            'admin:contenttollgate_genericrelease_view', args=[self.song_1.release.id]
        )
        response = self.client.get(url)

        self.assertIn(self.release.name, response.rendered_content)
        self.assertIn(self.release.upc.code, response.rendered_content)
        self.assertIn(self.release.label, response.rendered_content)
        self.assertIn(self.artist_2.name, response.rendered_content)
        self.assertIn(self.song_1.name, response.rendered_content)
        self.assertIn(self.song_1.isrc.code, response.rendered_content)
        self.assertIn(self.song_2.name, response.rendered_content)
        self.assertIn(self.song_2.isrc.code, response.rendered_content)
        for store in self.stores:
            self.assertIn(store.name, response.rendered_content)
