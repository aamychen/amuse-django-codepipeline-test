from datetime import date, datetime
from decimal import Decimal

from releases.models import RoyaltySplit, Release


def expected_splits_1(user1_id, user2_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 1,
        },
        {
            'user_id': None,
            'rate': Decimal('0.1000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 1,
        },
    ]


def expected_splits_1a(user1_id, user2_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 1,
        },
        {
            'user_id': None,
            'rate': Decimal('0.1000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 1,
        },
    ]


def expected_splits_2(user1_id, user2_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.6000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 1,
        },
    ]


def expected_splits_3(user1_id, user2_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.6000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 1,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 3, 20),
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 2,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': date(2020, 3, 20),
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 2,
        },
        {
            'user_id': None,
            'rate': Decimal('0.1000'),
            'start_date': date(2020, 3, 20),
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 2,
        },
    ]


def expected_splits_3a(user1_id, user2_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.6000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 1,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 3, 20),
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 2,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': date(2020, 3, 20),
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 2,
        },
        {
            'user_id': None,
            'rate': Decimal('0.1000'),
            'start_date': date(2020, 3, 20),
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 2,
        },
    ]


def expected_splits_4(user1_id, user2_id, user3_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.6000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user3_id,
            'rate': Decimal('0.1000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
    ]


def expected_splits_5(user1_id, user2_id, user3_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.6000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user3_id,
            'rate': Decimal('0.1000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 5, 10),
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 3,
        },
        {
            'user_id': None,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 5, 10),
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 3,
        },
    ]


def expected_splits_6(user1_id, user2_id, user3_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.6000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user3_id,
            'rate': Decimal('0.1000'),
            'start_date': date(2020, 3, 21),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 2,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 5, 12),
            'end_date': None,
            'status': RoyaltySplit.STATUS_CONFIRMED,
            'revision': 3,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 5, 12),
            'end_date': None,
            'status': RoyaltySplit.STATUS_PENDING,
            'revision': 3,
        },
    ]


def expected_splits_7(user1_id, user2_id, user3_id):
    return [
        {
            'user_id': user1_id,
            'rate': Decimal('0.6000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': None,
            'end_date': date(2020, 3, 20),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 1,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 3, 21),
            'end_date': date(2020, 5, 11),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 2,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.4000'),
            'start_date': date(2020, 3, 21),
            'end_date': date(2020, 5, 11),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 2,
        },
        {
            'user_id': user3_id,
            'rate': Decimal('0.1000'),
            'start_date': date(2020, 3, 21),
            'end_date': date(2020, 5, 11),
            'status': RoyaltySplit.STATUS_ARCHIVED,
            'revision': 2,
        },
        {
            'user_id': user1_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 5, 12),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 3,
        },
        {
            'user_id': user2_id,
            'rate': Decimal('0.5000'),
            'start_date': date(2020, 5, 12),
            'end_date': None,
            'status': RoyaltySplit.STATUS_ACTIVE,
            'revision': 3,
        },
    ]


