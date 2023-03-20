from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.forms import modelformset_factory
from django.test import RequestFactory, TestCase

from amuse.tests.factories import SupportReleaseFactory
from contenttollgate.forms import SongArtistRoleForm
from releases.admin import (
    AdminRelease,
    AssigneeeRelatedOnlyFieldListFilter,
    SongArtistRolesFormSet,
    SubscriptionTierFilter,
    SubscriptionTierMapping,
)
from releases.models import Release, SongArtistRole
from releases.tests.factories import SongFactory
from users.tests.factories import Artistv2Factory, UserFactory


class AdminReleaseTest(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        self.user_1 = UserFactory(is_staff=True)
        self.user_2 = UserFactory(is_staff=False)
        self.user_3 = UserFactory(is_staff=True)
        self.client.force_login(user=self.user_1)
        self.support_release_1 = SupportReleaseFactory(assignee=self.user_1)
        self.support_release_2 = SupportReleaseFactory(assignee=self.user_2)
        self.support_release_3 = SupportReleaseFactory(assignee=self.user_3)
        self.model = AdminRelease(Release, AdminSite())

    def _filterspec_get(self, changelist, request, cls):
        filters = changelist.get_filters(request)[0]
        # Step until given class is encountered or raise StopIteration if no match
        return next(f for f in set(filters) if isinstance(f, cls))

    def _request_get(self, user, params=None):
        request_factory = RequestFactory()
        request = request_factory.get('/admin', params)
        request.user = user
        return request

    def test_assignee_filter(self):
        request = self._request_get(self.user_1)
        changelist = self.model.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][2]

        assert isinstance(filterspec, AssigneeeRelatedOnlyFieldListFilter)
        assert filterspec.lookup_choices.sort(key=lambda x: x[0]) == [
            (self.user_1.pk, self.user_1.name),
            (self.user_3.pk, self.user_3.name),
        ].sort(key=lambda tup: tup[0])

    def test_subscriptiontier_tier_invalid_tier(self):
        request = self._request_get(self.user_1, params={"sub_tier": "invalid"})
        changelist = self.model.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        filterspec = self._filterspec_get(changelist, request, SubscriptionTierFilter)

        # The given queryset should be returned if sub_tier is unknown
        assert filterspec.queryset(request, queryset) == queryset

    def test_subscriptiontier_filter_free_tier(self):
        request = self._request_get(
            self.user_1, params={"sub_tier": SubscriptionTierMapping.free.name}
        )
        changelist = self.model.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        filterspec = self._filterspec_get(changelist, request, SubscriptionTierFilter)

        with mock.patch('releases.admin.queryset_annotate_free') as m:
            filterspec.queryset(request, queryset)
            m.assert_called_once()

    def test_subscriptiontier_filter_plus_tier(self):
        request = self._request_get(
            self.user_1, params={"sub_tier": SubscriptionTierMapping.plus.name}
        )
        changelist = self.model.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        filterspec = self._filterspec_get(changelist, request, SubscriptionTierFilter)

        with mock.patch('releases.admin.queryset_annotate_paid') as m:
            filterspec.queryset(request, queryset)
            m.assert_called_once()

    def test_subscriptiontier_filter_pro_tier(self):
        request = self._request_get(
            self.user_1, params={"sub_tier": SubscriptionTierMapping.pro.name}
        )
        changelist = self.model.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        filterspec = self._filterspec_get(changelist, request, SubscriptionTierFilter)

        with mock.patch('releases.admin.queryset_annotate_paid') as m:
            filterspec.queryset(request, queryset)
            m.assert_called_once()


class SongArtistRolesFormSetTest(TestCase):
    @mock.patch('amuse.tasks.zendesk_create_or_update_user')
    def setUp(self, _):
        song = SongFactory()
        artist_1 = Artistv2Factory()
        artist_2 = Artistv2Factory()
        artist_3 = Artistv2Factory()

        self.prefix = f"song_artist_role_{song.id}"
        self.data = {
            "release-status": str(Release.STATUS_APPROVED),
            f"{self.prefix}-TOTAL_FORMS": "3",
            f"{self.prefix}-INITIAL_FORMS": "0",
            f"{self.prefix}-0-id": None,
            f"{self.prefix}-0-artist": artist_1.pk,
            f"{self.prefix}-0-artist_sequence": "1",
            f"{self.prefix}-0-role": "1",
            f"{self.prefix}-0-song": song.pk,
            f"{self.prefix}-1-id": None,
            f"{self.prefix}-1-artist": artist_2.pk,
            f"{self.prefix}-1-artist_sequence": "2",
            f"{self.prefix}-1-role": "1",
            f"{self.prefix}-1-song": song.pk,
            f"{self.prefix}-2-id": None,
            f"{self.prefix}-2-artist": artist_3.pk,
            f"{self.prefix}-2-artist_sequence": "3",
            f"{self.prefix}-2-role": "2",
            f"{self.prefix}-2-song": song.pk,
        }
        self.song_artist_role_formset = modelformset_factory(
            SongArtistRole,
            form=SongArtistRoleForm,
            formset=SongArtistRolesFormSet,
            extra=0,
            can_delete=True,
        )
        self.queryset = song.songartistrole_set.all()

    def test_valid_sequence(self):
        formset = self.song_artist_role_formset(
            self.data, prefix=self.prefix, queryset=self.queryset
        )

        assert formset.is_valid()

    def test_invalid_sequence(self):
        self.data[f"{self.prefix}-1-artist_sequence"] = "99"
        formset = self.song_artist_role_formset(
            self.data, prefix=self.prefix, queryset=self.queryset
        )

        assert not formset.is_valid()
        assert formset.non_form_errors() == ['Song artist role sequence is invalid!']

    def test_deleting_triggers_invalid_sequence(self):
        self.data[f"{self.prefix}-1-DELETE"] = True
        formset = self.song_artist_role_formset(
            self.data, prefix=self.prefix, queryset=self.queryset
        )

        assert not formset.is_valid()
        assert formset.non_form_errors() == ['Song artist role sequence is invalid!']

    def test_missing_sequence(self):
        del self.data[f"{self.prefix}-1-artist_sequence"]
        formset = self.song_artist_role_formset(
            self.data, prefix=self.prefix, queryset=self.queryset
        )

        assert not formset.is_valid()
        assert formset.non_form_errors() == []
        assert formset.errors == [
            {},
            {'artist_sequence': ['This field is required.']},
            {},
        ]
