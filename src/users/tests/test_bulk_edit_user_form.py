from unittest import mock

import pytest

from users.admin import BulkEditUserForm
from users.models import User, UserMetadata, Comments
from users.tests.factories import UserFactory, CommentsFactory

NOT_EDITED = '#$%'

is_edited = lambda value: value != NOT_EDITED
get_edited_value = lambda value: value if is_edited(value) else None


@pytest.mark.parametrize(
    "is_active, category, flagged_reason, is_frozen, comment",
    [
        (
            True,
            User.CATEGORY_FLAGGED,
            UserMetadata.FLAGGED_REASON_INFRINGEMENTS,
            True,
            'xy',
        ),
        (False, User.CATEGORY_FLAGGED, UserMetadata.FLAGGED_REASON_DMCA, False, 'xy'),
        (
            False,
            User.CATEGORY_FLAGGED,
            UserMetadata.FLAGGED_REASON_DMCA,
            False,
            NOT_EDITED,
        ),
        (False, User.CATEGORY_DEFAULT, None, False, NOT_EDITED),
        (True, NOT_EDITED, NOT_EDITED, False, 'xy'),
    ],
)
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_bulk_user_edit_form_success(
    _, is_active, category, flagged_reason, is_frozen, comment
):
    users = [UserFactory() for i in range(0, 3)]

    form = BulkEditUserForm(
        {
            'is_active_0': is_edited(is_active),
            'is_active_1': get_edited_value(is_active),
            'category_0': is_edited(category),
            'category_1': get_edited_value(category),
            'flagged_reason_0': is_edited(flagged_reason),
            'flagged_reason_1': get_edited_value(flagged_reason),
            'comment_0': is_edited(comment),
            'comment_1': get_edited_value(comment),
            'is_frozen_0': is_edited(is_frozen),
            'is_frozen_1': get_edited_value(is_frozen),
            'objects': users,
        }
    )

    assert form.is_valid() is True
    form.bulk_update(None, User.objects.all())

    for index, user in enumerate(User.objects.all()):
        # test is_active
        assert user.is_active == is_active

        # test category
        if is_edited(category):
            assert user.category == category
        else:
            assert user.category == users[index].category

        # test is_frozen
        assert user.is_frozen == is_frozen

        # test flagged_reason
        user_meta = UserMetadata.objects.filter(user=user).first()
        if is_edited(flagged_reason):
            assert user_meta is not None
            assert user_meta.flagged_reason == flagged_reason
        else:
            assert user_meta is None

        # test comment
        user_comment = Comments.objects.filter(user=user).first()
        if is_edited(comment):
            assert user_comment is not None
            assert user_comment.text == comment
        else:
            assert user_comment is None


@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_bulk_user_edit_form_success_append_comment(_):
    users = [UserFactory() for i in range(0, 3)]
    comment = CommentsFactory(user=users[0], text='abc')

    form = BulkEditUserForm({'comment_0': True, 'comment_1': 'xy', 'objects': users})

    assert form.is_valid() is True
    form.bulk_update(None, User.objects.all())

    comments = Comments.objects.filter(user__in=users).all()
    assert len(comments) == 3
    for item in comments:
        if item.user == users[0]:
            assert item.text == 'abc\nxy'
        else:
            assert item.text == 'xy'


@pytest.mark.parametrize(
    "category, flagged_reason",
    [
        (NOT_EDITED, UserMetadata.FLAGGED_REASON_INFRINGEMENTS),
        (User.CATEGORY_FLAGGED, NOT_EDITED),
        (User.CATEGORY_DEFAULT, UserMetadata.FLAGGED_REASON_INFRINGEMENTS),
        (User.CATEGORY_QUALIFIED, NOT_EDITED),
    ],
)
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_bulk_user_edit_form_category_rule_errors(_, category, flagged_reason):
    users = [UserFactory() for i in range(0, 3)]

    form = BulkEditUserForm(
        {
            'category_0': is_edited(category),
            'category_1': get_edited_value(category),
            'flagged_reason_0': is_edited(flagged_reason),
            'flagged_reason_1': get_edited_value(flagged_reason),
            'comment_0': False,
            'comment_1': None,
            'is_frozen_0': False,
            'is_frozen_1': None,
            'objects': users,
        }
    )

    assert form.is_valid() is False
    assert len(form.errors) == 1
