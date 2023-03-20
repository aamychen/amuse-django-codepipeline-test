from .abstract_flow import AbstractFlow
from .regular_flow import RegularFlow
from .song_invitation_flow import SongInvitationFlow
from .team_invitation_flow import TeamInvitationFlow
from .royalty_invitation_flow import RoyaltyInvitationFlow


class SignupFlowFactory:
    @classmethod
    def create_flow(cls, validated_data: dict) -> AbstractFlow:
        royalty_token = validated_data.get('royalty_token', None)
        if royalty_token is not None:
            return RoyaltyInvitationFlow(royalty_token)

        user_artist_role_token = validated_data.get('user_artist_role_token', None)
        if user_artist_role_token is not None:
            return TeamInvitationFlow(user_artist_role_token)

        song_artist_invite_token = validated_data.get('song_artist_token', None)
        if song_artist_invite_token is not None:
            return SongInvitationFlow(song_artist_invite_token)

        return RegularFlow()
