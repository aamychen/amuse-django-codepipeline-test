from django.conf import settings

from amuse.vendor.customerio import default as cio
from amuse.vendor.rebrandly import Rebrandly
from users.models import UserArtistRole
from datetime import datetime


class CustomerIOEvents:
    def __init__(self):
        self.rebrandly = Rebrandly()
        team_invite_events = dict()
        team_invite_events[UserArtistRole.ADMIN] = 'email_invite_team_admin'
        team_invite_events[UserArtistRole.MEMBER] = 'email_invite_team_member'
        team_invite_events[UserArtistRole.SPECTATOR] = 'email_invite_team_spect'

        self.team_invite_events = team_invite_events
        self.royalty_invite_event_email = 'email_royalty_invite'
        self.royalty_invite_event_sms = 'sms_royalty_invite'
        self.royalty_invite_event_email_released = 'email_royalty_invite_released'
        self.royalty_invite_event_sms_released = 'sms_royalty_invite_released'
        self.royalty_new_split_existing_user = 'email_new_split_existing_user'
        self.royalty_new_split_existing_user_sms = 'sms_new_split_existing_user'
        self.royalty_new_split_existing_user_released = (
            'email_new_split_existing_user_released'
        )
        self.royalty_new_split_existing_user_sms_released = (
            'sms_new_split_existing_user_released'
        )

        self.royalty_split_release_owner_notification = (
            'email_split_release_owner_notification'
        )
        self.song_artist_invite_event_email = 'email_song_artist_invite'
        self.song_artist_invite_event_sms = 'sms_song_artist_invite'
        self.team_invite_event_sms = 'tna_invite_sms'

        self.team_role_changed_by_admin_self = 'tna_permch_byadmin_self'
        self.team_role_changed_by_owner = 'tna_permch_byowner'
        self.team_role_changed_by_admin = 'tna_permch_byadmin'

        self.team_role_removed_by_self = 'tna_remove_byself'
        self.team_role_removed_by_owner = 'tna_remove_byowner'
        self.team_role_removed_by_admin = 'tna_remove_byadmin'

        self.send_email_split_not_accepted_3_days = 'email_split_not_accepted_3_days'
        self.send_sms_split_not_accepted_3_days = 'sms_split_not_accepted_3_days'

        self.send_royalty_split_not_accepted_day_before_release = (
            'royalty_split_not_accepted_day_before_release'
        )
        self.send_sms_split_not_accepted_day_before_release = (
            'sms_split_not_accepted_day_before_release'
        )
        self.send_user_email_first_time_cid_use = 'email_user_first_time_cid_use'

    def get_team_invite_event(self, user_artist_role):
        return self.team_invite_events[user_artist_role]

    def generate_royalty_invite_confirm_url(self, token):
        return f"{settings.WRB_URL.rstrip('/')}/invitations/royalty/confirm/{token}"

    def get_team_role_changed_event(self, is_removed, is_self, is_by_owner):
        def removed(is_self_removed, is_removed_by_owner):
            event_name = self.team_role_removed_by_admin
            if is_self_removed:
                event_name = self.team_role_removed_by_self
            elif is_removed_by_owner:
                event_name = self.team_role_removed_by_owner

            return event_name

        def updated(is_self_updated, is_updated_by_owner):
            event_name = self.team_role_changed_by_admin
            if is_self_updated:
                event_name = self.team_role_changed_by_admin_self
            elif is_updated_by_owner:
                event_name = self.team_role_changed_by_owner

            return event_name

        return (
            removed(is_self, is_by_owner)
            if is_removed
            else updated(is_self, is_by_owner)
        )

    def send_royalty_invite(self, email, phone, data):
        url = self.generate_royalty_invite_confirm_url(data['token'])

        release_date_in_past = data['release_date'] <= datetime.now().date()
        email_event = (
            self.royalty_invite_event_email_released
            if release_date_in_past
            else self.royalty_invite_event_email
        )
        phone_event = (
            self.royalty_invite_event_sms_released
            if release_date_in_past
            else self.royalty_invite_event_sms
        )

        release_date = data['release_date'].isoformat()
        if email is not None:
            cio().track_anonymous(
                name=email_event,
                recipient=email,
                invitee_name=data['invitee_name'],
                sender_first_name=data['inviter_first_name'],
                sender_last_name=data['inviter_last_name'],
                song_name=data['song_name'],
                release_date=release_date,
                royalty_rate=data['royalty_rate'],
                url=url,
            )

        if phone is not None:
            url = self.rebrandly.generate_link(url)
            cio().track_anonymous(
                name=phone_event,
                recipient=phone,
                invitee_name=data['invitee_name'],
                sender_first_name=data['inviter_first_name'],
                sender_last_name=data['inviter_last_name'],
                song_name=data['song_name'],
                release_date=release_date,
                royalty_rate=data['royalty_rate'],
                url=url,
            )

    def send_royalty_assigned_to_existing_user(self, user_id, phone_number, data):
        url = self.generate_royalty_invite_confirm_url(data['token'])

        release_date_in_past = data['release_date'] <= datetime.now().date()
        email_event = (
            self.royalty_new_split_existing_user_released
            if release_date_in_past
            else self.royalty_new_split_existing_user
        )
        phone_event = (
            self.royalty_new_split_existing_user_sms_released
            if release_date_in_past
            else self.royalty_new_split_existing_user_sms
        )

        release_date = data['release_date'].isoformat()
        payload = {
            'invitee_name': data['invitee_name'],
            'sender_first_name': data['inviter_first_name'],
            'sender_last_name': data['inviter_last_name'],
            'song_name': data['song_name'],
            'release_date': release_date,
            'royalty_rate': data['royalty_rate'],
            'url': url,
        }

        cio().track(user_id, email_event, **payload)

        if phone_number:
            payload['url'] = self.rebrandly.generate_link(url)
            payload['recipient'] = phone_number
            cio().track(user_id, phone_event, **payload)

    def send_email_split_release_owner_notification(self, user_id, data):
        event = self.royalty_split_release_owner_notification

        payload = {
            'invitee_name': data['invitee_name'],
            'sender_first_name': data['inviter_first_name'],
            'sender_last_name': data['inviter_last_name'],
            'song_name': data['song_name'],
            'royalty_rate': data['royalty_rate'],
        }

        cio().track(user_id, event, **payload)

    def send_song_artist_invite(self, email, phone, data):
        url = f"{settings.WRB_URL.rstrip('/')}/invitations/songartist/confirm/{data['token']}"

        if email is not None:
            cio().track_anonymous(
                name=self.song_artist_invite_event_email,
                recipient=email,
                sender_first_name=data['sender_first_name'],
                sender_last_name=data['sender_last_name'],
                receiver_name=data['receiver_name'],
                url=url,
            )

        if phone is not None:
            url = self.rebrandly.generate_link(url)
            cio().track_anonymous(
                name=self.song_artist_invite_event_sms,
                recipient=phone,
                sender_first_name=data['sender_first_name'],
                sender_last_name=data['sender_last_name'],
                receiver_name=data['receiver_name'],
                url=url,
            )

    def send_team_invite(self, email, phone, data):
        url = f"{settings.WRB_URL.rstrip('/')}/invitations/team/confirm/{data['token']}"
        role = data['user_artist_role']

        email_args = {
            'sender_first_name': data['inviter_first_name'],
            'sender_last_name': data['inviter_last_name'],
            'receiver_first_name': data['invitee_first_name'],
            'receiver_last_name': data['invitee_last_name'],
            'artist_name': data['artist_name'],
            'permission_level': role,
            'url': url,
        }

        if email is not None:
            event = self.get_team_invite_event(role)
            cio().track_anonymous(name=event, recipient=email, **email_args)

        if phone is not None:
            email_args['url'] = self.rebrandly.generate_link(email_args['url'])
            cio().track_anonymous(
                name=self.team_invite_event_sms, recipient=phone, **email_args
            )

    def send_team_role_changed_event(self, user_id, data):
        is_self_update = data.pop('is_self_update', False)
        is_update_by_owner = data.pop('is_updated_by_owner', False)

        event = self.get_team_role_changed_event(
            False, is_self_update, is_update_by_owner
        )
        data = {
            'artist_name': data['artist_name'],
            'member_email': data['member_email'],
            'member_first_name': data['member_first_name'],
            'member_last_name': data['member_last_name'],
            'admin_first_name': data['admin_first_name'],
            'admin_last_name': data['admin_last_name'],
            'permission_level': UserArtistRole.get_name(data['role']),
            'owner_email': data['owner_email'],
            'owner_first_name': data['owner_first_name'],
            'owner_last_name': data['owner_last_name'],
        }

        cio().track(user_id, event, **data)

    def send_team_role_removed_event(self, user_id, data):
        is_self_removal = data.pop('is_self_removal', False)
        is_removed_by_owner = data.pop('is_removed_by_owner', False)

        event = self.get_team_role_changed_event(
            True, is_self_removal, is_removed_by_owner
        )

        data = {
            'artist_name': data['artist_name'],
            'member_email': data['member_email'],
            'member_first_name': data['member_first_name'],
            'member_last_name': data['member_last_name'],
            'admin_first_name': data['admin_first_name'],
            'admin_last_name': data['admin_last_name'],
            'permission_level': UserArtistRole.get_name(data['role']),
            'owner_email': data['owner_email'],
            'owner_first_name': data['owner_first_name'],
            'owner_last_name': data['owner_last_name'],
        }

        cio().track(user_id, event, **data)

    def report_duplicate_google_subscriptions(self, recipient, data):
        cio().track_anonymous(
            name='DUPLICATE_GOOGLE_SUBSCRIPTIONS', recipient=recipient, data=data
        )

    def send_split_3_day_reminder(self, inputdata):
        url = self.generate_royalty_invite_confirm_url(inputdata.token)

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

        if inputdata.recipient is not None:
            cio().track_anonymous(
                name=self.send_email_split_not_accepted_3_days, **data
            )

        if inputdata.phone_number is not None:
            data['url'] = self.rebrandly.generate_link(url)
            data['recipient'] = inputdata.phone_number
            cio().track_anonymous(name=self.send_sms_split_not_accepted_3_days, **data)

    def send_day_before_release_reminder(self, inputdata):
        url = self.generate_royalty_invite_confirm_url(inputdata.token)

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

        if inputdata.recipient is not None:
            cio().track_anonymous(
                name=self.send_royalty_split_not_accepted_day_before_release, **data
            )

        if inputdata.phone_number is not None:
            data['url'] = self.rebrandly.generate_link(url)
            data['recipient'] = inputdata.phone_number
            cio().track_anonymous(
                name=self.send_sms_split_not_accepted_day_before_release, **data
            )

    def user_updated_firebase_token(self, user, platform, token):
        cio().add_device(user.id, token, platform)

    def send_email_first_time_cid_use(self, user_id, data):
        event = self.send_user_email_first_time_cid_use

        payload = {
            'recipient': data['email'],
            'receiver_first_name': data['receiver_first_name'],
            'receiver_last_name': data['receiver_last_name'],
        }

        cio().track(user_id, event, **payload)


def default():
    return CustomerIOEvents()
