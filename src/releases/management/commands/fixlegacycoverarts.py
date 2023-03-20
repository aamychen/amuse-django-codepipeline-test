import os
from uuid import uuid4

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from releases.models import CoverArt


class Command(BaseCommand):
    s3 = boto3.resource(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            action='store',
            help='Limits the number of CoverArts that are fixed',
            type=int,
            default=0,
        )

        parser.add_argument(
            '--noop',
            action='store_true',
            help='Only print files that would be migrated',
        )

    def handle(self, *args, **options):
        cover_arts = CoverArt.objects.filter(
            Q(file__contains='/') | ~Q(file__iregex=self.UUID_PATTERN)
        )
        cover_arts = cover_arts.exclude(file='')
        cover_arts = cover_arts.all()

        if options['limit']:
            cover_arts = cover_arts[: options['limit']]

        for cover_art in cover_arts:
            print('fixing', cover_art.file.name)
            if options['noop']:
                print(f'NOOP: Migrating {cover_art.file.name}')
            else:
                self.fix_s3_file_path(cover_art)

    def fix_s3_file_path(self, cover_art):
        file_extension = os.path.splitext(cover_art.file.name)[1]

        dest_key = f'{uuid4()}{file_extension}'
        source_key = cover_art.file.name

        source = {
            'Bucket': settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME,
            'Key': source_key,
        }
        self.s3.meta.client.copy(
            source, settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME, dest_key
        )

        try:
            self.s3.meta.client.delete_object(
                Bucket=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME, Key=source_key
            )
        except Exception as e:
            self.stdout.write(f'Could not delete the source file [{source_key}]: {e}')

        cover_art.file.name = dest_key
        cover_art.save()
