from django.core.management.base import BaseCommand

from payments.services.moss import MossReport, MossReportException


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--quarter',
            help='Quarter to run for, defaults to current',
            nargs='?',
            type=int,
        )
        parser.add_argument(
            '--year', help='Year to run for, defaults to current', nargs='?', type=int
        )
        parser.add_argument(
            '--month',
            help='Month to run for, when this option is specified the quarter argument is ignored',
            nargs='?',
            type=int,
        )
        parser.add_argument(
            '--country',
            help='Country code in ISO format, if given, summarises for specified country only',
            nargs='?',
            type=str,
        )

    def handle(self, *args, **kwargs):
        try:
            report = MossReport(
                year=kwargs.get('year'),
                quarter=kwargs.get('quarter'),
                month=kwargs.get('month'),
                country=kwargs.get('country'),
            )

            report.generate_report(self.stdout)
        except MossReportException as ex:
            self.stderr.write(str(ex))
            exit(1)
