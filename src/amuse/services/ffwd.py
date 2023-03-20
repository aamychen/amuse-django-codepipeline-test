from releases.models import RoyaltySplit


def unlock_splits(split_ids):
    RoyaltySplit.objects.filter(pk__in=split_ids).update(is_locked=False)
