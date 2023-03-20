import pytest

from amuse.services.usermanagement.signup_flows.signup_flow_factory import (
    RegularFlow,
    RoyaltyInvitationFlow,
    SongInvitationFlow,
    TeamInvitationFlow,
    SignupFlowFactory,
)


@pytest.mark.parametrize(
    'validated_data,expected',
    [
        ({}, RegularFlow),
        ({'royalty_token': '123'}, RoyaltyInvitationFlow),
        ({'user_artist_role_token': '123'}, TeamInvitationFlow),
        ({'song_artist_token': '123'}, SongInvitationFlow),
    ],
)
def test_signup_flow_factory(validated_data, expected):
    flow = SignupFlowFactory.create_flow(validated_data)
    assert isinstance(flow, expected)
