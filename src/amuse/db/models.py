import io
from PIL import Image, ImageOps
from amuse.models import Image as ImageModel
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import ImageField
from django.db.models.fields.files import ImageFieldFile

# Value determined by ocular inspection of a coverart
# provided by the Product Team. Source coverart and derivatives
# can be found in the test for this module.
IMAGE_QUALITY_LEVEL = 92

# Generate thumbnails when saving objects.
# Default: True
THUMBS_GENERATE_THUMBNAILS = getattr(settings, "THUMBS_GENERATE_THUMBNAILS", True)

# Generate thumbnail when its url is accessed and the the file doesn't exist.
# Set this option when you are replacing ImageField with ImageWithThumbsField on a populated database where the thumbnails doesn't exist.
# Default: True
THUMBS_GENERATE_MISSING_THUMBNAILS = getattr(
    settings, "THUMBS_GENERATE_MISSING_THUMBNAILS", True
)


def generate_thumb(original, size, preserve_ratio, image_format='JPEG'):
    """Generates a thumbnail image and returns a ContentFile object with the thumbnail

    :param original: The image being resized as `File`.
    :param size: Desired thumbnail size as `tuple`. Example: (70, 100)
    :param preserve_ratio: True if the thumbnail is to keep the aspect ratio of the full image
    :param image_format: Format of the original image ('JPEG', 'PNG', ...) The thumbnail will be generated using this same image_format.
    :returns: ContentFile object with the thumbnail
    """
    original.seek(0)  # see http://code.djangoproject.com/ticket/8222 for details
    image = Image.open(original)
    if image.mode not in ('L', 'RGB'):
        image = image.convert('RGB')
    if preserve_ratio:
        image.thumbnail(size, Image.ANTIALIAS)
    else:
        image = ImageOps.fit(image, size, Image.ANTIALIAS)
    zo = io.BytesIO()
    if image_format.upper() == 'JPG':
        image_format = 'JPEG'
    image.save(zo, image_format, quality=IMAGE_QUALITY_LEVEL)
    return ContentFile(zo.getvalue())


