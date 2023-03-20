from django.db import models
from django.db.models import JSONField

from releases.models.fuga_metadata import FugaStores


class StoreQuerySet(models.QuerySet):
    def active(self):
        return self.filter(active=True)


class StoreManager(models.Manager):
    def get_queryset(self):
        return StoreQuerySet(self.model)

    def active(self):
        return self.get_queryset().active()


class StoreCategory(models.Model):
    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text='Display name for this category',
    )
    order = models.PositiveSmallIntegerField(
        default=0, help_text='Stores are ordered according to this number'
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Store categories'


class Store(models.Model):
    YOUTUBE_CONTENT_ID_STORE_NAME = 'YouTube Content ID'

    name = models.CharField(max_length=255, blank=False, null=False)
    internal_name = models.CharField(max_length=64, blank=True, null=True, unique=True)
    # Validated as a drf.SlugField on serialization.
    # Meant to be based on ``Store.name``, hence same size.
    slug = models.CharField(null=True, blank=True, max_length=255)
    # For storing a hexadecimal color in short, long or alpha form
    hex_color = models.CharField(null=True, blank=True, max_length=9)
    logo = models.URLField(max_length=255, blank=True, null=True)
    logo_color = models.URLField(max_length=255, blank=True, null=True)
    org_id = models.CharField(max_length=10, blank=True, null=True)
    order = models.PositiveSmallIntegerField(default=999)
    active = models.BooleanField(default=True)
    admin_active = models.BooleanField(default=True)
    is_pro = models.BooleanField(default=False)
    category = models.ForeignKey(
        StoreCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    show_on_top = models.BooleanField(default=False)
    multi_batch_support = models.BooleanField(default=True)
    batch_size = models.PositiveSmallIntegerField(default=10)
    fuga_store = models.ForeignKey(
        FugaStores, on_delete=models.SET_NULL, null=True, blank=True
    )
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    extra_info = JSONField(null=True, blank=True)
    objects = StoreManager()

    def __str__(self):
        return self.name

    @staticmethod
    def get_yt_content_id_store():
        return Store.objects.get(name=Store.YOUTUBE_CONTENT_ID_STORE_NAME)

    @staticmethod
    def get_pro_stores_fuga():
        """
        Helper method returning list of PRO Store objects delivered
        over FUGA delivery.
        JIRA: PLAT-89
        :param release:
        :return: list(Stores) or None
        """
        pro_stores = Store.objects.filter(
            is_pro=True, active=True, org_id__isnull=False
        ).exclude(name=Store.YOUTUBE_CONTENT_ID_STORE_NAME)
        return list(pro_stores)

    @staticmethod
    def get_twitch_store():
        return Store.objects.filter(name="Twitch").first()

    @staticmethod
    def get_tiktik_store():
        return Store.objects.filter(name='TikTok').first()

    @staticmethod
    def get_soundcloud_store():
        return Store.objects.filter(name='SoundCloud').first()

    @staticmethod
    def from_internal_name(internal_name):
        store = Store.objects.filter(internal_name=internal_name)
        if store:
            return store.first()
        return None

    @staticmethod
    def get_pro_stores():
        """
        Get PRO stores as they are defined on PLAT-89
        """
        pro_sores = Store.get_pro_stores_fuga()
        tiktok_store = Store.get_tiktik_store()
        if tiktok_store:
            pro_sores.append(tiktok_store)
        sound_cloudstore = Store.get_soundcloud_store()
        if sound_cloudstore:
            pro_sores.append(sound_cloudstore)
        return pro_sores

    @staticmethod
    def get_yt_music_store():
        return Store.objects.get(active=True, internal_name='youtube_music')
