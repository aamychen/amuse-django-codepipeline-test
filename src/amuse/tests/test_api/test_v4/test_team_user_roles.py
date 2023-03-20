import responses
from rest_framework import status
from django.urls import reverse_lazy as reverse
from unittest import mock

from users.tests.factories import UserFactory, Artistv2Factory, UserArtistRoleFactory
from amuse.tests.test_api.base import API_V4_ACCEPT_VALUE, AmuseAPITestCase
from subscriptions.tests.factories import (
    SubscriptionPlan,
    SubscriptionPlanFactory,
    SubscriptionFactory,
)
from users.models import ArtistV2, UserArtistRole


class TeamUserRolesAPITestCase(AmuseAPITestCase):
    def setUp(self):
        super().setUp()
        sub_plan = SubscriptionPlanFactory(tier=SubscriptionPlan.TIER_PRO)
        self.user = UserFactory()
        SubscriptionFactory(user=self.user, plan=sub_plan)
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)
        self.url = reverse('team-user-roles-list')
        self.my_artist = Artistv2Factory(name='My Artist', owner=self.user)
        UserArtistRoleFactory(
            user=self.user, artist=self.my_artist, type=UserArtistRole.OWNER
        )
        self.other_artist = Artistv2Factory(name='Other Artist', owner=UserFactory())
        UserArtistRoleFactory(
            user=self.other_artist.owner,
            artist=self.other_artist,
            type=UserArtistRole.OWNER,
        )

    @responses.activate
    def test_artist_roles_response_data(self):
        role = UserArtistRole.objects.get(
            user=self.user, artist=self.my_artist, type=UserArtistRole.OWNER
        )

        response = self.client.get(self.url)
        retrieved_roles = response.data[0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(retrieved_roles['id'], role.id)
        self.assertEqual(
            retrieved_roles['type'], dict(UserArtistRole.TYPE_CHOICES)[role.type]
        )
        self.assertIsNotNone(retrieved_roles['user'])
        self.assertEqual(retrieved_roles['user']['id'], self.user.id)
        self.assertEqual(retrieved_roles['user']['first_name'], self.user.first_name)
        self.assertEqual(retrieved_roles['user']['last_name'], self.user.last_name)
        self.assertEqual(retrieved_roles['user']['email'], self.user.email)
        self.assertIsNotNone(retrieved_roles['artist'])
        self.assertEqual(retrieved_roles['artist']['id'], self.my_artist.id)
        self.assertEqual(retrieved_roles['artist']['name'], self.my_artist.name)

    @responses.activate
    def test_artist_roles_retrieved(self):
        # Add another user to my team
        UserArtistRoleFactory(
            user=UserFactory(), artist=self.my_artist, type=UserArtistRole.ADMIN
        )
        # Collect all role ids for my artist
        artist_role_ids = list(
            UserArtistRole.objects.filter(artist=self.my_artist).values_list(
                'id', flat=True
            )
        )
        artist_role_ids.sort()

        response = self.client.get(self.url)
        retrieved_artist_role_ids = [d['id'] for d in response.data]
        retrieved_artist_role_ids.sort()

        # All artist roles for current user are retrieved
        self.assertEqual(len(retrieved_artist_role_ids), len(artist_role_ids))
        self.assertEqual(retrieved_artist_role_ids, artist_role_ids)

    @responses.activate
    def test_only_roles_for_user_artist_teams_retrieved(self):
        # Add other user to my team as and admin
        user_artist_other_user_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.my_artist, type=UserArtistRole.ADMIN
        )
        # Add another user to other artist team as an admin
        other_artist_other_user_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.other_artist, type=UserArtistRole.ADMIN
        )

        # Retrieve my role
        user_artist_role = UserArtistRole.objects.get(
            user=self.user, artist=self.my_artist
        )

        response = self.client.get(self.url)
        retrieved_artist_role_ids = [d['id'] for d in response.data]

        # Validate that only roles for my artists are retrieved,
        # not the role of other artist
        self.assertEqual(len(retrieved_artist_role_ids), 2)
        self.assertTrue(user_artist_role.id in retrieved_artist_role_ids)
        self.assertTrue(user_artist_other_user_role.id in retrieved_artist_role_ids)
        self.assertFalse(other_artist_other_user_role.id in retrieved_artist_role_ids)

    @responses.activate
    def test_edit_not_allowed_for_user_with_no_permissions(self):
        roles_with_no_edit_permissions = [
            UserArtistRole.MEMBER,
            UserArtistRole.SPECTATOR,
        ]
        for role in roles_with_no_edit_permissions:
            # Add user to the artist team with no edit permission role
            other_role = UserArtistRoleFactory(
                user=self.user, artist=self.other_artist, type=role
            )
            # Add member role to this artist to some other user
            other_user_artist_role = UserArtistRoleFactory(
                user=UserFactory(), artist=self.other_artist, type=UserArtistRole.MEMBER
            )
            # Try editing other user role
            url = f'/api/team-user-roles/{other_user_artist_role.pk}/'
            response = self.client.put(
                url,
                {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.SPECTATOR]},
                format='json',
            )
            other_role.delete()
            # Validate that user was not allowed to edit other user role
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_edit_successful_for_user_with_permissions(self):
        roles_with_edit_permissions = [UserArtistRole.ADMIN]
        for role in roles_with_edit_permissions:
            # Add user to the artist team with edit permission role
            UserArtistRoleFactory(user=self.user, artist=self.other_artist, type=role)
            # Add member role to this artist to some other user
            other_user_artist_role = UserArtistRoleFactory(
                user=UserFactory(), artist=self.other_artist, type=UserArtistRole.MEMBER
            )
            # Try editing other user role
            url = f'/api/team-user-roles/{other_user_artist_role.pk}/'
            response = self.client.put(
                url,
                {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.SPECTATOR]},
                format='json',
            )
            other_user_artist_role.refresh_from_db()
            # Validate that edit was successful
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(other_user_artist_role.type, UserArtistRole.SPECTATOR)

    @responses.activate
    def test_edit_successful_for_owner_user(self):
        # Add member role to my artist to some other user
        other_user_artist_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.my_artist, type=UserArtistRole.MEMBER
        )
        # Try editing other user role
        url = f'/api/team-user-roles/{other_user_artist_role.pk}/'
        response = self.client.put(
            url,
            {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.SPECTATOR]},
            format='json',
        )
        other_user_artist_role.refresh_from_db()
        # Validate that edit was successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_user_artist_role.type, UserArtistRole.SPECTATOR)

    @responses.activate
    def test_update_to_non_upgradable_roles_not_allowed(self):
        non_upgradable_roles = [UserArtistRole.OWNER, UserArtistRole.SUPERADMIN]
        # Add myself as admin to other artist
        UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        # Add user to other artist team to manage
        other_user_other_artist_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.other_artist, type=UserArtistRole.ADMIN
        )

        for role in non_upgradable_roles:
            # Try updating my role to non upgradable role
            url = f'/api/team-user-roles/{other_user_other_artist_role.pk}/'
            response = self.client.put(
                url, {"type": dict(UserArtistRole.TYPE_CHOICES)[role]}, format='json'
            )
            # Validate that user was not allowed to update role
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_delete_not_allowed_for_user_with_no_permissions(self):
        roles_with_no_delete_permissions = [
            UserArtistRole.MEMBER,
            UserArtistRole.SPECTATOR,
        ]
        for role in roles_with_no_delete_permissions:
            # Add user to the artist team with no edit permission role
            other_role = UserArtistRoleFactory(
                user=self.user, artist=self.other_artist, type=role
            )
            # Add member role to this artist to some other user
            other_user_artist_role = UserArtistRoleFactory(
                user=UserFactory(), artist=self.other_artist, type=UserArtistRole.MEMBER
            )
            # Try deleting other user role
            url = f'/api/team-user-roles/{other_user_artist_role.pk}/'
            response = self.client.delete(url)
            other_role.delete()
            # Validate that user was not allowed to delete other user role
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_delete_successful_for_user_with_permissions(self):
        roles_with_delete_permissions = [UserArtistRole.ADMIN]
        for role in roles_with_delete_permissions:
            # Add role to user to enable him to manage this artist roles
            UserArtistRoleFactory(user=self.user, artist=self.other_artist, type=role)
            # Add member role to this artist to some other user
            other_user_artist_role = UserArtistRoleFactory(
                user=UserFactory(), artist=self.other_artist, type=UserArtistRole.MEMBER
            )

            # Make request to manage the role of other user
            url = f'/api/team-user-roles/{other_user_artist_role.pk}/'
            response = self.client.delete(url)
            # Validate that other user role was removed
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @responses.activate
    def test_delete_successful_for_owner_user(self):
        # Add member role to this artist to some other user
        other_user_artist_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.my_artist, type=UserArtistRole.MEMBER
        )

        # Make request to manage the role of other user
        url = f'/api/team-user-roles/{other_user_artist_role.pk}/'
        response = self.client.delete(url)
        # Validate that other user role was removed
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @responses.activate
    def test_delete_successful_for_user_own_role(self):
        user_artist_role = UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.MEMBER
        )

        url = f'/api/team-user-roles/{user_artist_role.pk}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @responses.activate
    def test_fetch_teams_for_logged_in_user(self):
        url = reverse('team-user-roles-own')
        artist1 = Artistv2Factory(name='Artist 1', owner=UserFactory())
        artist2 = Artistv2Factory(name='Artist 2', owner=UserFactory())

        UserArtistRoleFactory(
            user=self.user, artist=artist1, type=UserArtistRole.MEMBER
        )
        UserArtistRoleFactory(
            user=self.user, artist=artist2, type=UserArtistRole.MEMBER
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(self.url)
        roles = response.data

        self.assertEqual(len(roles), 3)
        self.assertEqual(artist2.id, roles[2]['artist']['id'])
        self.assertEqual(artist1.id, roles[1]['artist']['id'])
        self.assertEqual(self.my_artist.id, roles[0]['artist']['id'])

    @responses.activate
    def test_edit_not_allowed_for_user_own_owner_role(self):
        my_owner_artist_role = UserArtistRole.objects.get(
            user=self.user, artist=self.my_artist, type=UserArtistRole.OWNER
        )
        # Try editing owner role
        url = f'/api/team-user-roles/{my_owner_artist_role.pk}/'
        response = self.client.put(
            url,
            {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.ADMIN]},
            format='json',
        )
        # Validate that user was not allowed to edit his owner role
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_delete_not_allowed_for_user_own_owner_role(self):
        my_owner_artist_role = UserArtistRole.objects.get(
            user=self.user, artist=self.my_artist, type=UserArtistRole.OWNER
        )
        # Try editing owner role
        url = f'/api/team-user-roles/{my_owner_artist_role.pk}/'
        response = self.client.delete(url)
        # Validate that user was not allowed to delete his owner role
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_edit_not_allowed_for_artist_owner_role(self):
        UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        owner_artist_role = UserArtistRole.objects.get(
            artist=self.other_artist, type=UserArtistRole.OWNER
        )
        # Try editing owner role
        url = f'/api/team-user-roles/{owner_artist_role.pk}/'
        response = self.client.put(
            url,
            {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.ADMIN]},
            format='json',
        )
        # Validate that user was not allowed to edit owner role
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_delete_not_allowed_for_artist_owner_role(self):
        UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        owner_artist_role = UserArtistRole.objects.get(
            artist=self.other_artist, type=UserArtistRole.OWNER
        )
        # Try editing owner role
        url = f'/api/team-user-roles/{owner_artist_role.pk}/'
        response = self.client.delete(url)
        # Validate that user was not allowed to edit owner role
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_updated_emails.delay', autospec=True)
    def test_email_tasks_called_correctly_when_updating_user_role(
        self, send_team_member_role_updated_emails
    ):
        # Set myself as admin
        UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        other_user_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        # Change other user role to member
        url = f'/api/team-user-roles/{other_user_role.pk}/'
        response = self.client.put(
            url,
            {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.MEMBER]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Validate that notification emails will be sent
        self.assertEqual(send_team_member_role_updated_emails.call_count, 1)
        # Validate that notification emails task is called with correct args
        self.assertEqual(
            send_team_member_role_updated_emails.call_args[0],
            (
                {
                    "user_id": self.user.id,
                    "artist_name": self.other_artist.name,
                    "member_email": other_user_role.user.email,
                    "member_first_name": other_user_role.user.first_name,
                    "member_last_name": other_user_role.user.last_name,
                    "admin_first_name": self.user.first_name,
                    "admin_last_name": self.user.last_name,
                    "owner_email": self.other_artist.owner.email,
                    "owner_first_name": self.other_artist.owner.first_name,
                    "owner_last_name": self.other_artist.owner.last_name,
                    "role": UserArtistRole.MEMBER,
                    "is_self_update": False,
                    "is_updated_by_owner": False,
                },
            ),
        )

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_updated_emails.delay', autospec=True)
    def test_email_tasks_called_correctly_when_updating_own_role(
        self, send_team_member_role_updated_emails
    ):
        my_admin_artist_role = UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        # Change my role to member
        url = f'/api/team-user-roles/{my_admin_artist_role.pk}/'
        response = self.client.put(
            url,
            {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.MEMBER]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Validate that notification emails will be sent
        self.assertEqual(send_team_member_role_updated_emails.call_count, 1)
        # Validate that notification emails task is called with correct args
        self.assertEqual(
            send_team_member_role_updated_emails.call_args[0],
            (
                {
                    "user_id": self.user.id,
                    "artist_name": self.other_artist.name,
                    "member_email": self.user.email,
                    "member_first_name": self.user.first_name,
                    "member_last_name": self.user.last_name,
                    "admin_first_name": self.user.first_name,
                    "admin_last_name": self.user.last_name,
                    "owner_email": self.other_artist.owner.email,
                    "owner_first_name": self.other_artist.owner.first_name,
                    "owner_last_name": self.other_artist.owner.last_name,
                    "role": UserArtistRole.MEMBER,
                    "is_self_update": True,
                    "is_updated_by_owner": False,
                },
            ),
        )

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_updated_emails.delay', autospec=True)
    def test_email_tasks_called_correctly_when_team_owner_updates_user_role(
        self, send_team_member_role_updated_emails
    ):
        other_user_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.my_artist, type=UserArtistRole.ADMIN
        )
        # Change my role to member
        url = f'/api/team-user-roles/{other_user_role.pk}/'
        response = self.client.put(
            url,
            {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.MEMBER]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Validate that notification emails will be sent
        self.assertEqual(send_team_member_role_updated_emails.call_count, 1)
        # Validate that notification emails task is called with correct args
        self.assertEqual(
            send_team_member_role_updated_emails.call_args[0],
            (
                {
                    "user_id": self.user.id,
                    "artist_name": self.my_artist.name,
                    "member_email": other_user_role.user.email,
                    "member_first_name": other_user_role.user.first_name,
                    "member_last_name": other_user_role.user.last_name,
                    "admin_first_name": self.user.first_name,
                    "admin_last_name": self.user.last_name,
                    "owner_email": self.user.email,
                    "owner_first_name": self.user.first_name,
                    "owner_last_name": self.user.last_name,
                    "role": UserArtistRole.MEMBER,
                    "is_self_update": False,
                    "is_updated_by_owner": True,
                },
            ),
        )

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_removed_emails.delay', autospec=True)
    def test_email_tasks_called_correctly_when_removing_role(
        self, send_team_member_role_removed_emails
    ):
        # Set myself as admin
        UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        other_user_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        # Remove user role
        url = f'/api/team-user-roles/{other_user_role.pk}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Validate that notification emails will be sent
        self.assertEqual(send_team_member_role_removed_emails.call_count, 1)
        # Validate that notification emails task is called with correct args
        self.assertEqual(
            send_team_member_role_removed_emails.call_args[0],
            (
                {
                    "user_id": self.user.id,
                    "artist_name": self.other_artist.name,
                    "member_email": other_user_role.user.email,
                    "member_first_name": other_user_role.user.first_name,
                    "member_last_name": other_user_role.user.last_name,
                    "admin_first_name": self.user.first_name,
                    "admin_last_name": self.user.last_name,
                    "owner_email": self.other_artist.owner.email,
                    "owner_first_name": self.other_artist.owner.first_name,
                    "owner_last_name": self.other_artist.owner.last_name,
                    "is_self_removal": False,
                    "is_removed_by_owner": False,
                    "role": other_user_role.type,
                },
            ),
        )

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_removed_emails.delay', autospec=True)
    def test_email_tasks_called_correctly_when_removing_own_role(
        self, send_team_member_role_removed_emails
    ):
        my_admin_artist_role = UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        # Remove my role
        url = f'/api/team-user-roles/{my_admin_artist_role.pk}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # # Validate that notification emails will be sent
        self.assertEqual(send_team_member_role_removed_emails.call_count, 1)
        # Validate that notification emails task is called with correct args
        self.assertEqual(
            send_team_member_role_removed_emails.call_args[0],
            (
                {
                    "user_id": self.user.id,
                    "artist_name": self.other_artist.name,
                    "member_email": self.user.email,
                    "member_first_name": self.user.first_name,
                    "member_last_name": self.user.last_name,
                    "admin_first_name": self.user.first_name,
                    "admin_last_name": self.user.last_name,
                    "owner_email": self.other_artist.owner.email,
                    "owner_first_name": self.other_artist.owner.first_name,
                    "owner_last_name": self.other_artist.owner.last_name,
                    "is_self_removal": True,
                    "is_removed_by_owner": False,
                    "role": my_admin_artist_role.type,
                },
            ),
        )

    @responses.activate
    @mock.patch('amuse.tasks.send_team_member_role_removed_emails.delay', autospec=True)
    def test_email_tasks_called_correctly_when_team_owner_removes_user_role(
        self, send_team_member_role_removed_emails
    ):
        other_user_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.my_artist, type=UserArtistRole.ADMIN
        )
        # Remove user role
        url = f'/api/team-user-roles/{other_user_role.pk}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Validate that notification emails will be sent
        self.assertEqual(send_team_member_role_removed_emails.call_count, 1)
        # Validate that notification emails task is called with correct args
        self.assertEqual(
            send_team_member_role_removed_emails.call_args[0],
            (
                {
                    "user_id": self.user.id,
                    "artist_name": self.my_artist.name,
                    "member_email": other_user_role.user.email,
                    "member_first_name": other_user_role.user.first_name,
                    "member_last_name": other_user_role.user.last_name,
                    "admin_first_name": self.user.first_name,
                    "admin_last_name": self.user.last_name,
                    "owner_email": self.user.email,
                    "owner_first_name": self.user.first_name,
                    "owner_last_name": self.user.last_name,
                    "is_self_removal": False,
                    "is_removed_by_owner": True,
                    "role": other_user_role.type,
                },
            ),
        )

    @responses.activate
    def test_retrieved_correct_roles_for_artist_filter(self):
        # Add myself to other artist team
        UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        # Retrieve all roles for other artist team
        other_artist_role_ids = list(
            UserArtistRole.objects.filter(artist=self.other_artist).values_list(
                'id', flat=True
            )
        )
        other_artist_role_ids.sort()

        # Retrieve filtered roles
        url = f'/api/team-user-roles/?artist_id={self.other_artist.id}'
        response = self.client.get(url)
        retrieved_role_ids = [d["id"] for d in response.data]
        retrieved_role_ids.sort()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Validate only roles for other artist team retrieved
        self.assertEqual(len(retrieved_role_ids), len(other_artist_role_ids))
        self.assertEqual(retrieved_role_ids, other_artist_role_ids)


class TeamUserRolesAPIProPemissions(AmuseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.client.credentials(HTTP_ACCEPT=API_V4_ACCEPT_VALUE)
        self.client.force_authenticate(user=self.user)
        self.url = reverse('team-user-roles-list')
        self.my_artist = Artistv2Factory(name='My Artist', owner=self.user)
        UserArtistRoleFactory(
            user=self.user, artist=self.my_artist, type=UserArtistRole.OWNER
        )
        self.other_artist = Artistv2Factory(name='Other Artist', owner=UserFactory())
        UserArtistRoleFactory(
            user=self.other_artist.owner,
            artist=self.other_artist,
            type=UserArtistRole.OWNER,
        )

    @responses.activate
    def test_non_pro_can_not_edit(self):
        # Add member role to my artist to some other user
        other_user_artist_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.my_artist, type=UserArtistRole.MEMBER
        )
        # Try editing other user role
        url = f'/api/team-user-roles/{other_user_artist_role.pk}/'
        response = self.client.put(
            url,
            {"type": dict(UserArtistRole.TYPE_CHOICES)[UserArtistRole.SPECTATOR]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @responses.activate
    def test_delete_successful_for_own_role(self):
        user_artist_role = UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.MEMBER
        )

        url = f'/api/team-user-roles/{user_artist_role.pk}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @responses.activate
    def test_can_not_delete_others(self):
        UserArtistRoleFactory(
            user=self.user, artist=self.other_artist, type=UserArtistRole.ADMIN
        )
        user_artist_role = UserArtistRoleFactory(
            user=UserFactory(), artist=self.other_artist, type=UserArtistRole.MEMBER
        )
        url = f'/api/team-user-roles/{user_artist_role.pk}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
