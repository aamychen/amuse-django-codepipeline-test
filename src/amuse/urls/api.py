from django.conf.urls import url, include
from django.urls import path, re_path
from rest_framework import routers

from amuse.api.base import viewsets
from amuse.api.base.views import (
    activity,
    appsflyer_device,
    auth,
    contributor_artist,
    metadata,
    payment_countries,
    payment_methods,
    payment_transactions,
    related_users,
    royalty_split,
    search,
    subscription,
    subscription_plan,
    transactions,
    user_metadata,
)
from amuse.api.base.views.audiomack import AudiomackOauthView, AudiomackCallbackView
from amuse.api.base.views.file import FileUploadView
from amuse.api.base.views.links import LinkView
from amuse.api.base.views.payouts.ffwd import FFWDView
from amuse.api.base.views.payouts.payee import PayeeView, PayeeGetAuthTokenView
from amuse.api.base.views.payouts.payee_profile import PayeeSummaryView
from amuse.api.base.views.payouts.payment import PaymentView
from amuse.api.base.views.payouts.transfer_method import TransferMethodView
from amuse.api.base.views.release import ReleaseMetadataView
from amuse.api.base.views.sms import download_link
from amuse.api.base.views.spotify_for_artists import (
    SpotifyForArtistsCallbackView,
    SpotifyForArtistsView,
    SpotifyForArtistsDisconnectView,
)
from amuse.api.base.views.store import StoreView


from amuse.api.base.views.suggest_contributor import SuggestContributor
from amuse.api.base.views.takedown import TakedownView
from payments import views as payment_views
from slayer.urls import urlpatterns as slayer_urls
from amuse.api.base.views.otp import OtpTriggerView, OtpVerifyView

