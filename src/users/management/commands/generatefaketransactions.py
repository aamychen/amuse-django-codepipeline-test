import datetime
import random
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from codes.models import Code, ISRC
from releases.models import Song
from users.models import User, TransactionSource, Transaction, TransactionDeposit


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        source_list = (
            'Apple Music',
            'Deezer',
            'Google Play',
            'iTunes',
            'Spotify',
            'Youtube',
            'Youtube Red',
        )
        date_list = [
            (d.year, d.month)
            for d in [
                datetime.date.today() - datetime.timedelta(weeks=4 * i)
                for i in range(0, 2)
            ]
        ][::-1]
        isrc_list = ISRC.objects.filter(status=Code.STATUS_USED)

        transactions = []

        for year, month in date_list:
            date = datetime.date(year, month, 1)
            for isrc in isrc_list:
                for source_name in source_list:
                    source, created = TransactionSource.objects.get_or_create(
                        name=source_name
                    )

                    users = User.objects.filter(releases__songs__isrc=isrc)

                    if len(users) == 0:
                        print('ISRC %s returned no user!' % isrc.code)
                        continue

                    if len(users) > 1:
                        print('ISRC %s returned more than one user!' % isrc.code)
                        continue

                    user = users[0]

                    amount = Decimal(
                        random.uniform(
                            0.0, 100.0 if random.randrange(0, 10) == 0 else 1.0
                        )
                    ).quantize(Decimal(10) ** -6)

                    transaction, created = Transaction.objects.get_or_create(
                        date=date,
                        source=source,
                        user=user,
                        defaults={
                            'type': Transaction.TYPE_DEPOSIT,
                            'status': Transaction.STATUS_COMPLETED,
                        },
                    )

                    if transaction.id not in transactions:
                        transactions.append(transaction.id)
                        if not created:
                            transaction.amount = Decimal(0.0)

                    transaction.amount += amount
                    transaction.save()

                    deposit, created = TransactionDeposit.objects.get_or_create(
                        transaction=transaction, isrc=isrc
                    )
                    deposit.amount = amount
                    deposit.save()
