import csv
from datetime import datetime

from django.core.management.base import BaseCommand

from releases.models import MetadataLanguage, Release, Song


class Command(BaseCommand):
    help = "Backfill missing languages codes for releases or songs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            type=str,
            help="Supported options are: release_language|song_language|song_locale",
        )
        parser.add_argument(
            "--limit", type=int, default=100, help="Limit the number of rows to update."
        )
        parser.add_argument(
            "--language_id",
            type=int,
            default=12,
            help="Override language_id. Defaults to 12 English in production.",
        )
        parser.add_argument(
            "--logpath",
            type=str,
            help="Specify path to save log file. Defaults to /tmp.",
            default="/tmp",
        )
        parser.add_argument(
            "--dry-run",
            dest="is_dry_run",
            action="store_true",
            help="Just print, do not update",
            default=False,
        )

    def handle(self, *args, **kwargs):
        update_field = kwargs.get("type")
        limit = kwargs.get("limit")
        language_id = kwargs.get("language_id")
        logpath = kwargs.get("logpath")
        is_dry_run = kwargs.get("is_dry_run", False)

        self.stdout.write(f"Start processing with {kwargs}")

        query_dict = {
            "release_language": {"klass": Release, "field": "meta_language"},
            "song_language": {"klass": Song, "field": "meta_language"},
            "song_locale": {"klass": Song, "field": "meta_audio_locale"},
        }

        query_item = query_dict.get(update_field, None)

        if query_item is None:
            self.stdout.write("Unsupported option")
            return

        klass, field = query_item["klass"], query_item["field"]
        query_kwargs = {f"{field}__isnull": True}

        obj_ids = (
            klass.objects.filter(**query_kwargs)
            .order_by("id")[:limit]
            .values_list("pk", flat=True)
        )

        self.stdout.write(
            f"Found {len(obj_ids)} objects with missing language to update."
        )

        log_file_name = None

        # This is just to check that the language actually exists in the database
        language = MetadataLanguage.objects.get(pk=language_id)

        if is_dry_run:
            for obj in obj_ids:
                self.stdout.write(f"Setting {obj} from None to {language.pk}")
        else:
            log_file_name = f"{logpath}/backfill_{update_field}_{language.pk}_{datetime.now().isoformat()}.csv"
            klass.objects.filter(id__in=obj_ids).update(**{field: language.pk})

            with open(log_file_name, "w", newline="") as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerow(["object_id"])

                for obj in obj_ids:
                    csvwriter.writerow([obj])

        self.stdout.write(
            f"Finished processing. Job results written to {log_file_name}."
        )