urlpatterns = [
    re_path(r'users/email-exists', viewsets.check_email_exists, name='email-exists'),
    re_path(r'users/phone-exists', viewsets.check_phone_exists, name='phone-exists'),
    re_path(r'users/check-email', viewsets.check_email, name='check-email'),
    re_path(
        r'users/withdrawal',
        transactions.CreateWithdrawal.as_view(),
        name='user-withdrawal',
    ),
    re_path(
        r'users/metadata',
        user_metadata.UserMetadataView.as_view(),
        name='user-metadata',
    ),
    re_path(r'file/upload', FileUploadView.as_view(), name='file-upload'),
    re_path(r'sms/download-link', download_link, name='sms-download-link'),
    path(
        r"metadata/artist/<str:spotify_id>/",
        metadata.artist_by_spotify_id,
        name="metadata-artist-spotify_id",
    ),
    re_path(r"metadata/artist", metadata.artist, name="metadata-artist"),
    path(
        r'users/<int:user_id>/transactions/',
        transactions.RetrieveTransactions.as_view(),
        name='user-transactions',
    ),
    path(
        r'users/<int:user_id>/transactions/statement/',
        transactions.CreateStatementRequest.as_view(),
        name='user-transactions-statement',
    ),
    path(
        r'users/<int:user_id>/transactions/<str:year_month>/',
        transactions.RetrieveTransactions.as_view(),
        name='user-transactions',
    ),
    path(
        r"users/<int:user_id>/activity/<path:path>/",
        activity.activity,
        name="user-activity",
    ),
    path(
        r"artists/<int:artist_id>/activity/<path:endpoint>/",
        activity.artist,
        name="artist-activity",
    ),
    re_path(
        r'suggest-contributor', SuggestContributor.as_view(), name='suggest-contributor'
    ),
    re_path(
        r'artists/related', search.RelatedArtistView.as_view(), name='related-artists'
    ),
    re_path(r'artists/search', search.ArtistSearchView.as_view(), name='artist-search'),
    re_path(r'users/related', related_users.related_users, name='related-users'),
    re_path(
        r'blacklist/search',
        search.BlacklistedArtistNameSearchView.as_view(),
        name='blacklisted-artist-name-search',
    ),
    re_path(
        r'appsflyer/devices',
        appsflyer_device.AppsflyerDeviceView.as_view(),
        name='appsflyer-devices',
    ),
    path('auth/login', auth.LoginView.as_view(), name='auth-login'),
    path(
        'royalty-splits/song/<int:song_id>',
        royalty_split.UpdateRoyaltySplitsView.as_view(),
        name='update-royalty-splits',
    ),
    path(
        'royalty-splits/release/<int:release_id>',
        royalty_split.GetRoyaltySplitsByReleaseIDView.as_view(),
        name='royalty-splits-per-release',
    ),
    path(
        r'royalty-splits',
        royalty_split.GetRoyaltySplitsView.as_view(),
        name='royalty-splits',
    ),
    path(
        'contributor-artist',
        contributor_artist.ContibutorArtistView.as_view(),
        name='create-contributor-artist',
    ),
    path(
        r'payments/supported-countries/adyen/',
        payment_countries.PaymentCountriesView.as_view(),
        name='payment-countries',
    ),
    path(
        r'subscriptions/apple/info/',
        subscription.AppleSubscriptionInfoView.as_view(),
        name='apple-subscription-info',
    ),
    path(
        r'subscriptions/apple/',
        subscription.CreateAppleSubscriptionView.as_view(),
        name='create-apple-subscription',
    ),
    path(
        r'subscriptions/adyen/upgrade/<int:plan_id>/',
        subscription.AdyenTierUpgradeView.as_view(),
        name='adyen-tier-upgrade',
    ),
    path(
        r'subscriptions/adyen/',
        subscription.CreateAdyenSubscriptionView.as_view(),
        name='create-adyen-subscription',
    ),
    path(
        r'subscriptions/google/',
        subscription.CreateGoogleSubscriptionView.as_view(),
        name='create-google-subscription',
    ),
    path(
        r'subscriptions/current/plan/',
        subscription.ChangeSubscriptionPlanView.as_view(),
        name='update-current-subscription-plan',
    ),
    path(
        r'subscriptions/current/payment-method/',
        payment_methods.UpdatePaymentMethodView.as_view(),
        name='update-current-payment-method',
    ),
    path(
        r'payments/supported-methods/adyen/',
        payment_methods.GetSupportedPaymentMethodView.as_view(),
        name='get-supported-payment-method',
    ),
    path(
        r'subscription-plans/',
        subscription_plan.SubscriptionPlansView.as_view(),
        name='subscription-plans',
    ),
    path(
        r'payments/transactions/',
        payment_transactions.PaymentTransactionView.as_view(),
        name='payment-transactions',
    ),
    path(
        r'payments/transactions/<int:transaction_id>/',
        payment_transactions.UpdatePaymentTransactionView.as_view(),
        name='update-payment-transaction',
    ),
    path(
        r'releases/wallet-metadata/',
        ReleaseMetadataView.as_view(),
        name='releases-wallet-list',
    ),
    path(
        r'releases/<int:release_id>/takedown/',
        TakedownView.as_view(),
        name='releases-takedown',
    ),
    path(
        r'spotify-for-artists/',
        SpotifyForArtistsView.as_view(),
        name='spotify-for-artists',
    ),
    path(
        r'spotify-for-artists/callback/',
        SpotifyForArtistsCallbackView.as_view(),
        name='spotify-for-artists-callback',
    ),
    path(
        r'spotify-for-artists/disconnect',
        SpotifyForArtistsDisconnectView.as_view(),
        name='spotify-for-artists-disconnect',
    ),
    path(r'audiomack/oauth', AudiomackOauthView.as_view(), name='audiomack-oauth'),
    path(
        r'audiomack/callback',
        AudiomackCallbackView.as_view(),
        name='audiomack-callback',
    ),
    path(r'links', LinkView.as_view(), name='links'),
    # These are App URLs but needed here for reverse to work, see amuse.vendor.adyen.base
    path(
        r'adyen/3ds/<int:payment_id>/<str:encrypted_user_id>/',
        payment_views.adyen_3ds,
        name='adyen_3ds',
    ),
    path(
        r'adyen/notifications/',
        payment_views.adyen_notification_view,
        name='adyen-notifications',
    ),
    path(r'payouts/payee/', PayeeView.as_view(), name='payee'),
    path(
        r'payouts/payee/auth-token/',
        PayeeGetAuthTokenView.as_view(),
        name="payee_auth_token",
    ),
    path(
        r'payouts/transfer-method/',
        TransferMethodView.as_view(),
        name="transfer_method",
    ),
    path(r'payouts/payment/', PaymentView.as_view(), name="payouts_payment"),
    path(r'payouts/ffwd/', FFWDView.as_view(), name="payouts_ffwd"),
    path(r'payouts/summary/', PayeeSummaryView.as_view(), name="payee_summary"),
    path(r'stores/', StoreView.as_view(), name='store-list'),
    url(r'', include(slayer_urls)),
    path(r'otp/trigger/', OtpTriggerView.as_view(), name='otp-trigger'),
    path(r'otp/verify/<otp_id>/', OtpVerifyView.as_view(), name='otp-verify'),
]

router = routers.DefaultRouter()

router.register(r'countries', viewsets.CountryViewSet)
router.register(r'genre-list', viewsets.GenreListViewSet)
router.register(
    r'metadata-languages',
    viewsets.MetadataLanguageViewSet,
    basename='metadata-languages',
)

router.register(r'users', viewsets.UserViewSet)

router.register(r'releases/song-file-upload', viewsets.SongFileUploadViewSet)
router.register(
    r'releases/google-drive-song-file-download',
    viewsets.GoogleDriveSongFileDownloadViewSet,
    basename='releases-google-drive-song-file-download',
)
router.register(
    r'releases/link-song-file-download',
    viewsets.LinkSongFileDownloadViewSet,
    basename='releases-link-song-file-download',
)
router.register(r'releases', viewsets.ReleaseViewSet)

router.register(r'artists', viewsets.ArtistViewSet, basename='artist')
router.register(
    r'team-user-roles', viewsets.TeamUserRolesViewSet, basename='team-user-roles'
)
router.register(
    r'team-invitations', viewsets.TeamInvitationViewSet, basename='team-invitations'
)
router.register(r'royalty-invitations', viewsets.RoyaltyInvitationViewSet)
router.register(
    r'subscriptions/current', viewsets.SubscriptionViewSet, basename='subscription'
)

urlpatterns += router.urls
