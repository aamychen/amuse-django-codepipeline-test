from unittest import mock

import pytest
from django.forms import CharField as CF, ValidationError

from users.bulk_edit_form import BulkEditForm, BulkEditField as BEF, BulkEditWidget
from users.models import User
from users.tests.factories import UserFactory


class SampleForm(BulkEditForm):
    comment = BEF(CF(required=False))

    def clean_comment(self):
        if self.cleaned_data['comment'] == 'x':
            raise ValidationError('comment error')
        return self.cleaned_data['comment']


@pytest.mark.parametrize(
    "description, is_valid, cleaned_data, expected_call_count",
    [
        ('Do not update if form is not valid', False, {'first_name': ''}, 0),
        ('Do not update if cleaned_data is empty', True, {}, 0),
        ('Update', True, {'first_name': 'Bugs Bunny'}, 1),
    ],
)
@mock.patch('users.models.User.objects.bulk_update')
@mock.patch.object(BulkEditForm, "is_valid")
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_bulk_edit_form_bulk_update_method(
    _,
    mock_is_valid,
    mock_bulk_update,
    description,
    is_valid,
    cleaned_data,
    expected_call_count,
):
    mock_is_valid.return_value = is_valid
    UserFactory(first_name='abc')

    form = BulkEditForm()
    form.cleaned_data = cleaned_data

    form.bulk_update(None, User.objects.all())
    assert mock_bulk_update.call_count == expected_call_count


@pytest.mark.parametrize(
    "description, field, value, expected",
    [
        ('True if not BulkEditField', CF(), None, True),
        ('False if disabled BulkEditField', BEF(CF(), disabled=True), None, False),
        ('True if value is number (not a list)', BEF(CF()), 1, True),
        ('True if value is string (not a list)', BEF(CF()), '123', True),
        ('True if value is tuple (not a list)', BEF(CF()), (1, 2), True),
        ('True if value is dict (not a list)', BEF(CF()), {}, True),
        ('True if value is None (not a list)', BEF(CF()), None, True),
        ('True if first element of value list is True', BEF(CF()), [True, None], True),
        (
            'False if first element of value list is False',
            BEF(CF()),
            [False, None],
            False,
        ),
    ],
)
@mock.patch("django.db.models.signals.ModelSignal.send")
@pytest.mark.django_db
def test_bulk_edit_form_should_perform_field_clean_method(
    _, description, field, value, expected
):
    form = BulkEditForm()
    actual = form._should_perform_field_clean(field, value)
    assert actual == expected


@pytest.mark.parametrize(
    "description, value, expected",
    [
        ('Return original value if value is not list', '123', '123'),
        ('Return original value if value is list of single element', ['12'], ['12']),
        ('Return value[1] if value is list', ['12', '34'], '34'),
    ],
)
def test_bulk_edit_field_prepare_value_method(description, value, expected):
    actual = BEF(CF()).prepare_value(value)
    assert actual == expected


@pytest.mark.parametrize(
    "description, value, expected",
    [
        ('Return None if value is not list', '123', None),
        ('Return None if value is list of single element', ['12'], None),
        ('Return None if first element is False', [False, '123'], None),
        ('Return second element of array if first element is True', [True, 'x'], 'x'),
    ],
)
def test_bulk_edit_field_compress_method(description, value, expected):
    actual = BEF(CF()).compress(value)
    assert actual == expected


@pytest.mark.parametrize(
    "description, value, expected",
    [
        ('Return [False, 12] if value is not None (value is 12)', 12, [False, 12]),
        ('Return [None, None] if value is None', None, [None, None]),
    ],
)
def test_bulk_edit_widget_decompress_method(description, value, expected):
    actual = BulkEditWidget(widgets=[CF(), CF()]).decompress(value)
    assert actual == expected


def test_bulk_edit_clean_fields_checked():
    """Form checked values should appear in cleaned_data"""
    form = SampleForm({'comment_0': True, 'comment_1': 'abc'})
    form.cleaned_data = dict()
    form._clean_fields()

    assert len(form.errors) == 0
    assert 'comment' in form.cleaned_data
    assert form.cleaned_data['comment'] == 'abc'


def test_bulk_edit_clean_fields_unchecked():
    """Form unchecked values should not appear in cleaned_data"""
    form = SampleForm({'comment_0': False, 'comment_1': 'abc'})
    form.cleaned_data = dict()
    form._clean_fields()

    assert 'comment' not in form.cleaned_data


def test_bulk_edit_clean_fields_validation_error():
    """If clean() method throws an Exception, it should be stored to form.errors collection"""
    form = SampleForm({'comment_0': True, 'comment_1': 'x'})
    form.cleaned_data = dict()
    form._clean_fields()

    assert len(form.errors) == 1
    assert form.errors['comment'][0] == 'comment error'


def test_bulk_edit_clean_fields_disabled():
    """Test disabled field. Value should not be in cleaned_data"""
    form = SampleForm({'comment_0': True, 'comment_1': 'abc'})
    form.fields['comment'].disabled = True
    form.cleaned_data = dict()
    form._clean_fields()

    assert 'comment' not in form.cleaned_data
