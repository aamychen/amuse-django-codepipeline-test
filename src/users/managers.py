from django.contrib.auth.models import BaseUserManager
from django.db import models


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class UserManager(BaseUserManager):
    def get_queryset(self):
        return UserQuerySet(self.model, using=self._db)

    @classmethod
    def normalize_email(cls, email):
        """Normalizes email addresses by lowercasing
        the domain portion and name portion of the email address."""
        normalized = super(UserManager, cls).normalize_email(email)
        return normalized.lower()

    def create_user(self, email, password, **fields):
        user = self.model(email=self.normalize_email(email), **fields)
        if password:
            user.set_password(password)

        if password is None or password == '':
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        user = self.create_user(email, password=password)
        user.is_staff = True
        user.save(using=self._db)
        return user

    @property
    def active(self):
        return self.get_queryset().active()


class OtpDeviceManager(models.Manager):
    def get_unique_otp_device(self, **kwargs):
        otp_devices = self.filter(**kwargs)
        otp_devices_count = len(otp_devices)
        if otp_devices_count > 1:
            for otp_device in otp_devices[1:]:
                otp_device.delete()
            return otp_devices[0]
        elif otp_devices_count == 1:
            return otp_devices[0]
        elif len(otp_devices) == 0:
            return self.create(**kwargs)
