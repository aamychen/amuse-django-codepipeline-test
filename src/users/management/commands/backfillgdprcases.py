from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import UserGDPR, UserMetadata


class Command(BaseCommand):
    help = 'Backfill missing UserMetadata.gdpr_wiped_at values'

    def handle(self, *args, **options):
        wipes = UserGDPR.objects.filter(
            minfraud_entries=True,
            artist_v2_history_entries=True,
            user_history_entries=True,
            email_adress=True,
            user_first_name=True,
            user_last_name=True,
            user_social_links=True,
            user_artist_name=True,
            artist_v2_names=True,
            artist_v2_social_links=True,
            artist_v1_names=True,
            artist_v1_social_links=True,
            user_apple_signin_id=True,
            user_facebook_id=True,
            user_firebase_token=True,
            user_zendesk_id=True,
            transaction_withdrawals=True,
            user_isactive_deactivation=True,
            user_newsletter_deactivation=True,
        )

        now = timezone.now()
        for wipe in wipes:
            UserMetadata.objects.update_or_create(
                user=wipe.user,
                defaults={'gdpr_wiped_at': now},
            )
