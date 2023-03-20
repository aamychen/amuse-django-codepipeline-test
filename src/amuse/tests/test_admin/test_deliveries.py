from unittest import mock

import pytest

from amuse.admin import (
    remove_duplicated_deliveries,
    remove_invalid_checksum_deliveries,
    remove_legacy_deliveries,
    remove_unsupported_release_statuses,
)
from amuse.deliveries import FUGA, SPOTIFY
from amuse.tests.factories import (
    BatchFactory,
    BatchDeliveryFactory,
    BatchDeliveryReleaseFactory,
)
from amuse.models.deliveries import BatchDeliveryRelease
from releases.models import Release
from releases.tests.factories import CoverArtFactory, ReleaseFactory


@pytest.mark.django_db
@mock.patch("amuse.admin._calculate_django_file_checksum", return_value="invalid")
@mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
def test_remove_invalid_checksum_deliveries(mock_create, mock_checksum):
    release = ReleaseFactory()
    CoverArtFactory(release=release)

    batch_1 = BatchFactory()
    batch_delivery_1 = BatchDeliveryFactory(batch=batch_1, channel=SPOTIFY)
    batch_2 = BatchFactory()
    batch_delivery_2 = BatchDeliveryFactory(batch=batch_2, channel=SPOTIFY)

    bdr_1 = BatchDeliveryReleaseFactory(
        release=release,
        redeliver=True,
        delivery=batch_delivery_1,
        type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
    )
    bdr_2 = BatchDeliveryReleaseFactory(
        release=release,
        redeliver=True,
        delivery=batch_delivery_2,
        type=BatchDeliveryRelease.DELIVERY_TYPE_UPDATE,
    )

    bdrs = BatchDeliveryRelease.objects.filter(redeliver=True)
    assert bdrs.count() == 2

    bdrs_no_dupes = remove_invalid_checksum_deliveries(bdrs, mock.Mock())
    assert bdrs_no_dupes.count() == 0


@pytest.mark.django_db
@mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
def test_remove_duplicated_deliveries(_):
    release_1 = ReleaseFactory()
    release_2 = ReleaseFactory()

    batch = BatchFactory()
    batch_delivery = BatchDeliveryFactory(batch=batch, channel=SPOTIFY)

    bdr_1 = BatchDeliveryReleaseFactory(
        release=release_1,
        redeliver=True,
        delivery=batch_delivery,
        type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
    )
    bdr_2 = BatchDeliveryReleaseFactory(
        release=release_1,
        redeliver=True,
        delivery=batch_delivery,
        type=BatchDeliveryRelease.DELIVERY_TYPE_UPDATE,
    )
    bdr_3 = BatchDeliveryReleaseFactory(
        release=release_2,
        redeliver=True,
        delivery=batch_delivery,
        type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
    )

    bdrs = BatchDeliveryRelease.objects.filter(redeliver=True)
    assert bdrs.count() == 3

    bdrs_no_dupes = remove_duplicated_deliveries(bdrs, mock.Mock())
    assert bdrs_no_dupes.count() == 2
    assert bdrs_no_dupes.filter(id__in=[bdr_2.id, bdr_3.id]).count() == 2


@pytest.mark.django_db
@mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
def test_remove_unsupported_release_statuses(_):
    release_1 = ReleaseFactory(status=Release.STATUS_DELIVERED)
    release_2 = ReleaseFactory(status=Release.STATUS_TAKEDOWN)

    batch = BatchFactory()
    batch_delivery = BatchDeliveryFactory(batch=batch, channel=SPOTIFY)

    bdr_1 = BatchDeliveryReleaseFactory(
        release=release_1,
        redeliver=True,
        delivery=batch_delivery,
        type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
    )
    bdr_2 = BatchDeliveryReleaseFactory(
        release=release_2,
        redeliver=True,
        delivery=batch_delivery,
        type=BatchDeliveryRelease.DELIVERY_TYPE_TAKEDOWN,
    )

    bdrs = BatchDeliveryRelease.objects.filter(redeliver=True)
    assert bdrs.count() == 2

    bdrs_no_unsupported = remove_unsupported_release_statuses(bdrs, mock.Mock())
    assert bdrs_no_unsupported.count() == 1
    assert bdrs_no_unsupported.get(id=bdr_1.id)


@pytest.mark.django_db
@mock.patch("amuse.tasks.zendesk_create_or_update_user", return_value=mock.Mock())
def test_remove_legacy_deliveries(_):
    release_1 = ReleaseFactory(status=Release.STATUS_DELIVERED)
    release_2 = ReleaseFactory(status=Release.STATUS_DELIVERED)

    batch = BatchFactory()
    batch_delivery = BatchDeliveryFactory(batch=batch, channel=FUGA)

    bdr_1 = BatchDeliveryReleaseFactory(
        release=release_1,
        redeliver=True,
        delivery=batch_delivery,
        type=BatchDeliveryRelease.DELIVERY_TYPE_UPDATE,
    )
    bdr_2 = BatchDeliveryReleaseFactory(
        release=release_2,
        redeliver=True,
        delivery=batch_delivery,
        type=BatchDeliveryRelease.DELIVERY_TYPE_INSERT,
    )

    bdrs = BatchDeliveryRelease.objects.filter(redeliver=True)
    assert bdrs.count() == 2

    bdrs_no_unsupported = remove_legacy_deliveries(bdrs, mock.Mock())
    assert bdrs_no_unsupported.count() == 1
    assert bdrs_no_unsupported.get(id=bdr_1.id)
