from datetime import date, datetime, timedelta
from unittest import mock

import responses
from django.conf import settings
from django.test import TestCase
from requests import Session

from amuse.vendor.customerio import CustomerIO, events
from amuse.vendor.rebrandly import Rebrandly
from users.models import UserArtistRole as UAR


class MockResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.content = "Mock data"
        self.text = "123"


class MockInput(object):
    def __init__(self, data):
        self.data = data
        for k, v in self.data.items():
            setattr(self, k, v)


REBRANDLY_SHORT_LINK = 'https://rebrand.ly/FAKE'


class TestEvents(TestCase):
    def setUp(self):
        self.cioevents = events.default
        self.cio = CustomerIO(
            site_id='siteid', api_key='apikey', host="host", port=3210, retries=5
        )

        release_date = datetime.now().date() + timedelta(days=20)
        self.data = {
            'invitee_id': 2,
            'invitee_name': 'bunny',
            'inviter_first_name': 'donald',
            'inviter_id': 3,
            'inviter_last_name': 'duck',
            'release_date': release_date,
            'royalty_rate': '23.45%',
            'song_name': 'song awesome',
            'token': '123',
        }
        self.event_data = {
            'invitee_name': 'bunny',
            'release_date': release_date.isoformat(),
            'royalty_rate': '23.45%',
            'sender_first_name': 'donald',
            'sender_last_name': 'duck',
            'song_name': 'song awesome',
        }

        # do not verify the ssl certificate as it is self signed
        # should only be done for tests
        self.cio.http.verify = False

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_royalty_invite_called_twice(self, mockdata):
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_royalty_invite('aaa@example.com', '+1234', self.data)

        self.assertEqual(track_anonymous.call_count, 2)

    @mock.patch.object(Rebrandly, 'generate_link', return_value=REBRANDLY_SHORT_LINK)
    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_royalty_invite_sms(self, mockdata, mock_rebrandly):
        recipient = '+1234'
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_royalty_invite(None, recipient, self.data)

        url = REBRANDLY_SHORT_LINK
        track_anonymous.assert_called_with(
            name='sms_royalty_invite', recipient=recipient, url=url, **self.event_data
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Rebrandly, 'generate_link', return_value=REBRANDLY_SHORT_LINK)
    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_royalty_invite_sms_released(self, mockdata, mock_rebrandly):
        recipient = '+1234'

        self.data['release_date'] = datetime.now().date() - timedelta(days=3)
        self.event_data['release_date'] = self.data['release_date'].isoformat()

        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_royalty_invite(None, recipient, self.data)

        url = REBRANDLY_SHORT_LINK
        track_anonymous.assert_called_with(
            name='sms_royalty_invite_released',
            recipient=recipient,
            url=url,
            **self.event_data,
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_royalty_invite_email(self, mockdata):
        recipient = 'aaa@example.com'
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_royalty_invite(recipient, None, self.data)

        url = f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/123"

        track_anonymous.assert_called_with(
            name='email_royalty_invite', recipient=recipient, url=url, **self.event_data
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @responses.activate
    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    def test_send_royalty_invite_email_released(self, mockdata):
        mockdata.return_value = None
        recipient = 'aaa@example.com'

        self.data['release_date'] = datetime.now().date() - timedelta(days=3)
        self.event_data['release_date'] = self.data['release_date'].isoformat()

        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_royalty_invite(recipient, None, self.data)

        url = f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/123"

        track_anonymous.assert_called_with(
            name='email_royalty_invite_released',
            recipient=recipient,
            url=url,
            **self.event_data,
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @responses.activate
    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @mock.patch.object(CustomerIO, 'track_anonymous')
    @mock.patch.object(CustomerIO, 'track')
    def test_send_royalty_assigned_to_existing_user(
        self, mock_track, mock_track_anonymous, mockdata
    ):
        release_date = datetime.now().date() + timedelta(days=3)
        data = {
            'member_email': 'member@example.com',
            'inviter_first_name': 'Memo',
            'inviter_last_name': 'Memov',
            'invitee_name': 'Doc',
            'song_name': 'Song abc',
            'royalty_rate': '20.00%',
            'release_date': release_date,
            'token': 'tokenxyz',
        }

        user_id = 123
        self.cioevents().send_royalty_assigned_to_existing_user(user_id, None, data)

        self.assertEqual(0, mock_track_anonymous.call_count)
        mock_track.assert_called_once_with(
            user_id,
            'email_new_split_existing_user',
            invitee_name='Doc',
            sender_first_name='Memo',
            sender_last_name='Memov',
            song_name='Song abc',
            release_date=release_date.isoformat(),
            royalty_rate='20.00%',
            url=f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/tokenxyz",
        )

    @responses.activate
    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @mock.patch.object(CustomerIO, 'track_anonymous')
    @mock.patch.object(CustomerIO, 'track')
    def test_send_royalty_assigned_to_existing_user_released(
        self, mock_track, mock_track_anonymous, mockdata
    ):
        release_date = datetime.now().date() - timedelta(days=3)
        data = {
            'member_email': 'member@example.com',
            'inviter_first_name': 'Memo',
            'inviter_last_name': 'Memov',
            'invitee_name': 'Doc',
            'song_name': 'Song abc',
            'royalty_rate': '20.00%',
            'release_date': release_date,
            'token': 'tokenxyz',
        }

        user_id = 123
        self.cioevents().send_royalty_assigned_to_existing_user(user_id, None, data)

        self.assertEqual(0, mock_track_anonymous.call_count)
        mock_track.assert_called_once_with(
            user_id,
            'email_new_split_existing_user_released',
            invitee_name='Doc',
            sender_first_name='Memo',
            sender_last_name='Memov',
            song_name='Song abc',
            release_date=release_date.isoformat(),
            royalty_rate='20.00%',
            url=f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/tokenxyz",
        )

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_royalty_assigned_to_existing_user_with_phone(self, mockdata):
        user_id = 123
        phone = '+123-456-789'
        release_date = datetime.now().date() + timedelta(days=3)
        data = {
            'member_email': 'member@example.com',
            'inviter_first_name': 'Memo',
            'inviter_last_name': 'Memov',
            'invitee_name': 'Doc',
            'song_name': 'Song abc',
            'release_date': release_date,
            'royalty_rate': '20.00%',
            'token': 'token-xyz',
        }

        with mock.patch.object(CustomerIO, 'track') as track:
            self.cioevents().send_royalty_assigned_to_existing_user(
                user_id, phone, data
            )

        calls = [
            mock.call(
                user_id,
                'email_new_split_existing_user',
                invitee_name='Doc',
                sender_first_name='Memo',
                sender_last_name='Memov',
                song_name='Song abc',
                release_date=release_date.isoformat(),
                royalty_rate='20.00%',
                url=f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/token-xyz",
            ),
            mock.call(
                user_id,
                'sms_new_split_existing_user',
                invitee_name='Doc',
                sender_first_name='Memo',
                sender_last_name='Memov',
                song_name='Song abc',
                release_date=release_date.isoformat(),
                royalty_rate='20.00%',
                recipient=phone,
                url=f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/token-xyz",
            ),
        ]

        track.assert_has_calls(calls)
        self.assertEqual(2, track.call_count)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_royalty_assigned_to_existing_user_released_with_phone(self, mockdata):
        user_id = 123
        phone = '+123-456-789'
        release_date = datetime.now().date() - timedelta(days=3)
        data = {
            'member_email': 'member@example.com',
            'inviter_first_name': 'Memo',
            'inviter_last_name': 'Memov',
            'invitee_name': 'Doc',
            'song_name': 'Song abc',
            'release_date': release_date,
            'royalty_rate': '20.00%',
            'token': 'token-xyz',
        }

        with mock.patch.object(CustomerIO, 'track') as track:
            self.cioevents().send_royalty_assigned_to_existing_user(
                user_id, phone, data
            )

        calls = [
            mock.call(
                user_id,
                'email_new_split_existing_user_released',
                invitee_name='Doc',
                sender_first_name='Memo',
                sender_last_name='Memov',
                song_name='Song abc',
                release_date=release_date.isoformat(),
                royalty_rate='20.00%',
                url=f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/token-xyz",
            ),
            mock.call(
                user_id,
                'sms_new_split_existing_user_released',
                invitee_name='Doc',
                sender_first_name='Memo',
                sender_last_name='Memov',
                song_name='Song abc',
                release_date=release_date.isoformat(),
                royalty_rate='20.00%',
                recipient=phone,
                url=f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/token-xyz",
            ),
        ]

        track.assert_has_calls(calls)
        self.assertEqual(2, track.call_count)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_email_split_release_owner_notification(self, mockdata):
        data = {
            'member_email': 'member@example.com',
            'inviter_first_name': 'Memo',
            'inviter_last_name': 'Memov',
            'invitee_name': 'Doc',
            'song_name': 'Song abc',
            'royalty_rate': '20.00%',
        }

        user_id = 123
        with mock.patch.object(CustomerIO, 'track') as track:
            self.cioevents().send_email_split_release_owner_notification(user_id, data)

        track.assert_called_once_with(
            user_id,
            'email_split_release_owner_notification',
            invitee_name='Doc',
            sender_first_name='Memo',
            sender_last_name='Memov',
            song_name='Song abc',
            royalty_rate='20.00%',
        )

    def test_get_team_invite_event(self):
        class Case:
            def __init__(self, expected, role):
                self.expected = expected
                self.role = role

        d = [
            Case('email_invite_team_admin', UAR.ADMIN),
            Case('email_invite_team_member', UAR.MEMBER),
            Case('email_invite_team_spect', UAR.SPECTATOR),
        ]

        for v in d:
            f = self.cioevents()
            actual = f.get_team_invite_event(user_artist_role=v.role)
            self.assertEqual(
                v.expected, actual, f'test failed for test case: role={v.role}'
            )

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_team_invite_email(self, mockdata):
        data = {
            'invitee_first_name': 'bugs',
            'invitee_last_name': 'bunny',
            'inviter_first_name': 'duffy',
            'inviter_last_name': 'duck',
            'user_artist_role': UAR.MEMBER,
            'artist_name': 'susi',
            'token': '123',
        }

        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_team_invite('aaa@example.com', None, data)

        url = f"{settings.WRB_URL.rstrip('/')}/invitations/team/confirm/123"
        track_anonymous.assert_called_with(
            name='email_invite_team_member',
            recipient='aaa@example.com',
            artist_name='susi',
            permission_level=UAR.MEMBER,
            receiver_first_name='bugs',
            receiver_last_name='bunny',
            sender_first_name='duffy',
            sender_last_name='duck',
            url=url,
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Rebrandly, 'generate_link', return_value=REBRANDLY_SHORT_LINK)
    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_team_invite_sms(self, mockdata, mock_rebrandly):
        data = {
            'invitee_first_name': 'bugs',
            'invitee_last_name': 'bunny',
            'inviter_first_name': 'duffy',
            'inviter_last_name': 'duck',
            'user_artist_role': UAR.MEMBER,
            'artist_name': 'susi',
            'token': '123',
        }

        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_team_invite(None, '+1234', data)

        url = REBRANDLY_SHORT_LINK
        track_anonymous.assert_called_with(
            name='tna_invite_sms',
            recipient='+1234',
            artist_name='susi',
            permission_level=UAR.MEMBER,
            receiver_first_name='bugs',
            receiver_last_name='bunny',
            sender_first_name='duffy',
            sender_last_name='duck',
            url=url,
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_team_invite_sms_email(self, mockdata):
        data = {
            'invitee_first_name': 'bugs',
            'invitee_last_name': 'bunny',
            'inviter_first_name': 'duffy',
            'inviter_last_name': 'duck',
            'user_artist_role': UAR.MEMBER,
            'artist_name': 'susi',
            'token': '123',
        }

        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_team_invite("aaaa@example.com", '+1234', data)

        self.assertEqual(track_anonymous.call_count, 2)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_song_arist_invite(self, mockdata):
        data = {
            'sender_first_name': 'bugs',
            'sender_last_name': 'bunny',
            'inviter_first_name': 'duffy',
            'inviter_last_name': 'duck',
            'receiver_name': 'InviteMe',
            'token': 'qwe1234',
            'url': 'url',
        }

        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_song_artist_invite("aaaa@example.com", '+1234', data)

        self.assertEqual(track_anonymous.call_count, 2)

    @responses.activate
    def test_get_team_role_changed_event(self):
        class Case:
            def __init__(self, event, is_removed, is_self, is_by_owner):
                self.expected = event
                self.is_removed = is_removed
                self.is_self = is_self
                self.is_by_owner = is_by_owner

        cases = [
            Case('tna_permch_byadmin_self', False, True, False),
            Case('tna_permch_byadmin_self', False, True, True),
            Case('tna_permch_byowner', False, False, True),
            Case('tna_permch_byadmin', False, False, False),
            Case('tna_remove_byself', True, True, False),
            Case('tna_remove_byself', True, True, True),
            Case('tna_remove_byowner', True, False, True),
            Case('tna_remove_byadmin', True, False, False),
        ]

        for v in cases:
            actual = self.cioevents().get_team_role_changed_event(
                v.is_removed, v.is_self, v.is_by_owner
            )

            self.assertEqual(
                v.expected,
                actual,
                f'test failed for test case: is_removed={v.is_removed} is_self={v.is_self} is_by_owner={v.is_by_owner}',
            )

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_team_role_changed_event(self, mockdata):
        data = {
            'artist_name': 'Donald The Artist',
            'member_email': 'member@example.com',
            'member_first_name': 'Memo',
            'member_last_name': 'Memov',
            'admin_first_name': 'Adm',
            'admin_last_name': 'Adminov',
            'role': 1,
            'owner_email': 'owner@example.com',
            'owner_first_name': 'Owl',
            'owner_last_name': 'Owlow',
            'is_self_update': False,
            'is_updated_by_owner': True,
        }

        user_id = 123
        with mock.patch.object(CustomerIO, 'track') as track:
            self.cioevents().send_team_role_changed_event(user_id, data)

        track.assert_called_once_with(
            user_id,
            'tna_permch_byowner',
            admin_first_name='Adm',
            admin_last_name='Adminov',
            artist_name='Donald The Artist',
            member_email='member@example.com',
            member_first_name='Memo',
            member_last_name='Memov',
            owner_email='owner@example.com',
            owner_first_name='Owl',
            owner_last_name='Owlow',
            permission_level='admin',
        )

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_team_role_removed_event(self, mockdata):
        data = {
            'artist_name': 'Donald The Artist',
            'member_email': 'member@example.com',
            'member_first_name': 'Memo',
            'member_last_name': 'Memov',
            'admin_first_name': 'Adm',
            'admin_last_name': 'Adminov',
            'role': 1,
            'owner_email': 'owner@example.com',
            'owner_first_name': 'Owl',
            'owner_last_name': 'Owlow',
            'is_self_removal': True,
            'is_removed_by_owner': False,
        }

        user_id = 123
        with mock.patch.object(CustomerIO, 'track') as track:
            self.cioevents().send_team_role_removed_event(user_id, data)

        track.assert_called_once_with(
            user_id,
            'tna_remove_byself',
            admin_first_name='Adm',
            admin_last_name='Adminov',
            artist_name='Donald The Artist',
            member_email='member@example.com',
            member_first_name='Memo',
            member_last_name='Memov',
            owner_email='owner@example.com',
            owner_first_name='Owl',
            owner_last_name='Owlow',
            permission_level='admin',
        )

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_split_3_day_reminder_email(self, mockdata):
        mocked_data = {
            "invitee_name": "Spliter",
            "recipient": "email@example.com",
            "phone_number": None,
            "rate": 0.3,
            "first_name": "Split",
            "last_name": "Sender",
            "song_name": "Best song in the world",
            "release_date": date(2020, 3, 3),
            "token": "1234555asdsdf",
        }
        inputdata = MockInput(data=mocked_data)
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_split_3_day_reminder(inputdata=inputdata)

        url = self.cioevents().generate_royalty_invite_confirm_url(inputdata.token)

        data = {
            "invitee_name": inputdata.invitee_name,
            "recipient": inputdata.recipient,
            "royalty_rate": f'{float(inputdata.rate):.2%}',
            "sender_first_name": inputdata.first_name,
            "sender_last_name": inputdata.last_name,
            "song_name": inputdata.song_name,
            "release_date": str(inputdata.release_date),
            "url": url,
        }

        track_anonymous.assert_called_with(
            name='email_split_not_accepted_3_days', **data
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_split_3_day_reminder_sms(self, mockdata):
        mocked_data = {
            "invitee_name": "Spliter",
            "recipient": None,
            "phone_number": '+3984334333',
            "rate": 0.3,
            "first_name": "Split",
            "last_name": "Sender",
            "song_name": "Best song in the world",
            "release_date": date(2020, 3, 3),
            "token": "1234555asdsdf",
        }
        inputdata = MockInput(data=mocked_data)
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_split_3_day_reminder(inputdata=inputdata)

        url = self.cioevents().generate_royalty_invite_confirm_url(inputdata.token)

        data_sms = {
            "invitee_name": inputdata.invitee_name,
            "recipient": inputdata.phone_number,
            "royalty_rate": f'{float(inputdata.rate):.2%}',
            "sender_first_name": inputdata.first_name,
            "sender_last_name": inputdata.last_name,
            "song_name": inputdata.song_name,
            "release_date": str(inputdata.release_date),
            "url": self.cioevents().rebrandly.generate_link(url),
        }

        track_anonymous.assert_called_with(
            name='sms_split_not_accepted_3_days', **data_sms
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_day_before_release_reminder_email(self, mockdata):
        mocked_data = {
            "invitee_name": "Spliter",
            "recipient": "email@example.com",
            "phone_number": None,
            "rate": 0.3,
            "first_name": "Split",
            "last_name": "Sender",
            "song_name": "Best song in the world",
            "release_date": date(2020, 3, 3),
            "token": "1234555asdsdf",
        }
        inputdata = MockInput(data=mocked_data)
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_day_before_release_reminder(inputdata=inputdata)

        url = self.cioevents().generate_royalty_invite_confirm_url(inputdata.token)

        data = {
            "invitee_name": inputdata.invitee_name,
            "recipient": inputdata.recipient,
            "royalty_rate": f'{float(inputdata.rate):.2%}',
            "sender_first_name": inputdata.first_name,
            "sender_last_name": inputdata.last_name,
            "song_name": inputdata.song_name,
            "release_date": str(inputdata.release_date),
            "url": url,
        }

        track_anonymous.assert_called_with(
            name='royalty_split_not_accepted_day_before_release', **data
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_send_day_before_release_reminder_sms(self, mockdata):
        mocked_data = {
            "invitee_name": "Spliter",
            "recipient": None,
            "phone_number": "+38722222",
            "rate": 0.3,
            "first_name": "Split",
            "last_name": "Sender",
            "song_name": "Best song in the world",
            "release_date": date(2020, 3, 3),
            "token": "1234555asdsdf",
        }
        inputdata = MockInput(data=mocked_data)
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().send_day_before_release_reminder(inputdata=inputdata)

        url = self.cioevents().generate_royalty_invite_confirm_url(inputdata.token)

        data = {
            "invitee_name": inputdata.invitee_name,
            "recipient": inputdata.phone_number,
            "royalty_rate": f'{float(inputdata.rate):.2%}',
            "sender_first_name": inputdata.first_name,
            "sender_last_name": inputdata.last_name,
            "song_name": inputdata.song_name,
            "release_date": str(inputdata.release_date),
            "url": url,
        }

        track_anonymous.assert_called_with(
            name='sms_split_not_accepted_day_before_release', **data
        )

        self.assertEqual(track_anonymous.call_count, 1)

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_user_updated_firebase_token(self, mockdata):
        user = mock.Mock(id=123)
        with mock.patch.object(CustomerIO, "add_device") as add_device:
            self.cioevents().user_updated_firebase_token(user, "ios", "test123")
            add_device.assert_called_once_with(123, "test123", "ios")

    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @responses.activate
    def test_report_duplicate_google_subscriptions(self, mockdata):
        payload = {'subscriptions': []}
        with mock.patch.object(CustomerIO, 'track_anonymous') as track_anonymous:
            self.cioevents().report_duplicate_google_subscriptions(
                recipient='a@a.a', data=payload
            )
            track_anonymous.assert_called_with(
                name='DUPLICATE_GOOGLE_SUBSCRIPTIONS', recipient='a@a.a', data=payload
            )

            self.assertEqual(track_anonymous.call_count, 1)

    @responses.activate
    @mock.patch.object(Session, 'send', return_value=MockResponse(status_code=200))
    @mock.patch.object(CustomerIO, 'track')
    def test_send_email_first_time_cid_use(self, mock_track, mock_data):
        data = {
            'email': 'john.doe234234@example.com',
            'receiver_first_name': 'John',
            'receiver_last_name': 'Doe',
        }
        user_id = 123

        self.cioevents().send_email_first_time_cid_use(user_id, data)

        mock_track.assert_called_once_with(
            user_id,
            'email_user_first_time_cid_use',
            recipient='john.doe234234@example.com',
            receiver_first_name='John',
            receiver_last_name='Doe',
        )