class ImageWithThumbsFieldFile(ImageFieldFile):
    """Django `ImageField` replacement with automatic generation of thumbnail images.
    See `ImageWithThumbsField` for usage example.

    """

    THUMB_SUFFIX = '%s.%sx%s.%s'

    def __init__(self, *args, **kwargs):
        super(ImageFieldFile, self).__init__(*args, **kwargs)

    def _url_for_size(self, size):
        """Return a URL pointing to the thumbnail image of the requested size.
        If `THUMBS_GENERATE_MISSING_THUMBNAILS` is True, the thumbnail will be created if it doesn't exist on disk.

        :param size: A tuple with the desired width and height. Example: (100, 100)

        """
        if not self:
            return ''
        else:
            # generate missing thumbnail if needed
            fileBase, extension = self.name.rsplit('.', 1)
            thumb_file = self.THUMB_SUFFIX % (fileBase, size[0], size[1], extension)
            if THUMBS_GENERATE_MISSING_THUMBNAILS:
                if not self.storage.exists(thumb_file):
                    try:
                        self._generate_thumb(self.storage.open(self.name), size)
                    except Exception:
                        if settings.DEBUG:
                            raise
            return self.storage.url(thumb_file)

    def __getattr__(self, name):
        """Return the url for the requested size.

        :param name: The field `url` with size suffix formatted as _WxH. Example: instance.url_100x70

        """
        if "url_" not in name:
            return getattr(super(ImageFieldFile), name)
        sizeStr = name.replace("url_", "")
        width, height = sizeStr.split("x")
        requestedSize = (int(width), int(height))
        acceptedSize = None
        for configuredSize in self.field.sizes:
            # FIXME: fuzzy search, accept nearest size
            if requestedSize == configuredSize:
                acceptedSize = requestedSize
        if acceptedSize is not None:
            return self._url_for_size(acceptedSize)
        raise ValueError("The requested thumbnail size %s doesn't exist" % sizeStr)

    def _generate_thumb(self, image, size, force_format=None):
        """Generates a thumbnail of `size`.
        :param image: An `File` object with the image in its original size.
        :param size: A tuple with the desired width and height. Example: (100, 100)
        """
        base, extension = self.name.rsplit('.', 1)
        if force_format:
            extension = force_format

        thumb_name = self.THUMB_SUFFIX % (base, size[0], size[1], extension)
        thumbnail = generate_thumb(image, size, self.field.preserve_ratio, extension)
        saved_as = self.storage.save(thumb_name, thumbnail)
        if thumb_name != saved_as:
            raise ValueError('There is already a file named %s' % thumb_name)

        return ImageModel(
            path=thumb_name,
            mime=f'image/{extension}',
            size=len(thumbnail),
            width=size[0],
            height=size[1],
        )

    def save(self, name, content, save=True):
        super(ImageFieldFile, self).save(name, content, save)
        if THUMBS_GENERATE_THUMBNAILS:
            if self.field.sizes:
                for size in self.field.sizes:
                    try:
                        self._generate_thumb(content, size)
                    except Exception:
                        if settings.DEBUG:
                            raise

    def delete(self, save=True):
        if self.name and self.field.sizes:
            for size in self.field.sizes:
                base, extension = self.name.rsplit('.', 1)
                thumb_name = self.THUMB_SUFFIX % (base, size[0], size[1], extension)
                try:
                    self.storage.delete(thumb_name)
                except Exception:
                    if settings.DEBUG:
                        raise
        super(ImageFieldFile, self).delete(save)

    def generate_thumbnails(self, force_format=None):
        """ """
        if self.field.sizes:
            images = []
            for size in self.field.sizes:
                try:
                    image = self.generate_thumbnail(size, force_format)
                    images.append(image)
                except Exception:
                    if settings.DEBUG:
                        raise
            return images

    def generate_thumbnail(self, size, format):
        return self._generate_thumb(self.storage.open(self.name), size, format)

    def thumbnail(self, widthOrSize, height=None):
        """Return the thumbnail url for an specific size. The same thing as url_[width]x[height] without the magic.

        :param widthOrSize: Width as integer or size as tuple.
        :param height: Height as integer. Optional, will use `widthOrSize` as height if missing.

        :Example:
        instance.thumbnail(48, 48)
        instance.thumbnail(64)
        instance.thumbnail( (100, 70) )
        """
        if type(widthOrSize) is tuple:
            size = widthOrSize
        else:
            if height is None:
                height = widthOrSize
            size = (widthOrSize, height)
        return self.__getattr__('url_%sx%s' % (size[0], size[1]))


class ImageWithThumbsField(ImageField):
    """
    Usage example:
    ==============
    photo = ImageWithThumbsField(upload_to='images', sizes=((125,125),(300,200),)

    To retrieve image URL, exactly the same way as with ImageField:
        my_object.photo.url
    To retrieve thumbnails URL's just add the size to it:
        my_object.photo.url_125x125
        my_object.photo.url_300x200

    Note: The 'sizes' attribute is not required. If you don't provide it,
    ImageWithThumbsField will act as a normal ImageField

    How it works:
    =============
    For each size in the 'sizes' atribute of the field it generates a
    thumbnail with that size and stores it following this format:

    available_filename.[width]x[height].extension

    Where 'available_filename' is the available filename returned by the storage
    backend for saving the original file.

    Following the usage example above: For storing a file called "photo.jpg" it saves:
    photo.jpg          (original file)
    photo.125x125.jpg  (first thumbnail)
    photo.300x200.jpg  (second thumbnail)

    With the default storage backend if photo.jpg already exists it will use these filenames:
    photo_.jpg
    photo_.125x125.jpg
    photo_.300x200.jpg

    Note: django-thumbs assumes that if filename "any_filename.jpg" is available
    filenames with this format "any_filename.[widht]x[height].jpg" will be available, too.

    """

    attr_class = ImageWithThumbsFieldFile

    def __init__(
        self,
        verbose_name=None,
        name=None,
        width_field=None,
        height_field=None,
        sizes=None,
        preserve_ratio=False,
        **kwargs,
    ):
        super(ImageField, self).__init__(**kwargs)
        self.verbose_name = verbose_name
        self.name = name
        self.width_field = width_field
        self.height_field = height_field
        self.sizes = sizes
        self.preserve_ratio = preserve_ratio

    def update_dimension_fields(self, *args, **kwargs):
        # Wrap update_dimension_fields in a try to avoid exception when viewing
        # admin page for object with missing image file
        try:
            super().update_dimension_fields(*args, **kwargs)
        except OSError:
            pass
