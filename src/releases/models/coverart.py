from io import BytesIO, UnsupportedOperation
from os.path import splitext
from uuid import uuid4

from django.conf import settings
from django.db import models
from PIL import Image as PILImage
from PIL import ImageCms
from PIL.ImageCms import ImageCmsProfile

from amuse.db.decorators import with_history
from amuse.db.models import ImageWithThumbsField
from amuse.models import Image
from amuse.storages import S3Storage
from releases.models import Release, release_completed
from users.models import User


def cover_art_file_changed(release):
    # If no other flags than 'artwork_' is set, set the release status to Pending Approval
    if not len(
        [
            f
            for f in release.error_flags
            if not f[0].startswith('artwork') and f[1] is True
        ]
    ):
        release.status = Release.STATUS_PENDING
        release.save()


def uploaded_directory_path(instance, filename):
    return '%s%s' % (str(uuid4()), splitext(filename)[1])


@with_history
class CoverArt(models.Model):
    release = models.OneToOneField(
        Release, null=True, related_name='cover_art', on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)
    file = ImageWithThumbsField(
        storage=S3Storage(
            bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME,
            querystring_auth=False,
            custom_domain=settings.ASSETS_CDN_DOMAIN,
        ),
        upload_to=uploaded_directory_path,
        width_field='width',
        height_field='height',
        sizes=((200, 200), (400, 400), (800, 800)),
    )

    images = models.ManyToManyField(Image)

    width = models.PositiveSmallIntegerField(blank=True, null=True, default=None)
    height = models.PositiveSmallIntegerField(blank=True, null=True, default=None)
    checksum = models.TextField(null=True, blank=True, editable=False)

    @property
    def thumbnail_url_400(self):
        try:
            return self.file.url_400x400
        except OSError:
            return ''

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        release_completed(self.release)

        if self.file:
            from amuse.tasks import process_coverart

            process_coverart(self.pk)

    def get_file_image(self):
        try:
            image = PILImage.open(self.file)
            image.load()
            return image
        except (OSError, UnsupportedOperation, SyntaxError):
            pass
        finally:
            try:
                self.file.seek(0)  # Reset file to original state
            except IOError:
                pass

        return None

    def has_correct_file_ending(self):
        filename = self.file.name.lower()
        return filename.endswith('.jpg') or filename.endswith('.jpeg')

    def save_jpeg_image(self, image):
        image_data = BytesIO()
        image.save(image_data, 'JPEG', quality=95, optimize=True)
        filename = self.file.name.lower()
        if not self.has_correct_file_ending():
            self.file.name += '.jpg'
        self.file.save(self.file.name, image_data)

    def convert_to_rgb(self, image):
        """Converts CMYK and other mode images to RGB.

        If the image bundles an ICC profile use that and target profile
        sRGB IEC61966-2.1. For other cases use Pillow builtin.
        """
        if image.mode == 'RGB':
            return image
        else:
            icc_profile = image.info.get('icc_profile')

            if icc_profile:
                profile = ImageCmsProfile(BytesIO(icc_profile))
                target_profile = ImageCmsProfile(settings.TARGET_ICC_PROFILE)
                try:
                    transform = ImageCms.buildTransform(
                        profile,
                        target_profile,
                        image.mode,
                        'RGB',
                        renderingIntent=ImageCms.INTENT_RELATIVE_COLORIMETRIC,
                    )
                    converted = ImageCms.applyTransform(image, transform)
                except ImageCms.PyCMSError:
                    converted = image.convert('RGB')
            else:
                converted = image.convert('RGB')

            return converted

    def resize_to_allowed(self, image):
        if image.width > 3000 or image.height > 3000 and image.width == image.height:
            converted = image.resize((3000, 3000), PILImage.LANCZOS)
            return converted
        return image