splits_with_correct_rates = [
    {'royalty_splits__rate': Decimal('0.5500'), 'royalty_splits__revision': 1},
    {'royalty_splits__rate': Decimal('0.4500'), 'royalty_splits__revision': 1},
    {'royalty_splits__rate': Decimal('0.9900'), 'royalty_splits__revision': 2},
    {'royalty_splits__rate': Decimal('0.0100'), 'royalty_splits__revision': 2},
]
splits_with_incorrect_rates = [
    {'royalty_splits__rate': Decimal('0.5500'), 'royalty_splits__revision': 1},
    {'royalty_splits__rate': Decimal('0.4500'), 'royalty_splits__revision': 1},
    {'royalty_splits__rate': Decimal('1.0000'), 'royalty_splits__revision': 2},
    {'royalty_splits__rate': Decimal('0.5000'), 'royalty_splits__revision': 2},
]
splits_with_correct_is_owner_true = [
    {
        'release_owner_id': 1,
        'royalty_splits__user_id': 1,
        'royalty_splits__is_owner': True,
    }
]
splits_with_correct_is_owner_false = [
    {
        'release_owner_id': 1,
        'royalty_splits__user_id': 2,
        'royalty_splits__is_owner': False,
    }
]
splits_with_incorrect_is_owner_true = [
    {
        'release_owner_id': 999,
        'royalty_splits__user_id': 1,
        'royalty_splits__is_owner': True,
    }
]
splits_with_incorrect_is_owner_false = [
    {
        'release_owner_id': 1,
        'royalty_splits__user_id': 1,
        'royalty_splits__is_owner': False,
    }
]
splits_with_active_revision = [
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 2,
    },
]
splits_with_active_revision_2 = [
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_RELEASED,
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 1,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_RELEASED,
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 2,
    },
]
splits_with_active_revision_3 = [
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_TAKEDOWN,
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 1,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_TAKEDOWN,
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 1,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_TAKEDOWN,
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 2,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_TAKEDOWN,
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 2,
    },
]
splits_with_active_revision_4 = [
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 2,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 2,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 3,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 3,
    },
]
splits_with_no_active_revision = [
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 2,
    },
]
splits_with_no_active_revision_2 = [
    {
        'release__release_date': date(2019, 11, 18),
        'release__status': Release.STATUS_DELIVERED,
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 1,
    }
]
splits_with_incorrect_dates_1 = [
    {
        'royalty_splits__start_date': None,
        'royalty_splits__end_date': date(2020, 4, 21),
        'royalty_splits__revision': 1,
    }
]
splits_with_incorrect_dates_2 = [
    {
        'royalty_splits__start_date': date(2020, 4, 21),
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 1,
    }
]
splits_with_incorrect_dates_3 = [
    {
        'royalty_splits__start_date': date(2020, 4, 21),
        'royalty_splits__end_date': date(2019, 1, 1),
        'royalty_splits__revision': 1,
    }
]
splits_with_incorrect_dates_4 = [
    {
        'royalty_splits__start_date': None,
        'royalty_splits__end_date': date(2020, 1, 1),
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__start_date': date(2020, 1, 1),
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 2,
    },
]
splits_with_incorrect_dates_5 = [
    {
        'royalty_splits__start_date': None,
        'royalty_splits__end_date': date(2020, 1, 1),
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__start_date': date(2020, 1, 2),
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__start_date': date(2020, 1, 1),
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 2,
    },
]
splits_with_correct_dates_1 = [
    {
        'royalty_splits__start_date': None,
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 1,
    }
]
splits_with_correct_dates_2 = [
    {
        'royalty_splits__start_date': None,
        'royalty_splits__end_date': date(2020, 1, 1),
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__start_date': date(2020, 1, 2),
        'royalty_splits__end_date': date(2020, 2, 1),
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__start_date': date(2020, 1, 2),
        'royalty_splits__end_date': date(2020, 2, 1),
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__start_date': date(2020, 2, 2),
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 3,
    },
]
splits_with_correct_dates_3 = [
    {
        'royalty_splits__start_date': None,
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__start_date': date(2020, 1, 2),
        'royalty_splits__end_date': None,
        'royalty_splits__revision': 2,
    },
]
splits_with_correct_single_is_owner = [
    {'royalty_splits__revision': 1, 'royalty_splits__is_owner': True},
    {'royalty_splits__revision': 2, 'royalty_splits__is_owner': True},
    {'royalty_splits__revision': 2, 'royalty_splits__is_owner': False},
    {'royalty_splits__revision': 3, 'royalty_splits__is_owner': False},
]
splits_with_incorrect_multiple_is_owner = [
    {'royalty_splits__revision': 1, 'royalty_splits__is_owner': True},
    {'royalty_splits__revision': 2, 'royalty_splits__is_owner': True},
    {'royalty_splits__revision': 2, 'royalty_splits__is_owner': True},
    {'royalty_splits__revision': 3, 'royalty_splits__is_owner': True},
]
splits_with_correct_single_user_1 = [
    {'royalty_splits__user_id': 1, 'royalty_splits__revision': 1},
    {'royalty_splits__user_id': 2, 'royalty_splits__revision': 2},
]
splits_with_correct_single_user_2 = [
    {'royalty_splits__user_id': 1, 'royalty_splits__revision': 1},
    {'royalty_splits__user_id': None, 'royalty_splits__revision': 2},
]
splits_with_correct_no_user = [
    {'royalty_splits__user_id': None, 'royalty_splits__revision': 1},
    {'royalty_splits__user_id': None, 'royalty_splits__revision': 2},
]
splits_with_incorrect_multiple_user_1 = [
    {'royalty_splits__user_id': 1, 'royalty_splits__revision': 1},
    {'royalty_splits__user_id': 1, 'royalty_splits__revision': 1},
]
splits_with_incorrect_multiple_user_2 = [
    {'royalty_splits__user_id': 1, 'royalty_splits__revision': 1},
    {'royalty_splits__user_id': None, 'royalty_splits__revision': 2},
    {'royalty_splits__user_id': 2, 'royalty_splits__revision': 2},
    {'royalty_splits__user_id': 2, 'royalty_splits__revision': 2},
]
splits_with_correct_status_1 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 1,
    }
]
splits_with_correct_status_2 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 1,
    },
]
splits_with_correct_status_3 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 2,
    },
]
splits_with_correct_status_4 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 3,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 3,
    },
]
splits_with_correct_status_5 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 2,
    },
]
splits_with_correct_status_6 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 3,
    },
]
splits_with_correct_status_7 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 3,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 4,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 4,
    },
]
splits_with_correct_status_8 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 3,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 4,
    },
]
splits_with_incorrect_status_1 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    }
]
splits_with_incorrect_status_2 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 1,
    }
]
splits_with_incorrect_status_3 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_CONFIRMED,
        'royalty_splits__revision': 2,
    },
]
splits_with_incorrect_status_4 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 2,
    },
]
splits_with_incorrect_status_5 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 2,
    },
]
splits_with_incorrect_status_6 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_PENDING,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ACTIVE,
        'royalty_splits__revision': 3,
    },
]
splits_with_incorrect_status_7 = [
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 1,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 2,
    },
    {
        'royalty_splits__status': RoyaltySplit.STATUS_ARCHIVED,
        'royalty_splits__revision': 3,
    },
]
splits_with_correct_revisions_1 = [{'royalty_splits__revision': 1}]
splits_with_correct_revisions_2 = [
    {'royalty_splits__revision': 1},
    {'royalty_splits__revision': 2},
    {'royalty_splits__revision': 3},
]
splits_with_incorrect_revisions_1 = [{'royalty_splits__revision': 3}]
splits_with_incorrect_revisions_2 = [
    {'royalty_splits__revision': 1},
    {'royalty_splits__revision': 3},
    {'royalty_splits__revision': 4},
]
