ADVANCE_ERROR_MESSAGE = (
    "Advance withdrawal failed. Please contact Amuse support "
    "https://bit.ly/2MeQrvT for more information regarding this."
)


class RoyaltyAdvanceAPIError(Exception):
    error_message = ADVANCE_ERROR_MESSAGE


class RoyaltyAdvanceCancelError(RoyaltyAdvanceAPIError):
    """
    Network error, malformed payload or changed API definition.
    """

    pass


class RoyaltyAdvanceActivateError(RoyaltyAdvanceAPIError):
    """
    Network error, malformed payload or changed API definition.
    """

    pass
