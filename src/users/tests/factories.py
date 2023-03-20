import secrets
import uuid

import factory.fuzzy

from releases.models.royalty_split import RoyaltySplit
from users import models
from users.models import AppsflyerDevice


class UserFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.User

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    artist_name = factory.Faker('user_name')

    spotify_id = str(uuid.uuid4())

    email = factory.LazyAttribute(lambda o: "%s@example.org" % uuid.uuid4())
    email_verified = True
    password = 'hunter2'

    phone = factory.Sequence('+46760{0:06d}'.format)
    place_id = factory.Sequence('{0:d}'.format)
    country = factory.Faker('country_code')
    language = 'sv'
    profile_link = factory.Faker('url')
    profile_photo = factory.Sequence(lambda _: str(uuid.uuid4()))
    spotify_page = factory.SelfAttribute('artist_name')
    twitter_name = factory.SelfAttribute('artist_name')
    facebook_page = factory.SelfAttribute('artist_name')
    instagram_name = factory.SelfAttribute('artist_name')
    soundcloud_page = factory.SelfAttribute('artist_name')
    youtube_channel = factory.SelfAttribute('artist_name')

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        manager = cls._get_manager(model_class)
        is_pro = kwargs.pop('is_pro', False)
        user = manager.create_user(*args, **kwargs)
        if is_pro:
            from payments.tests.factories import SubscriptionFactory

            SubscriptionFactory(user=user, valid_from=user.created, plan__trial_days=0)
            UserMetadataFactory(
                user=user, pro_trial_expiration_date=user.created.date()
            )
        return user


class UserMetadataFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = models.UserMetadata


class CommentsFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Comments

    user = factory.SubFactory(UserFactory)
    text = factory.Faker('text')


class UserGDPRFactory(factory.DjangoModelFactory):
    initiator = factory.SubFactory(UserFactory)
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = models.UserGDPR


class Artistv2Factory(factory.DjangoModelFactory):
    class Meta:
        model = models.ArtistV2

    name = factory.Faker('user_name')
    spotify_id = None
    audiomack_id = None
    owner = factory.SubFactory(UserFactory)


class UserArtistRoleFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.UserArtistRole

    artist = factory.SubFactory(Artistv2Factory)
    user = factory.SubFactory(UserFactory)
    type = models.UserArtistRole.OWNER


def get_token():
    token = secrets.token_hex()
    return token


class TeamInvitationFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.TeamInvitation

    inviter = factory.SubFactory(UserFactory)
    invitee = factory.SubFactory(UserFactory)
    artist = factory.SubFactory(Artistv2Factory)
    first_name = factory.Faker('name')
    last_name = factory.Faker('name')
    phone_number = factory.Sequence('+46760{0:06d}'.format)
    status = models.TeamInvitation.STATUS_PENDING
    email = factory.Faker('safe_email')
    token = factory.LazyFunction(get_token)
    team_role = models.TeamInvitation.TEAM_ROLE_OWNER


class RoyaltyInvitationFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.RoyaltyInvitation

    inviter = factory.SubFactory(UserFactory)
    invitee = None
    royalty_split = factory.SubFactory(RoyaltySplit)
    status = models.RoyaltyInvitation.STATUS_CREATED
    email = factory.Faker('safe_email')
    phone_number = factory.Sequence('+46760{0:06d}'.format)
    name = factory.Faker('user_name')


class SongArtistInvitationFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SongArtistInvitation

    inviter = factory.SubFactory(UserFactory)
    invitee = None
    artist = factory.SubFactory(Artistv2Factory)
    song = None
    status = models.SongArtistInvitation.STATUS_CREATED
    email = factory.Faker('safe_email')
    phone_number = factory.Sequence('+46760{0:06d}'.format)


class AppsflyerDeviceFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = AppsflyerDevice
