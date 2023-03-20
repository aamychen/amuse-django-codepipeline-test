import logging

from django.db import IntegrityError, connection

from amuse.models.support import SupportEvent, SupportRelease
from releases.models.release import Release
from subscriptions.models import Subscription, SubscriptionPlan
from users.models import User

logger = logging.getLogger(__name__)


def sort_order_field(field):
    return {
        'created_date': 'created',
        'release_date': 'release_date',
        'updated_date': 'updated',
    }[field]


def count_pending_releases(tier=User.TIER_FREE):
    if tier == User.TIER_FREE:  # free release filtering stays the same as before
        sql = """SELECT COUNT(1)
                 FROM releases_release r
                 INNER JOIN users_user u ON (r.created_by_id = u.id)
                 WHERE r.status = %s
                 AND (
                    SELECT COUNT(*)
                    FROM subscriptions_subscription s
                    WHERE s.user_id = u.id
                    AND s.status IN (%s, %s, %s)
                    AND r.created BETWEEN s.valid_from AND COALESCE(CASE WHEN s.valid_until IS NOT NULL THEN s.grace_period_until ELSE NULL END, s.valid_until, now())
                 ) = 0
                 AND (
                    SELECT COUNT(*)
                    FROM amuse_supportrelease sr
                    WHERE sr.release_id = r.id
                 ) = 0"""
    else:  # add tier filtering to original sql
        sql = """SELECT COUNT(1)
                 FROM releases_release r
                 INNER JOIN users_user u ON (r.created_by_id = u.id)
                 WHERE r.status = %s
                 AND (
                    SELECT COUNT(*)
                    FROM subscriptions_subscription s
                    INNER JOIN subscriptions_subscriptionplan sp ON (s.plan_id = sp.id)
                    WHERE s.user_id = u.id
                    AND s.status IN (%s, %s, %s)
                    AND sp.tier = {0}
                    AND r.created BETWEEN s.valid_from AND COALESCE(CASE WHEN s.valid_until IS NOT NULL THEN s.grace_period_until ELSE NULL END, s.valid_until, now())
                 ) >= 1
                 AND (
                    SELECT COUNT(*)
                    FROM amuse_supportrelease sr
                    WHERE sr.release_id = r.id
                 ) = 0""".format(
            tier
        )
    with connection.cursor() as c:
        c.execute(
            sql,
            [
                Release.STATUS_PENDING,
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_GRACE_PERIOD,
                Subscription.STATUS_EXPIRED,
            ],
        )
        result = c.fetchone()
        return result[0]


def count_prepared_releases(tier=User.TIER_FREE):
    if tier == User.TIER_FREE:  # free release filtering stays the same as before
        sql = """SELECT COUNT(*)
                 FROM releases_release r
                 INNER JOIN users_user u ON (r.created_by_id = u.id)
                 WHERE r.status = %s
                 AND (
                    SELECT COUNT(*)
                    FROM subscriptions_subscription s
                    WHERE s.user_id = u.id
                    AND s.status IN (%s, %s, %s)
                    AND r.created BETWEEN s.valid_from AND COALESCE(CASE WHEN s.valid_until IS NOT NULL THEN s.grace_period_until ELSE NULL END, s.valid_until, now())
                 ) = 0
                 AND (
                    SELECT COUNT(*)
                    FROM amuse_supportrelease sr
                    WHERE sr.release_id = r.id
                    AND sr.prepared = 't'
                 ) = 1
                 AND (
                    SELECT COUNT(*)
                    FROM amuse_supportevent se
                    WHERE se.release_id = r.id
                    AND se.event = %s
                 ) = 1"""
    else:  # add tier filtering to original sql
        sql = """SELECT COUNT(*)
                 FROM releases_release r
                 INNER JOIN users_user u ON (r.created_by_id = u.id)
                 WHERE r.status = %s
                 AND (
                    SELECT COUNT(*)
                    FROM subscriptions_subscription s
                    INNER JOIN subscriptions_subscriptionplan sp ON (s.plan_id = sp.id)
                    WHERE s.user_id = u.id
                    AND s.status IN (%s, %s, %s)
                    AND sp.tier = {0}
                    AND r.created BETWEEN s.valid_from AND COALESCE(CASE WHEN s.valid_until IS NOT NULL THEN s.grace_period_until ELSE NULL END, s.valid_until, now())
                 ) = 1
                 AND (
                    SELECT COUNT(*)
                    FROM amuse_supportrelease sr
                    WHERE sr.release_id = r.id
                    AND sr.prepared = 't'
                 ) = 1
                 AND (
                    SELECT COUNT(*)
                    FROM amuse_supportevent se
                    WHERE se.release_id = r.id
                    AND se.event = %s
                 ) = 1""".format(
            tier
        )

    with connection.cursor() as c:
        c.execute(
            sql,
            [
                Release.STATUS_PENDING,
                Subscription.STATUS_ACTIVE,
                Subscription.STATUS_GRACE_PERIOD,
                Subscription.STATUS_EXPIRED,
                SupportEvent.ASSIGNED,
            ],
        )
        return c.fetchone()[0]


def assign_pending_releases(
    count, user, sorting, tier=User.TIER_FREE, release_type=None, language=None
):
    sql = build_query(count, user, "pending", sorting, tier, release_type, language)
    releases = Release.objects.raw(sql)

    support_releases = []

    try:
        count = 0
        for release in releases:
            count += 1
            support_releases.append(
                SupportRelease.objects.create(release=release, assignee=user)
            )
            SupportEvent.objects.create(
                event=SupportEvent.ASSIGNED, release=release, user=user
            )
            has_subscription = release.user.has_subscription_for_date(release.created)
            tier_is_not_free = tier != User.TIER_FREE
            if has_subscription != tier_is_not_free:
                user_tier = release.user.get_tier_for_date(release.created)
                if user_tier == SubscriptionPlan.TIER_PRO:
                    release_type = 'pro'
                elif user_tier == SubscriptionPlan.TIER_PLUS:
                    release_type = 'plus'
                else:
                    release_type = 'free'

                if tier == SubscriptionPlan.TIER_PLUS:
                    assignment_type = 'plus'
                elif tier == SubscriptionPlan.TIER_PRO:
                    assignment_type = 'pro'
                else:
                    assignment_type = 'free'

                logger.info(
                    f'Pending {assignment_type} release ({release.id}:{release_type}) was assigned to {user.id}'
                )
        return count
    except IntegrityError:
        return len(support_releases)


def assign_prepared_releases(
    count, user, sorting, tier=User.TIER_FREE, release_type=None, language=None
):
    sql = build_query(count, user, "prepared", sorting, tier, release_type, language)
    releases = Release.objects.raw(sql)

    count = 0
    for release in releases:
        count += 1
        release.supportrelease.assignee = user
        release.supportrelease.save()
        SupportEvent.objects.create(
            event=SupportEvent.ASSIGNED, release=release, user=user
        )
        has_subscription = release.user.has_subscription_for_date(release.created)
        tier_is_not_free = tier != User.TIER_FREE
        if has_subscription != tier_is_not_free:
            user_tier = release.user.get_tier_for_date(release.created)
            if user_tier == SubscriptionPlan.TIER_PRO:
                release_type = 'pro'
            elif user_tier == SubscriptionPlan.TIER_PLUS:
                release_type = 'plus'
            else:
                release_type = 'free'

            if tier == SubscriptionPlan.TIER_PLUS:
                assignment_type = 'plus'
            elif tier == SubscriptionPlan.TIER_PRO:
                assignment_type = 'pro'
            else:
                assignment_type = 'free'
            logger.info(
                f'Prepared {assignment_type} release ({release.id}:{release_type}) was assigned to {user.id}'
            )
    return count


def release_status_change_event(release, old_status, new_status):
    if not hasattr(release, 'supportrelease'):
        return

    if old_status == Release.STATUS_PENDING and new_status in (
        Release.STATUS_APPROVED,
        Release.STATUS_NOT_APPROVED,
    ):
        event = (
            SupportEvent.APPROVED
            if new_status == Release.STATUS_APPROVED
            else SupportEvent.REJECTED
        )
        SupportEvent.objects.create(
            event=event, release=release, user=release.supportrelease.assignee
        )


def build_query(count, user, status, sorting, tier, release_type, language):
    query = f"""SELECT *
             FROM releases_release r
             INNER JOIN users_user u ON (r.created_by_id = u.id)
             WHERE r.status = {Release.STATUS_PENDING} """

    if release_type == Release.TYPE_SINGLE:
        query += f" AND r.type = {Release.TYPE_SINGLE} "

    elif release_type in (Release.TYPE_EP, Release.TYPE_ALBUM):
        query += f" AND r.type IN ({Release.TYPE_EP}, {Release.TYPE_ALBUM}) "

    if tier == User.TIER_FREE:
        query += f"""
                    AND (
                    SELECT COUNT(*)
                    FROM subscriptions_subscription s
                    WHERE s.user_id = u.id
                    AND s.status IN ({Subscription.STATUS_ACTIVE}, {Subscription.STATUS_GRACE_PERIOD}, {Subscription.STATUS_EXPIRED})
                    AND r.created BETWEEN s.valid_from AND COALESCE(CASE WHEN s.valid_until IS NOT NULL THEN s.grace_period_until ELSE NULL END, s.valid_until, now())
                    ) = 0
                """
    else:
        query += f"""
                    AND (
                    SELECT COUNT(*)
                    FROM subscriptions_subscription s
                    INNER JOIN subscriptions_subscriptionplan sp ON (s.plan_id = sp.id)
                    WHERE s.user_id = u.id
                    AND s.status IN ({Subscription.STATUS_ACTIVE}, {Subscription.STATUS_GRACE_PERIOD}, {Subscription.STATUS_EXPIRED})
                    AND sp.tier = {tier}
                    AND r.created BETWEEN s.valid_from AND COALESCE(CASE WHEN s.valid_until IS NOT NULL THEN s.grace_period_until ELSE NULL END, s.valid_until, now())
                    ) >= 1
                """

    if language == "spanish":
        query += f"""
                AND meta_language_id IN (
                SELECT id
                FROM releases_metadatalanguage
                WHERE iso_639_1 = 'es'
                )
                """

    elif language == "non-spanish":
        query += f"""
                AND meta_language_id NOT IN (
                SELECT id
                FROM releases_metadatalanguage
                WHERE iso_639_1 = 'es'
                )
                """

    if status == "prepared":
        query += f"""
                     AND (
                        SELECT COUNT(*)
                        FROM amuse_supportrelease sr
                        WHERE sr.release_id = r.id
                        AND sr.prepared = 't'
                     ) = 1
                     AND (
                        SELECT COUNT(*)
                        FROM amuse_supportevent se
                        WHERE se.release_id = r.id
                        AND se.event = {SupportEvent.ASSIGNED}
                     ) = 1
                    """
    else:  # if not prepared only assign pending releases
        query += """
                     AND (
                        SELECT COUNT(*)
                        FROM amuse_supportrelease sr
                        WHERE sr.release_id = r.id
                     ) = 0
                 """

    query += f"""
             ORDER BY r.{sort_order_field(sorting)}
             LIMIT {count}
             """

    return query
