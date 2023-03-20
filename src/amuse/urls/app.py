"""amuse URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  re_path(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  re_path(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Import the include() function: from django.conf.urls import url, include
    3. Add a URL to urlpatterns:  re_path(r'^blog/', include(blog_urls))
"""
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, re_path
from django.views.generic import RedirectView

from amuse.api.base.views.hyperwallet_notifications import hyperwallet_notification_view
from amuse.firebase import slack_notification
from amuse.health import healthcheck
from amuse.tokens import password_reset_token_generator
from amuse.urls.api import urlpatterns as api_urlpatterns
from app.views import sns
from payments import views as payment_views
from payments.views import adyen_notification_view
from subscriptions.views import apple_subscription_view, google_subscription_view
from transcoder.urls import urlpatterns as transcoder_urlpatterns
from users import views as users_views
from website import views as website_views
from apidocs.urls import urlpatterns as apidocs_urlpatterns


admin.site.site_header = 'JARVI5'

urlpatterns = [
    re_path(r'^$', RedirectView.as_view(url=settings.WWW_URL, permanent=True)),
    re_path(r'^health/', healthcheck),
    re_path(r'^slack-notification/?$', slack_notification),
    re_path(r'^ext-legal-agreements/?$', website_views.ext_legal_agreements),
    re_path(r'^privacy/?$', website_views.privacy),
    re_path(r'^transcoder/', include(transcoder_urlpatterns)),
    re_path(r'^admin/docs/api/', include(apidocs_urlpatterns)),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^api/', include(api_urlpatterns)),
    re_path(
        r'^password-reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,32})/$',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='website/registration/password_reset_confirm.html',
            token_generator=password_reset_token_generator,
        ),
        name='password_reset_confirm',
    ),
    re_path(
        r'^password-reset/done/$',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='website/registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
    re_path(
        r'^email-verification/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,20})/$',
        users_views.email_verification_confirm,
        name='email_verification_confirm',
    ),
    re_path(
        r'^email-verification/done/$',
        users_views.email_verification_done,
        name='email_verification_done',
    ),
    re_path(
        r'^email-verification/fail/$',
        users_views.email_verification_fail,
        name='email_verification_fail',
    ),
    re_path(
        r'^withdrawal-verification/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,20})/$',
        users_views.withdrawal_verification_confirm,
        name='withdrawal_verification_confirm',
    ),
    # Song file transcoder
    re_path(r"^sns/notification/$", sns.notification, name="sns_notification"),
    re_path(
        r'^sns/song-file-transcoder-state-change/$',
        sns.song_file_transcoder_state_change,
        name='song_file_transcoder_state_change',
    ),
    path('subscriptions/apple/', apple_subscription_view, name='apple-subscriptions'),
    path(
        'subscriptions/google/', google_subscription_view, name='google-subscriptions'
    ),
    path(r'adyen/', payment_views.adyen_debug, name='adyen_debug'),
    path(
        r'adyen/3ds/<int:payment_id>/<str:encrypted_user_id>/',
        payment_views.adyen_3ds,
        name='adyen_3ds',
    ),
    path(r'adyen/notifications/', adyen_notification_view, name='adyen-notifications'),
    path(
        r'hyperwallet/notifications/eu/',
        hyperwallet_notification_view,
        name='hyperwallet-notifications-eu',
    ),
    path(
        r'hyperwallet/notifications/row/',
        hyperwallet_notification_view,
        name='hyperwallet-notifications-row',
    ),
    path(
        r'hyperwallet/notifications/se/',
        hyperwallet_notification_view,
        name='hyperwallet-notifications-se',
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [re_path(r'^__debug__/', include(debug_toolbar.urls))] + urlpatterns
