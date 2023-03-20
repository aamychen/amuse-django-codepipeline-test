from uuid import uuid4

import factory
from django.core.management.base import BaseCommand

from releases.tests.factories import (
    CoverArtFactory,
    ReleaseFactory,
    SongArtistRoleFactory,
    SongFactory,
    SongArtistRole,
)
from subscriptions.tests.factories import SubscriptionFactory
from users import models
from users.tests.factories import (
    Artistv2Factory,
    TeamInvitationFactory,
    UserArtistRoleFactory,
    UserFactory,
)


class Command(BaseCommand):
    help = """Creates Users, Artists, Releases, Songs, Contributors and STATS
              for testing purposes."""

    def add_arguments(self, parser):
        parser.add_argument(
            '--cypress',
            action='store_true',
            help='Create base users for cypress testing.',
        )
        parser.add_argument(
            '--generic',
            action='store_true',
            help='Create base generic users for testing.',
        )

    def handle(self, *args, **options):
        if options['cypress']:
            generate_cypress_users_and_releases()
        else:
            generate_users_and_releases()

        self.stdout.write(self.style.SUCCESS('Fixtures successfully created.'))


def generate_users_and_releases(user_count=10):
    print(f'Creating {user_count} users')
    UserFactory.create_batch(user_count)
    for i in range(0, user_count):
        user = UserFactory()
        user.create_artist_v2(user.artist_name)
        for i in range(0, 5):
            release = ReleaseFactory(user=user)
            CoverArtFactory(release=release, user=user, file=f"{str(uuid4())}.jpg")
            for j in range(0, 3):
                song = SongFactory(release=release)
                SongArtistRoleFactory(artist=user.artists.first(), song=song)
                SongArtistRoleFactory(
                    artist=Artistv2Factory(),
                    song=song,
                    role=SongArtistRole.ROLE_FEATURED_ARTIST,
                )


def generate_cypress_users_and_releases():
    user_fixtures = [
        {
            "email": 'test@amuse.io',
            "password": 'qwerty123',
            "first_name": 'TestUser',
            "last_name": 'Owner',
            "artist_name": 'TestArtistName',
            "is_pro": True,
            "role": models.UserArtistRole.OWNER,
        },
        {
            "email": 'test+admin@amuse.io',
            "password": 'qwerty123',
            "first_name": 'TestUser',
            "last_name": 'Admin',
            "artist_name": 'TestTeamAdminUser',
            "is_pro": True,
            "role": models.UserArtistRole.ADMIN,
        },
        {
            "email": 'test+member@amuse.io',
            "password": 'qwerty123',
            "first_name": 'TestUser',
            "last_name": 'Member',
            "artist_name": 'TestTeamMemberUser',
            "is_pro": True,
            "role": models.UserArtistRole.MEMBER,
        },
        {
            "email": 'test+spectator@amuse.io',
            "password": 'qwerty123',
            "first_name": 'TestUser',
            "last_name": 'Spectator',
            "artist_name": 'TestTeamSpectatorUser',
            "is_pro": True,
            "role": models.UserArtistRole.SPECTATOR,
        },
        {
            "email": 'test+free@amuse.io',
            "password": 'qwerty123',
            "first_name": 'TestUser',
            "last_name": 'Free',
            "artist_name": 'TestTeamFreeUser',
            "is_pro": False,
            "role": models.UserArtistRole.MEMBER,
        },
        {
            "email": 'test+web-invite-not-existing-user-6203@amuse.io',
            "password": 'qwerty123',
            "first_name": 'TestUser',
            "last_name": 'NotExists6203',
            "artist_name": 'TestUser NotExists6203',
            "is_pro": True,
            "role": models.UserArtistRole.MEMBER,
        },
    ]

    user_list = []
    artistv2_list = []

    for user_fixture in user_fixtures:
        role = user_fixture.pop('role', models.UserArtistRole.MEMBER)
        user = UserFactory(**user_fixture)
        print(f'{user.email}')

        artistv2 = user.create_artist_v2(user.artist_name)

        user_list.append(user)
        artistv2_list.append(artistv2)

        if not user_fixture['email'] in 'test@amuse.io':
            UserArtistRoleFactory(
                user=user_list[-1], artist=artistv2_list[0], type=role
            )

    invite_only_user = UserFactory(
        email='test+web-invite-not-existing-user-7178@amuse.io',
        password='qwerty123',
        first_name='TestUser',
        last_name='NotExists7178',
        artist_name='TestUser NotExists7178',
        is_pro=False,
    )
    print(f'{invite_only_user.email}')

    TeamInvitationFactory(
        email=invite_only_user.email,
        first_name=invite_only_user.first_name,
        last_name=invite_only_user.last_name,
        inviter=user_list[0],
        invitee=invite_only_user,
        artist=artistv2_list[0],
        status=models.TeamInvitation.STATUS_PENDING,
        team_role=models.TeamInvitation.TEAM_ROLE_MEMBER,
    )
