from django.test import TestCase

from contenttollgate.forms import ReleaseForm, SongForm
from releases.models import Release, Store
from releases.tests.factories import GenreFactory, StoreFactory


class ReleaseFormTest(TestCase):
    def setUp(self):
        StoreFactory()
        self.stores = Store.objects.all()
        self.data = {
            "name": "blaha",
            "label": "blabla",
            "release_version": 0,
            "type": 2,
            "release_date": "1998-01-01",
            "original_release_date": "1995-01-31",
            "genre": GenreFactory().pk,
            "status": 4,
            "stores": [store.pk for store in self.stores],
        }

    def test_no_error_flags_is_valid(self):
        self.data["error_flags"] = []
        assert ReleaseForm(self.data, stores_queryset=self.stores).is_valid()

    def test_allowed_error_flags_is_valid(self):
        self.data["error_flags"] = ["metadata_symbols-emoji-info"]
        assert ReleaseForm(self.data, stores_queryset=self.stores).is_valid()

        self.data["error_flags"] = ["release_date-changed"]
        assert ReleaseForm(self.data, stores_queryset=self.stores).is_valid()

        self.data["error_flags"] = [
            "metadata_symbols-emoji-info",
            "release_date-changed",
        ]
        assert ReleaseForm(self.data, stores_queryset=self.stores).is_valid()

    def test_disallowed_error_flags_raises_error(self):
        self.data["error_flags"] = ["artwork_blurry", "rights_no-rights"]
        form = ReleaseForm(self.data, stores_queryset=self.stores)

        assert form.is_valid() is False
        assert (
            form.non_field_errors()[0] == "Error flags not allowed for status Approved"
        )

    def test_error_flags_not_validated_on_other_status(self):
        self.data["status"] = 2
        self.data["error_flags"] = ["release_underage"]
        assert ReleaseForm(self.data, stores_queryset=self.stores).is_valid()

    def test_no_stores_raises_error(self):
        self.data["stores"] = []
        form = ReleaseForm(self.data, stores_queryset=self.stores)

        assert form.is_valid() is False
        assert form.non_field_errors()[0] == "No stores not allowed for status Approved"

    def test_no_stores_not_validated_on_other_status(self):
        self.data["stores"] = []
        self.data["status"] = 2
        assert ReleaseForm(self.data, stores_queryset=self.stores).is_valid()


class SongFormTest(TestCase):
    def setUp(self):
        self.data = {
            "name": "blaha",
            "sequence": 1,
            "recording_year": "1998",
            "genre": GenreFactory().pk,
            "explicit": 0,
            "origin": 1,
            "youtube_content_id": 0,
            "release-status": str(Release.STATUS_APPROVED),
        }

    def test_no_error_flags_is_valid(self):
        self.data["error_flags"] = []
        assert SongForm(self.data).is_valid()

    def test_allowed_error_flags_is_valid(self):
        self.data["error_flags"] = ["explicit_lyrics"]
        assert SongForm(self.data).is_valid()

    def test_disallowed_error_flags_raises_error(self):
        self.data["error_flags"] = ["wrong-isrc", "rights_remix"]
        form = SongForm(self.data)

        assert form.is_valid() is False
        assert (
            form.non_field_errors()[0] == "Error flags not allowed for status Approved"
        )

    def test_error_flags_not_validated_on_other_status(self):
        self.data["release-status"] = Release.STATUS_NOT_APPROVED
        self.data["error_flags"] = ["wrong-isrc"]
        assert SongForm(self.data).is_valid()
