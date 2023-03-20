from django.urls import reverse_lazy as reverse
from django.utils import timezone
from rest_framework import status

from amuse.api.base.viewsets import TeamInvitationViewSet
from amuse.tokens import user_invitation_token_generator
from releases.tests.factories import SongFactory
from users.models import TeamInvitation, UserArtistRole
from users.tests.factories import UserFactory, TeamInvitationFactory, Artistv2Factory
from ..base import AmuseAPITestCase
from subscriptions.models import Subscription


class TeamInvitationAPITestCase(AmuseAPITestCase):
    def setUp(self):
        super(AmuseAPITestCase, self).setUp()
        self.user = UserFactory(artist_name='Lil Artist', is_pro=True)
        self.artist = self.user.create_artist_v2('Lil Artist')
        self.song = SongFactory()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user.auth_token.key)
        self.url = reverse('team-invitations-list')

    def test_retrieved_data(self):
        invitation = TeamInvitationFactory(
            inviter=self.user,
            artist=self.artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )

        response = self.client.get(self.url)
        retrieved_invitation = response.data[0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved_invitation["id"], invitation.id)
        self.assertEqual(
            retrieved_invitation["team_role"],
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[TeamInvitation.TEAM_ROLE_MEMBER],
        )
        self.assertEqual(
            retrieved_invitation["status"],
            dict(TeamInvitation.STATUS_CHOICES)[TeamInvitation.STATUS_PENDING],
        )

    def test_creation_minimal_payload(self):
        payload = {
            'email': 'come_join_amuse@example.com',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invitation = TeamInvitation.objects.last()
        self.assertEqual(invitation.inviter, self.user)
        self.assertEqual(invitation.invitee, None)
        self.assertEqual(invitation.artist, self.artist)
        self.assertEqual(invitation.email, payload['email'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertEqual(
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[invitation.team_role],
            payload['team_role'],
        )
        self.assertTrue(invitation.valid)

    def test_creation_minimal_payload_with_phone(self):
        payload = {
            'phone_number': '+1-202-555-0174',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invitation = TeamInvitation.objects.last()
        self.assertEqual(invitation.inviter, self.user)
        self.assertEqual(invitation.invitee, None)
        self.assertEqual(invitation.artist, self.artist)
        self.assertEqual(invitation.email, None)
        self.assertEqual(invitation.phone_number, payload['phone_number'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertEqual(
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[invitation.team_role],
            payload['team_role'],
        )
        self.assertTrue(invitation.valid)

    def test_creation_with_invitee(self):
        invitee = UserFactory()

        payload = {
            'email': 'come_join_amuse@example.com',
            'phone_number': '+1-202-555-0174',
            'invitee': invitee.id,
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        invitation_id = response.data['id']
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invitation = TeamInvitation.objects.last()
        self.assertEqual(invitation.id, invitation_id)
        self.assertEqual(invitation.inviter, self.user)
        self.assertEqual(invitation.invitee, invitee)
        self.assertEqual(invitation.artist, self.artist)
        self.assertEqual(invitation.email, payload['email'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertEqual(
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[invitation.team_role],
            payload['team_role'],
        )
        self.assertEqual(invitation.phone_number, payload['phone_number'])
        self.assertTrue(invitation.valid)

    def test_creation_without_invitee(self):
        payload = {
            'email': 'come_join_amuse@example.com',
            'phone_number': '+1-202-555-0174',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        invitation_id = response.data['id']
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invitation = TeamInvitation.objects.last()
        self.assertEqual(invitation.id, invitation_id)
        self.assertEqual(invitation.inviter, self.user)
        self.assertIsNone(invitation.invitee)
        self.assertEqual(invitation.artist, self.artist)
        self.assertEqual(invitation.email, payload['email'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertEqual(
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[invitation.team_role],
            payload['team_role'],
        )
        self.assertEqual(invitation.phone_number, payload['phone_number'])
        self.assertTrue(invitation.valid)

    def test_user_can_create_multiple_invites_for_artist(self):
        payload = {
            'email': 'come_join_amus1e@example.com',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response1 = self.client.post(self.url, payload, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        payload['email'] = 'come_join_amuse2@example.com'
        response2 = self.client.post(self.url, payload, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        payload['email'] = 'come_join_amuse3@example.com'
        response3 = self.client.post(self.url, payload, format='json')
        self.assertEqual(response3.status_code, status.HTTP_201_CREATED)

        self.assertEqual(TeamInvitation.objects.filter(artist=self.artist).count(), 3)

    def test_email_or_number_is_required(self):
        payload = {
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    def test_email_or_number_value_is_required(self):
        payload = {
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
            'phone_number': None,
            'email': None,
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    def test_email_cannot_be_empty_string(self):
        payload = {
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
            'phone_number': None,
            'email': '',
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    def test_basic_user_cannot_create_invite(self):
        artist = Artistv2Factory()
        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.SPECTATOR
        )
        payload = {
            'email': 'come_join_amuse@example.com',
            'artist': artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    def test_token(self):
        invitee = UserFactory(artist_name='New User')

        payload = {
            'email': invitee.email,
            'artist': self.artist.id,
            'invitee': invitee.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        invite = TeamInvitation.objects.last()
        token = invite.token
        token_data = user_invitation_token_generator.decode_token(token)

        self.assertEqual(token_data['inviter_first_name'], self.user.first_name)
        self.assertEqual(token_data['inviter_last_name'], self.user.last_name)
        self.assertEqual(token_data['user_id'], self.user.id)
        self.assertEqual(token_data['artist_id'], self.artist.id)
        self.assertEqual(token_data['artist_name'], self.artist.name)
        self.assertEqual(token_data['invitee_id'], invitee.id)

    def test_decline(self):
        invitation = TeamInvitationFactory(inviter=self.user, artist=self.artist)
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, TeamInvitation.STATUS_DECLINED)
        self.assertFalse(invitation.valid)

    def test_cant_decline_others_invites(self):
        invitation = TeamInvitationFactory()
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.data)

    def test_cant_create_invite_to_own_email(self):
        payload = {
            'email': self.user.email,
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    def test_can_create_multiple_invites_to_same_email_if_status_not_pending(self):
        email = "email@email.com"

        invitation = TeamInvitationFactory(
            artist=self.artist, email=email, status=TeamInvitation.STATUS_ACCEPTED
        )

        payload = {
            'email': email,
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_cant_create_multiple_invites_to_same_email_if_status_pending(self):
        email = 'email@example.com'

        invitation = TeamInvitationFactory(
            artist=self.artist, email=email, status=TeamInvitation.STATUS_PENDING
        )

        payload = {
            'email': email,
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )
        self.assertIn('already been sent', response.data[0])

    def test_cant_create_multiple_invites_to_same_phone(self):
        phone_number = '+1-202-555-0174'

        invitation = TeamInvitationFactory(
            artist=self.artist, phone_number=phone_number
        )

        payload = {
            'phone_number': phone_number,
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )
        self.assertIn('already been sent', response.data[0])

    def test_cant_create_invitation_for_role_owner(self):
        payload = {
            'email': 'come_join_amuse@example.com',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_OWNER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    def test_accepted_invitation_cant_be_resent(self):
        invitation = TeamInvitationFactory(inviter=self.user, artist=self.artist)
        last_sent = invitation.last_sent + timezone.timedelta(days=-3)
        invitation.last_sent = last_sent
        invitation.status = TeamInvitation.STATUS_ACCEPTED
        invitation.save()
        invitation.refresh_from_db()
        url = reverse('team-invitations-detail', args=[invitation.id])

        payload = {'email': 'come_join_amuse_again@example.com'}
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )
        self.assertIn('already accepted', response.data['non_field_errors'][0])

    def test_user_can_fetch_own_invites(self):
        invitation1 = TeamInvitationFactory(inviter=self.user, artist=self.artist)
        invitation2 = TeamInvitationFactory(inviter=self.user, artist=self.artist)
        invitation3 = TeamInvitationFactory()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 2)

    def test_fetching_related_invitations(self):
        admin = UserFactory()
        artist = admin.create_artist_v2('admin')

        invitation1 = TeamInvitationFactory(inviter=admin, artist=artist)
        invitation2 = TeamInvitationFactory(inviter=admin, artist=artist)
        invitation3 = TeamInvitationFactory()

        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.SPECTATOR
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 2)

    def test_admin_can_manage_team_invites(self):
        admin = UserFactory()
        artist = admin.create_artist_v2('admin')

        invitation = TeamInvitationFactory(inviter=admin, artist=artist)
        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.ADMIN
        )

        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_spectator_cannot_manage_team_invites(self):
        admin = UserFactory()
        artist = admin.create_artist_v2('admin')

        invitation = TeamInvitationFactory(inviter=admin, artist=artist)
        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.SPECTATOR
        )

        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    def test_accepting_invitation_success(self):
        artist = Artistv2Factory()
        invitation = TeamInvitationFactory(artist=artist, invitee=self.user)

        data = {'token': invitation.token}
        url = reverse('team-invitations-confirm')
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, TeamInvitation.STATUS_ACCEPTED)
        self.assertEqual(invitation.invitee, self.user)
        self.assertFalse(invitation.valid)

        uar = UserArtistRole.objects.get(user=self.user, artist=artist)
        self.assertEqual(uar.type, invitation.team_role)

    def test_accepting_invitation_for_non_pro_user_without_artist_success(self):
        # Make our user non pro user without an artist
        self.user.subscriptions.all().delete()
        UserArtistRole.objects.filter(user=self.user).delete()
        # Send invite to some other artist to our user
        artist = Artistv2Factory()
        invitation = TeamInvitationFactory(artist=artist, invitee=self.user)

        data = {'token': invitation.token}
        url = reverse('team-invitations-confirm')
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, TeamInvitation.STATUS_ACCEPTED)
        self.assertEqual(invitation.invitee, self.user)
        self.assertFalse(invitation.valid)

        uar = UserArtistRole.objects.get(user=self.user, artist=artist)
        self.assertEqual(uar.type, invitation.team_role)

    def test_accepting_invitation_for_non_pro_user_with_artist_not_allowed(self):
        # Make our user non pro user
        self.user.subscriptions.all().delete()
        # Send invite to some other artist to our user
        artist = Artistv2Factory()
        invitation = TeamInvitationFactory(artist=artist, invitee=self.user)

        data = {'token': invitation.token}
        url = reverse('team-invitations-confirm')
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data, {'detail': TeamInvitationViewSet.permission_denied_message}
        )

    def test_accepted_invitation_cannot_be_accepted_again(self):
        artist = Artistv2Factory()
        invitation = TeamInvitationFactory(
            artist=artist, invitee=self.user, status=TeamInvitation.STATUS_ACCEPTED
        )
        data = {'token': invitation.token}

        url = reverse('team-invitations-confirm')
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.data)

    def test_cannot_accept_invitation_if_member_already(self):
        artist = Artistv2Factory()
        invitation = TeamInvitationFactory(artist=artist, invitee=self.user)

        UserArtistRole.objects.create(
            artist=artist, user=self.user, type=UserArtistRole.MEMBER
        )

        data = {'token': invitation.token}
        url = reverse('team-invitations-confirm')
        response = self.client.post(url, data=data)
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

    def test_retrieved_correct_invitations_for_artist_filter(self):
        owner1 = UserFactory()
        artist1 = owner1.create_artist_v2('Artist 1')
        TeamInvitationFactory(inviter=owner1, artist=artist1)
        TeamInvitationFactory(inviter=owner1, artist=artist1)
        UserArtistRole.objects.create(
            artist=artist1, user=self.user, type=UserArtistRole.ADMIN
        )

        owner2 = UserFactory()
        artist2 = owner2.create_artist_v2('Artist 2')
        TeamInvitationFactory(inviter=owner2, artist=artist2)
        TeamInvitationFactory(inviter=owner2, artist=artist2)
        UserArtistRole.objects.create(
            artist=artist2, user=self.user, type=UserArtistRole.ADMIN
        )

        artist1_invitation_ids = list(
            TeamInvitation.objects.filter(artist=artist1).values_list('id', flat=True)
        )
        artist1_invitation_ids.sort()

        url = f'/api/team-invitations/?artist_id={artist1.id}'
        response = self.client.get(url)
        retrieved_invitation_ids = [d["id"] for d in response.data]
        retrieved_invitation_ids.sort()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Validate only invitations for artist1 team retrieved
        self.assertEqual(len(retrieved_invitation_ids), len(artist1_invitation_ids))
        self.assertEqual(retrieved_invitation_ids, artist1_invitation_ids)

    def test_sensitive_data_is_hidden_for_member(self):
        user = UserFactory()
        artist = user.create_artist_v2(name='Artist')
        UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.MEMBER
        )
        invitation = TeamInvitationFactory(
            inviter=user, artist=artist, team_role=TeamInvitation.TEAM_ROLE_MEMBER
        )

        response = self.client.get(self.url)
        retrieved_invitation = response.data[0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved_invitation["id"], invitation.id)
        self.assertEqual(
            retrieved_invitation["team_role"],
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[TeamInvitation.TEAM_ROLE_MEMBER],
        )
        self.assertEqual(
            retrieved_invitation["status"],
            dict(TeamInvitation.STATUS_CHOICES)[TeamInvitation.STATUS_PENDING],
        )
        self.assertEqual(retrieved_invitation["email"], '[Filtered]')
        self.assertEqual(retrieved_invitation["phone_number"], '[Filtered]')

    def test_sensitive_data_is_hidden_for_spectator(self):
        user = UserFactory()
        artist = user.create_artist_v2(name='Artist')
        UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.SPECTATOR
        )
        invitation = TeamInvitationFactory(
            inviter=user, artist=artist, team_role=TeamInvitation.TEAM_ROLE_MEMBER
        )

        response = self.client.get(self.url)
        retrieved_invitation = response.data[0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved_invitation["id"], invitation.id)
        self.assertEqual(
            retrieved_invitation["team_role"],
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[TeamInvitation.TEAM_ROLE_MEMBER],
        )
        self.assertEqual(
            retrieved_invitation["status"],
            dict(TeamInvitation.STATUS_CHOICES)[TeamInvitation.STATUS_PENDING],
        )
        self.assertEqual(retrieved_invitation["email"], '[Filtered]')
        self.assertEqual(retrieved_invitation["phone_number"], '[Filtered]')

    def test_sensitive_data_is_shown_for_admin(self):
        user = UserFactory()
        artist = user.create_artist_v2(name='Artist')
        UserArtistRole.objects.create(
            user=self.user, artist=artist, type=UserArtistRole.ADMIN
        )
        invitation = TeamInvitationFactory(
            inviter=user, artist=artist, team_role=TeamInvitation.TEAM_ROLE_MEMBER
        )

        response = self.client.get(self.url)
        retrieved_invitation = response.data[0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved_invitation["id"], invitation.id)
        self.assertEqual(
            retrieved_invitation["team_role"],
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[TeamInvitation.TEAM_ROLE_MEMBER],
        )
        self.assertEqual(
            retrieved_invitation["status"],
            dict(TeamInvitation.STATUS_CHOICES)[TeamInvitation.STATUS_PENDING],
        )
        self.assertNotEqual(retrieved_invitation["email"], '[Filtered]')
        self.assertNotEqual(retrieved_invitation["phone_number"], '[Filtered]')

    def test_sensitive_data_is_shown_for_owner(self):
        invitation = TeamInvitationFactory(
            inviter=self.user,
            artist=self.artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )

        response = self.client.get(self.url)
        retrieved_invitation = response.data[0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved_invitation["id"], invitation.id)
        self.assertEqual(
            retrieved_invitation["team_role"],
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[TeamInvitation.TEAM_ROLE_MEMBER],
        )
        self.assertEqual(
            retrieved_invitation["status"],
            dict(TeamInvitation.STATUS_CHOICES)[TeamInvitation.STATUS_PENDING],
        )
        self.assertNotEqual(retrieved_invitation["email"], '[Filtered]')
        self.assertNotEqual(retrieved_invitation["phone_number"], '[Filtered]')

    def test_frozen_user_can_not_create_invite(self):
        self.user.is_frozen = True
        self.user.save()

        payload = {
            'email': 'come_join_amuse@example.com',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_ADMIN
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('is frozen', str(response.content))

    def test_frozen_user_can_not_update_invite(self):
        self.user.is_frozen = True
        self.user.save()

        invitation = TeamInvitationFactory(
            inviter=self.user,
            artist=self.artist,
            team_role=TeamInvitation.TEAM_ROLE_ADMIN,
        )

        update_payload = {
            'email': 'new_email@fake.com',
            'phone_number': None,
            'invitee': UserFactory().id,
        }
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('is frozen', str(response.content))


class TeamInvitationUpdateAPITestCase(AmuseAPITestCase):
    def setUp(self):
        super(AmuseAPITestCase, self).setUp()
        self.user = UserFactory(artist_name='Lil Artist', is_pro=True)
        self.artist = self.user.create_artist_v2('Lil Artist')
        self.song = SongFactory()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user.auth_token.key)
        self.url = reverse('team-invitations-list')

    def test_update_with_invitee(self):
        invitee = UserFactory(artist_name='New User')
        payload = {
            'email': invitee.email,
            'artist': self.artist.id,
            'invitee': invitee.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        invitation = TeamInvitation.objects.get(pk=response.data['id'])
        initial_token = invitation.token

        # do not update
        update_payload = {
            'email': invitee.email,
            'phone_number': None,
            'invitee': UserFactory().id,
        }
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(
            status.HTTP_400_BAD_REQUEST, response.status_code, response.data
        )

        # update if more than 3 minutes has passed since last sent
        last_sent = invitation.last_sent + timezone.timedelta(minutes=-3)
        invitation.last_sent = last_sent
        invitation.save()
        invitation.refresh_from_db()

        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(status.HTTP_200_OK, response.status_code, response.data)

        invitation.refresh_from_db()
        self.assertEqual(invitation.email, update_payload['email'])
        self.assertEqual(invitation.phone_number, update_payload['phone_number'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertEqual(invitation.invitee_id, update_payload['invitee'])
        self.assertNotEqual(initial_token, invitation.token)
        self.assertNotEqual(last_sent, invitation.last_sent)

    def test_update_without_invitee(self):
        payload = {
            'email': 'come_join_amuse@example.com',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        invitation = TeamInvitation.objects.get(pk=response.data['id'])
        initial_token = invitation.token

        update_payload = {
            'email': 'come_join_amuse@example.com',
            'first_name': 'sime',
            'last_name': 'kime',
        }
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )

        last_sent = invitation.last_sent + timezone.timedelta(minutes=-3)
        invitation.last_sent = last_sent
        invitation.save()
        invitation.refresh_from_db()

        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        invitation.refresh_from_db()
        self.assertEqual(invitation.email, update_payload['email'])
        self.assertEqual(invitation.first_name, update_payload['first_name'])
        self.assertEqual(invitation.last_name, update_payload['last_name'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertIsNone(invitation.invitee)
        self.assertNotEqual(initial_token, invitation.token)
        self.assertNotEqual(last_sent, invitation.last_sent)

    def test_update_if_email_changed(self):
        invitee = UserFactory(artist_name='New User')
        payload = {
            'email': invitee.email,
            'artist': self.artist.id,
            'invitee': invitee.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        invitation = TeamInvitation.objects.get(pk=response.data['id'])
        initial_token = invitation.token

        update_payload = {
            'email': 'new_email@fake.com',
            'phone_number': None,
            'invitee': UserFactory().id,
        }
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(status.HTTP_200_OK, response.status_code, response.data)

        invitation.refresh_from_db()
        self.assertEqual(invitation.email, update_payload['email'])
        self.assertEqual(invitation.phone_number, update_payload['phone_number'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertEqual(invitation.invitee_id, update_payload['invitee'])
        self.assertNotEqual(initial_token, invitation.token)

    def test_update_if_phone_changed(self):
        invitee = UserFactory(artist_name='New User')
        payload = {
            'email': invitee.email,
            'artist': self.artist.id,
            'invitee': invitee.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        invitation = TeamInvitation.objects.get(pk=response.data['id'])
        initial_token = invitation.token

        update_payload = {
            'email': invitee.email,
            'phone_number': '+1-202-555-0175',
            'invitee': UserFactory().id,
        }
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(status.HTTP_200_OK, response.status_code, response.data)

        invitation.refresh_from_db()
        self.assertEqual(invitation.email, update_payload['email'])
        self.assertEqual(invitation.phone_number, update_payload['phone_number'])
        self.assertEqual(invitation.status, TeamInvitation.STATUS_PENDING)
        self.assertEqual(invitation.invitee_id, update_payload['invitee'])
        self.assertNotEqual(initial_token, invitation.token)

    def test_cant_update_to_existing_pending_email(self):
        email = 'email@example.com'
        email2 = 'email2@example.com'

        invitation1 = TeamInvitationFactory(artist=self.artist, email=email)
        invitation2 = TeamInvitationFactory(
            inviter=self.user, artist=self.artist, email=email2
        )
        invitation2.last_sent = timezone.now() - timezone.timedelta(days=3)
        invitation2.save()

        payload = {'email': email}
        url = reverse('team-invitations-detail', args=[invitation2.id])
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )
        self.assertIn('already been sent', response.data[0])

    def test_can_update_to_existing_email(self):
        email = 'email@example.com'
        email2 = 'email2@example.com'

        invitation0 = TeamInvitationFactory(
            artist=self.artist, email=email, status=TeamInvitation.STATUS_DECLINED
        )
        invitation1 = TeamInvitationFactory(
            artist=self.artist, email=email, status=TeamInvitation.STATUS_ACCEPTED
        )
        invitation2 = TeamInvitationFactory(
            inviter=self.user, artist=self.artist, email=email2
        )
        invitation2.last_sent = timezone.now() - timezone.timedelta(days=3)
        invitation2.save()

        payload = {'email': email}
        url = reverse('team-invitations-detail', args=[invitation2.id])
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(status.HTTP_200_OK, response.status_code, response.data)

    def test_cant_update_to_existing_pending_phone_number(self):
        phone_number = '+1-202-555-0175'
        phone_number2 = '+1-202-555-0174'

        invitation1 = TeamInvitationFactory(
            artist=self.artist, phone_number=phone_number
        )
        invitation2 = TeamInvitationFactory(
            inviter=self.user, artist=self.artist, phone_number=phone_number2
        )
        invitation2.last_sent = timezone.now() - timezone.timedelta(days=3)
        invitation2.save()

        payload = {'phone_number': phone_number}
        url = reverse('team-invitations-detail', args=[invitation2.id])
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )
        self.assertIn('already been sent', response.data[0])

    def test_can_update_to_existing_phone_number(self):
        phone_number = '+1-202-555-0175'
        phone_number2 = '+1-202-555-0174'

        invitation0 = TeamInvitationFactory(
            artist=self.artist,
            phone_number=phone_number,
            status=TeamInvitation.STATUS_DECLINED,
        )
        invitation1 = TeamInvitationFactory(
            artist=self.artist,
            phone_number=phone_number,
            status=TeamInvitation.STATUS_ACCEPTED,
        )
        invitation2 = TeamInvitationFactory(
            inviter=self.user, artist=self.artist, phone_number=phone_number2
        )
        invitation2.last_sent = timezone.now() - timezone.timedelta(days=3)
        invitation2.save()

        payload = {'phone_number': phone_number}
        url = reverse('team-invitations-detail', args=[invitation2.id])
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(status.HTTP_200_OK, response.status_code, response.data)

    def test_accepted_invitation_cant_be_resent(self):
        invitation = TeamInvitationFactory(inviter=self.user, artist=self.artist)
        last_sent = invitation.last_sent + timezone.timedelta(days=-3)
        invitation.last_sent = last_sent
        invitation.status = TeamInvitation.STATUS_ACCEPTED
        invitation.save()
        invitation.refresh_from_db()
        url = reverse('team-invitations-detail', args=[invitation.id])

        payload = {'email': 'come_join_amuse_again@example.com'}
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST, response.data
        )
        self.assertIn('already accepted', response.data['non_field_errors'][0])


class TeamInvitationAPIProPermission(AmuseAPITestCase):
    def setUp(self):
        super(AmuseAPITestCase, self).setUp()
        self.user = UserFactory(artist_name='Lil Artist', is_pro=False)
        self.artist = self.user.create_artist_v2('Lil Artist')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user.auth_token.key)
        self.url = reverse('team-invitations-list')

    def test_retrieved_data(self):
        invitation = TeamInvitationFactory(
            inviter=self.user,
            artist=self.artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )

        response = self.client.get(self.url)
        retrieved_invitation = response.data[0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved_invitation["id"], invitation.id)
        self.assertEqual(
            retrieved_invitation["team_role"],
            dict(TeamInvitation.TEAM_ROLE_CHOICES)[TeamInvitation.TEAM_ROLE_MEMBER],
        )
        self.assertEqual(
            retrieved_invitation["status"],
            dict(TeamInvitation.STATUS_CHOICES)[TeamInvitation.STATUS_PENDING],
        )

    def test_can_not_create_invite(self):
        payload = {
            'email': 'come_join_amuse@example.com',
            'artist': self.artist.id,
            'team_role': dict(TeamInvitation.TEAM_ROLE_CHOICES)[
                TeamInvitation.TEAM_ROLE_MEMBER
            ],
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_not_update(self):
        invitation = TeamInvitationFactory(
            inviter=self.user,
            artist=self.artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )

        update_payload = {
            'email': 'new_email@fake.com',
            'phone_number': None,
            'invitee': UserFactory().id,
        }
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.patch(url, update_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_not_delete(self):
        invitation = TeamInvitationFactory(
            inviter=self.user,
            artist=self.artist,
            team_role=TeamInvitation.TEAM_ROLE_MEMBER,
        )
        url = reverse('team-invitations-detail', args=[invitation.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
