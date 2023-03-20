import hashlib
from os import path
from django.test import TestCase
from ..models import generate_thumb


def fixture(name):
    return path.join(path.dirname(__file__), 'fixtures', name)


def write_fixture(readable, name):
    with open(fixture(name), 'wb') as outfile:
        outfile.write(readable.read())


class ImageTestCase(TestCase):
    def assertFilesEqual(self, readable1, readable2):
        self.assertEqual(
            str(hashlib.sha1(readable1.read()).hexdigest),
            str(hashlib.sha1(readable2.read()).hexdigest),
        )

    def test_generate_jpeg_thumb_with_preserved_ratio(self):
        input_image = open(fixture('image_rgb.jpg'), 'rb')
        output_image = generate_thumb(input_image, (640, 640), True, 'JPEG')
        self.assertFilesEqual(
            output_image, open(fixture('640_preserved_ratio.jpg'), 'rb')
        )

    def test_generate_jpeg_thumb_without_preserved_ratio(self):
        input_image = open(fixture('image_rgb.jpg'), 'rb')
        output_image = generate_thumb(input_image, (640, 640), False, 'JPEG')
        self.assertFilesEqual(
            output_image, open(fixture('640_no_preserved_ratio.jpg'), 'rb')
        )

    def test_generate_jpeg_thumb_from_cmyk(self):
        input_image = open(fixture('image_cmyk.jpg'), 'rb')
        output_image = generate_thumb(input_image, (640, 640), True, 'JPEG')
        self.assertFilesEqual(
            output_image, open(fixture('640_preserved_ratio.jpg'), 'rb')
        )

    def test_generate_png_thumb_with_preserved_ratio(self):
        input_image = open(fixture('image_rgb.jpg'), 'rb')
        output_image = generate_thumb(input_image, (640, 640), True, 'PNG')
        self.assertFilesEqual(
            output_image, open(fixture('640_preserved_ratio.png'), 'rb')
        )

    def test_generate_png_thumb_without_preserved_ratio(self):
        input_image = open(fixture('image_rgb.jpg'), 'rb')
        output_image = generate_thumb(input_image, (640, 640), False, 'PNG')
        self.assertFilesEqual(
            output_image, open(fixture('640_no_preserved_ratio.png'), 'rb')
        )

    def test_generate_png_thumb_from_cmyk(self):
        input_image = open(fixture('image_cmyk.jpg'), 'rb')
        output_image = generate_thumb(input_image, (640, 640), True, 'PNG')
        self.assertFilesEqual(
            output_image, open(fixture('640_preserved_ratio.png'), 'rb')
        )

    def test_standard_sizes_quality_level(self):
        standard_sizes = [(200, 200), (400, 400), (800, 800)]

        input_image = open(fixture('Reyn_Lowkey_Artwork_Final.jpg'), 'rb')

        for size in standard_sizes:
            filename = f'standard_{size[0]}x{size[1]}.jpg'
            output_image = generate_thumb(input_image, size, True, 'JPEG')
            # write_fixture(output_image, filename)

            self.assertFilesEqual(output_image, open(fixture(filename), 'rb'))
