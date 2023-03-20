from unittest import mock

from django.contrib.admin.models import LogEntry
from django.forms import ModelForm
from django.forms import modelformset_factory
from django.test import TestCase

from amuse.models.support import SupportEvent
from amuse.tests.factories import ACRCloudMatchFactory, SupportReleaseFactory
from contenttollgate.forms import ReleaseForm, CommentsForm
from contenttollgate.utils import (
    show_audio_recognition_warning,
    trigger_release_updated_events,
    calculate_next_release,
    write_release_history_log,
)
from releases.models import Comments
from releases.models import Release, Song
from releases.tests.factories import (
    SongFactory,
    SongArtistRoleFactory,
    ReleaseFactory,
    ReleaseArtistRoleFactory,
    GenreFactory,
)
from releases.utils import ordered_stores_queryset
from users.tests.factories import Artistv2Factory, UserFactory


class ShowAudioRecognitionWarningTestCase(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
    def setUp(self, _):
        self.song = SongFactory()

    def test_no_matches(self):
        result = show_audio_recognition_warning(self.song)
        assert result is False

    def test_full_match(self):
        ACRCloudMatchFactory(score=100, song=self.song)

        result = show_audio_recognition_warning(self.song)
        assert result is True

    def test_matching_song_name_different_isrc(self):
        ACRCloudMatchFactory(song=self.song, track_title=self.song.name)

        result = show_audio_recognition_warning(self.song)
        assert result is True

    @mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
    def test_matching_artist_name_different_isrc(self, _):
        song_artist = SongArtistRoleFactory(song=self.song)
        ACRCloudMatchFactory(song=self.song, artist_name=song_artist.artist.name)

        result = show_audio_recognition_warning(self.song)
        assert result is True


class TriggerReleaseUpdatedEvents(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
    def setUp(self, _):
        self.release = ReleaseFactory(status=Release.STATUS_APPROVED)
        self.user = UserFactory(is_staff=True)
        self.support_release = SupportReleaseFactory(
            assignee=self.user, release=self.release, prepared=True
        )

    def test_support_event_created_when_transitions_to_prepared(self):
        initial_prepared_status = False
        trigger_release_updated_events(
            self.release,
            Release.STATUS_PENDING,
            self.support_release,
            initial_prepared_status,
            self.user,
        )

        assert SupportEvent.objects.get(
            event=SupportEvent.PREPARED, release=self.release, user=self.user
        )

    def test_no_support_event_created_when_already_prepared(self):
        initial_prepared_status = True
        trigger_release_updated_events(
            self.release,
            Release.STATUS_PENDING,
            self.support_release,
            initial_prepared_status,
            self.user,
        )

        events = SupportEvent.objects.filter(
            event=SupportEvent.PREPARED, release=self.release, user=self.user
        )
        assert len(events) == 0

    @mock.patch('contenttollgate.utils.send_release_lifecycle_segment_event')
    def test_if_release_status_changes_send_segment_event(self, mock_trigger):
        trigger_release_updated_events(
            self.release, Release.STATUS_PENDING, self.support_release, False, self.user
        )
        mock_trigger.assert_called_once_with(self.release)

    def test_support_event_created_when_release_transitions_from_pending_to_approved(
        self,
    ):
        initial_release_status = Release.STATUS_PENDING
        trigger_release_updated_events(
            self.release, initial_release_status, self.support_release, False, self.user
        )

        assert SupportEvent.objects.get(
            event=SupportEvent.APPROVED, release=self.release, user=self.user
        )

    def test_support_event_created_when_release_transitions_from_pending_to_not_approved(
        self,
    ):
        initial_release_status = Release.STATUS_PENDING
        self.release.status = Release.STATUS_NOT_APPROVED
        trigger_release_updated_events(
            self.release, initial_release_status, self.support_release, False, self.user
        )

        assert SupportEvent.objects.get(
            event=SupportEvent.REJECTED, release=self.release, user=self.user
        )

    @mock.patch('contenttollgate.utils.send_royalty_invitations')
    @mock.patch('contenttollgate.utils.send_song_artist_invitations')
    def test_send_invites_when_release_transitions_to_approved(
        self, mock_royalty_invitation, mock_artist_invitation
    ):
        initial_release_status = Release.STATUS_PENDING
        trigger_release_updated_events(
            self.release, initial_release_status, self.support_release, False, self.user
        )

        mock_royalty_invitation.assert_called_once_with(self.release.id)
        mock_artist_invitation.assert_called_once_with(self.release.id)

    @mock.patch('contenttollgate.utils.send_royalty_invitations')
    @mock.patch('contenttollgate.utils.send_song_artist_invitations')
    def test_send_invites_not_called_when_release_transitions_to_not_approved(
        self, mock_royalty_invitation, mock_artist_invitation
    ):
        initial_release_status = Release.STATUS_PENDING
        self.release.status = Release.STATUS_NOT_APPROVED
        trigger_release_updated_events(
            self.release, initial_release_status, self.support_release, False, self.user
        )

        mock_royalty_invitation.assert_not_called()
        mock_artist_invitation.assert_not_called()

    @mock.patch('contenttollgate.utils.send_royalty_invitations')
    @mock.patch('contenttollgate.utils.send_song_artist_invitations')
    def test_send_invites_not_called_when_status_does_not_change(
        self, mock_royalty_invitation, mock_artist_invitation
    ):
        initial_release_status = Release.STATUS_APPROVED
        self.release.status = Release.STATUS_APPROVED
        trigger_release_updated_events(
            self.release, initial_release_status, self.support_release, False, self.user
        )

        mock_royalty_invitation.assert_not_called()
        mock_artist_invitation.assert_not_called()


class CalculateNextRelease(TestCase):
    def test_get_next_release_when_multiple_releases(self):
        assigned_ids = [2, 4, 6]
        result = calculate_next_release(2, assigned_ids)
        assert result == 4
        result = calculate_next_release(result, assigned_ids)
        assert result == 6
        result = calculate_next_release(result, assigned_ids)
        assert result == 2

    def test_return_first_release_when_current_not_in_list(self):
        assigned_ids = [2, 3, 4]
        result = calculate_next_release(8, assigned_ids)
        assert result == 2


class MockSongForm(ModelForm):
    class Meta:
        model = Song
        fields = ("name", "sequence")


class TestWriteReleaseHistoryLog(TestCase):
    @mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
    def setUp(self, _):
        self.user = UserFactory(is_staff=True)
        self.release = ReleaseFactory(status=Release.STATUS_APPROVED)
        self.support_release = SupportReleaseFactory(
            assignee=self.user, release=self.release, prepared=True
        )
        self.genre = GenreFactory()
        self.song = SongFactory(release=self.release, genre=self.genre)
        self.artist = Artistv2Factory()
        self.release_artist_role = ReleaseArtistRoleFactory(
            artist=self.artist, release=self.release
        )

    @mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
    def test_writes_history_log_correctly(self, _):
        comment_text = "this is a test comment!"
        self.release.comments = Comments(release=self.release, text=comment_text)

        release_form = ReleaseForm(
            instance=self.release, stores_queryset=ordered_stores_queryset()
        )
        comments_form = CommentsForm(
            instance=self.release.comments, initial={"release": self.release}
        )
        SongFormSet = modelformset_factory(Song, form=MockSongForm, extra=0)

        mock_formset_data = {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '0',
            'form-0-name': self.song.name,
            'form-0-sequence': self.song.sequence,
        }
        song_formset = SongFormSet(mock_formset_data, queryset=self.release.songs.all())
        song_formset.save(commit=False)
        forms = [release_form, comments_form]
        formsets = [song_formset]

        write_release_history_log(self.user.id, self.release, forms, formsets)

        assert len(LogEntry.objects.all()) == 1

        log_entry = LogEntry.objects.filter(content_type__model='release').get()

        assert log_entry.user_id == self.user.id
        assert int(log_entry.object_id) == self.release.id
        assert comment_text in log_entry.change_message
        assert self.release.name in log_entry.change_message
        assert self.song.name in log_entry.change_message
