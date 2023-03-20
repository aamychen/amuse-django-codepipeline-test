import pytest
import string
from amuse import blacklist
from releases.models import BlacklistedArtistName


@pytest.fixture
def blacklisted_artist_name():
    names = [
        'Marília Mendonça',
        'Jessie Reyez',
        'Zoé',
        'Beyoncé',
        'Ed Sheeran',
        'Coldplay',
        'The Shadows',
        'The Who',
    ]
    [BlacklistedArtistName.objects.create(name=name) for name in names]


@pytest.mark.django_db
def test_finds_blacklisted_text(blacklisted_artist_name):
    assert blacklist.find('Marília Mendonça') == 'Marília Mendonça'


@pytest.mark.django_db
def test_finds_blacklisted_lowercase_text(blacklisted_artist_name):
    assert blacklist.find('jessie reyez') == 'Jessie Reyez'


@pytest.mark.django_db
def test_finds_blacklisted_diacritic(blacklisted_artist_name):
    assert blacklist.find('ZOÉ') == 'Zoé'


@pytest.mark.django_db
def test_finds_provided_examples(blacklisted_artist_name):
    assert blacklist.find('Beyoncé') == 'Beyoncé'
    assert blacklist.find('Beyonce') == 'Beyoncé'
    assert blacklist.find('Be yonce') == 'Beyoncé'
    assert blacklist.find('beyoncé') == 'Beyoncé'
    assert blacklist.find('Be “Y” Once') == 'Beyoncé'
    assert blacklist.find('Ed Sheeran') == 'Ed Sheeran'
    assert blacklist.find('The Coldplay') == 'Coldplay'
    assert blacklist.find('Shadows') == 'The Shadows'
    assert blacklist.find('W.H.O.') == 'The Who'
