from pyslayer import services
from pyslayer.client import SlayerClient
from pyslayer.sync import wrap_async


class SlayerClientWrapper(SlayerClient):
    @wrap_async(pluck=None)
    def analytics_artist_release_tracks(self, artist_id, upc, response_length):
        return self.analytics.artist_release_track_summary(
            services.analytics.ArtistReleaseTrackSummaryRequest(
                artist_id=artist_id, upc=upc, response_length=response_length
            )
        )

    # Streaming Analytics API Phase 1
    @wrap_async(pluck=None)
    def analytics_release_summary(self, artist_id, upc):
        return self.analytics.release_summary(
            services.analytics.ReleaseSummaryRequest(artist_id=artist_id, upc=upc)
        )

    @wrap_async(pluck=None)
    def analytics_artist_country_summary(self, artist_id):
        return self.analytics.artist_country_summary(
            services.analytics.ArtistCountrySummaryRequest(artist_id=artist_id)
        )

    @wrap_async(pluck=None)
    def analytics_artist_playlist_summary(self, artist_id, response_length):
        return self.analytics.artist_playlist_summary(
            services.analytics.ArtistPlaylistSummaryRequest(
                artist_id=artist_id, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_artist_daily(self, artist_id, response_length):
        return self.analytics.artist_daily(
            services.analytics.ArtistDailyRequest(
                artist_id=artist_id, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_artist_summary(self, artist_id):
        return self.analytics.artist_summary(
            services.analytics.ArtistSummaryRequest(artist_id=artist_id)
        )

    @wrap_async(pluck=None)
    def analytics_artist_release_summary(self, artist_id, response_length):
        return self.analytics.artist_release_summary(
            services.analytics.ArtistReleaseSummaryRequest(
                artist_id=artist_id, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_artist_track_summary(self, artist_id, response_length):
        return self.analytics.artist_track_summary(
            services.analytics.ArtistTrackSummaryRequest(
                artist_id=artist_id, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_track_summary(self, artist_id, isrc):
        return self.analytics.track_summary(
            services.analytics.TrackSummaryRequest(artist_id=artist_id, isrc=isrc)
        )

    @wrap_async(pluck=None)
    def analytics_release_summary(self, artist_id, upc):
        return self.analytics.release_summary(
            services.analytics.ReleaseSummaryRequest(artist_id=artist_id, upc=upc)
        )

    @wrap_async(pluck=None)
    def analytics_track_daily(self, artist_id, isrc, response_length):
        return self.analytics.artist_track_daily(
            services.analytics.ArtistTrackDailyRequest(
                artist_id=artist_id, isrc=isrc, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_release_daily(self, artist_id, upc, response_length):
        return self.analytics.artist_release_daily(
            services.analytics.ArtistReleaseDailyRequest(
                artist_id=artist_id, upc=upc, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_track_ugc_daily(self, artist_id, isrc, response_length):
        return self.analytics.artist_track_ugc_daily(
            services.analytics.ArtistTrackUgcDailyRequest(
                artist_id=artist_id, isrc=isrc, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_track_yt_cid_summary(self, artist_id, isrc):
        return self.analytics.artist_track_youtube_content_id_summary(
            services.analytics.ArtistTrackYoutubeContentIdSummaryRequest(
                artist_id=artist_id, isrc=isrc
            )
        )

    @wrap_async(pluck=None)
    def analytics_track_countries(self, artist_id, isrc):
        return self.analytics.artist_track_country_summary(
            services.analytics.ArtistTrackCountrySummaryRequest(
                artist_id=artist_id, isrc=isrc
            )
        )

    @wrap_async(pluck=None)
    def analytics_release_countries(self, artist_id, upc):
        return self.analytics.artist_release_country_summary(
            services.analytics.ArtistReleaseCountrySummaryRequest(
                artist_id=artist_id, upc=upc
            )
        )

    @wrap_async(pluck=None)
    def analytics_track_playlist(self, artist_id, isrc, response_length):
        return self.analytics.artist_track_playlist_summary(
            services.analytics.ArtistTrackPlaylistSummaryRequest(
                artist_id=artist_id, isrc=isrc, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_release_playlist(self, artist_id, upc, response_length):
        return self.analytics.artist_release_playlist_summary(
            services.analytics.ArtistReleasePlaylistSummaryRequest(
                artist_id=artist_id, upc=upc, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_monthly(self, artist_id, response_length):
        return self.analytics.artist_monthly(
            services.analytics.ArtistMonthlyRequest(
                artist_id=artist_id, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_track_monthly(self, artist_id, isrc, response_length):
        return self.analytics.artist_track_monthly(
            services.analytics.ArtistTrackMonthlyRequest(
                artist_id=artist_id, isrc=isrc, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_release_monthly(self, artist_id, upc, response_length):
        return self.analytics.artist_release_monthly(
            services.analytics.ArtistReleaseMonthlyRequest(
                artist_id=artist_id, upc=upc, response_length=response_length
            )
        )

    @wrap_async(pluck=None)
    def analytics_release_share(self, artist_id, upc):
        return self.analytics.artist_release_share_summary(
            services.analytics.ArtistReleaseShareRequest(artist_id=artist_id, upc=upc)
        )

    ###

    @wrap_async(pluck="artist_daily")
    def legacy_artist_daily(self, artist_id):
        return self.legacy.artist_daily(
            services.legacy.ArtistDailySimpleRequest(artist_id=artist_id)
        )

    @wrap_async(pluck="artist_song_daily")
    def legacy_artist_song_daily(self, artist_id):
        return self.legacy.artist_song_daily(
            services.legacy.ArtistSongDailySimpleRequest(artist_id=artist_id)
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def activity_artist_summary(self, artist_id):
        return self.activity.artist_summary(
            services.activity.ArtistSummaryRequest(artist_id=artist_id)
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def metadata_release_with_license_info(self, release_id):
        return self.metadata.get_release(
            services.metadata.GetReleaseRequest(release_id=release_id)
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def metadata_spotify_artist_search(self, query):
        return self.metadata.spotify_artist_search(
            services.metadata.SpotifyArtistSearchRequest(query=query)
        )

    @wrap_async(pluck=None)
    def metadata_spotify_artist_lookup(self, spotify_id):
        return self.metadata.spotify_artist_lookup(
            services.metadata.SpotifyArtistLookupRequest(id=spotify_id)
        )

    @wrap_async(pluck=None)
    def metadata_users_to_spotify_artists(self, user_ids):
        return self.metadata.users_to_spotify_artists(
            services.metadata.UsersToSpotifyArtistsRequest(user_ids=user_ids)
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def activity_artist(self, artist_id, endpoint, *_):
        return self.query_activity_endpoint(
            service_name='artist',
            endpoint_name=endpoint,
            query_filter={'artist_id': artist_id},
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def activity_contributor(self, artist_id, endpoint):
        return self.query_activity_endpoint(
            service_name='contributor',
            endpoint_name=endpoint,
            query_filter={'artist_id': artist_id},
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def revenue_validate_app_royalty_advance_offer(
        self, user_id, offer_id, create_pending_transactions=False
    ):
        return self.revenue.validate_app_royalty_advance_offer(
            services.revenue.ValidateAppRoyaltyAdvanceOfferRequest(
                user_id=user_id,
                royalty_advance_offer_id=offer_id,
                create_pending_transactions=create_pending_transactions,
            )
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def activate_app_royalty_advance(self, **kwargs):
        return self.revenue.activate_app_royalty_advance(
            services.revenue.ActivateAppRoyaltyAdvanceRequest(**kwargs)
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def cancel_app_royalty_advance(self, **kwargs):
        return self.revenue.cancel_app_royalty_advance(
            services.revenue.CancelAppRoyaltyAdvanceRequest(**kwargs)
        )

    @wrap_async(pluck=None, ignore_defaults=True)
    def refund_app_royalty_advance(
        self,
        user_id,
        royalty_advance_id,
        refund_amount_currency,
        refund_amount,
        description,
        refund_reference,
    ):
        return self.revenue.refund_app_royalty_advance(
            services.revenue.RefundAppRoyaltyAdvanceRequest(
                user_id=user_id,
                royalty_advance_id=royalty_advance_id,
                refund_amount_currency=refund_amount_currency,
                refund_amount=refund_amount,
                description=description,
                refund_reference=refund_reference,
            )
        )

    def update_royalty_advance_offer(
        self, user_id, advance_id, action, description=None, payment_id=None
    ):
        svc_args = dict(
            user_id=user_id,
            royalty_advance_id=advance_id,
            description=str(description).replace("'", '"'),
        )

        if payment_id:
            svc_args['withdrawal_reference'] = payment_id

        if action == 'activate':
            return self.activate_app_royalty_advance(**svc_args)
        elif action == 'cancel':
            return self.cancel_app_royalty_advance(**svc_args)


#: Mimic legacy HTTP/1-JSON Slayer client interface
slayer = SlayerClientWrapper()
legacy_user_daily_stats = slayer.legacy_artist_daily
legacy_song_daily_stats = slayer.legacy_artist_song_daily
summary = slayer.activity_artist_summary
metadata_spotifyartist = slayer.metadata_spotify_artist_search
spotify_artist_lookup = slayer.metadata_spotify_artist_lookup
users_spotifyartist = slayer.metadata_users_to_spotify_artists
# gRPC JSON gateway mapping was: user => artist
user_activity = slayer.activity_artist
# gRPC JSON gateway mapping was: artist => contributor
artist_activity = slayer.activity_contributor
validate_royalty_advance_offer = slayer.revenue_validate_app_royalty_advance_offer
update_royalty_advance_offer = slayer.update_royalty_advance_offer
refund_royalty_advance_offer = slayer.refund_app_royalty_advance
get_release_with_license_info = slayer.metadata_release_with_license_info
