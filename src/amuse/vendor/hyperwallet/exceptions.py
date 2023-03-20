GENERIC_ERROR_MSG = "Please contact Amuse support https://bit.ly/2MeQrvT for more information regarding this failed withdrawal."
LIMIT_SUBCEEDED_MSG = (
    "Your withdrawal amount does not meet the Hyperwallet minimum withdrawal limit "
    "including the payment transaction fees. Please contact Hyperwallet support "
    "https://www.hyperwallet.com/support/ for information regarding the exact limit "
    "for your country."
)
NAME_CONSTRAINT_MSG = (
    "Your %s name must be Max 50 characters and only use letters, space and "
    "' , - . in conjunction with other letters. "
    "No numbers or other special characters are allowed. "
    "You can edit your name in the user settings section in the apps or on the web."
)
INCORRECT_FUNDING_PROGRAM_MSG = (
    "You have most likely changed the country on your Amuse account after you created "
    "your Hyperwallet account. The countries on both Amuse and Hyperwallet must be the "
    "same. Please contact Hyperwallet support "
    "https://www.hyperwallet.com/support/ for more information regarding this."
)
INVALID_WALLET_STATUS_MSG = (
    "Your Hyperwallet account is not active. Please contact Hyperwallet support "
    "https://www.hyperwallet.com/support/ for more information regarding your "
    "account status and how to activate your account."
)
STORE_INVALID_CURRENCY_MSG = (
    "Withdrawals are not supported for your country. Please contact Amuse "
    "Support https://bit.ly/2MeQrvT for more information."
)
DUPLICATE_EXTRA_ID_TYPE_MSG = (
    "A Hyperwallet account already exists. Please contact Amuse support "
    "https://bit.ly/2MeQrvT for more information regarding this."
)


class HyperwalletAPIError(Exception):
    error_message = GENERIC_ERROR_MSG


class LimitSubceededError(HyperwalletAPIError):
    """
    Withdrawal amount doesn't meet minimum cashout limit including wire transfer fees
    for this country in local currency.
    """

    error_message = LIMIT_SUBCEEDED_MSG


class FirstNameConstraintError(HyperwalletAPIError):
    """
    Failed Hyperwallet first name validation.
    Max 50 characters. Allows letters space and ' , - . in conjunction with letters.
    """

    error_message = NAME_CONSTRAINT_MSG % "first"


class LastNameConstraintError(HyperwalletAPIError):
    """
    Failed Hyperwallet last name validation.
    Max 50 characters. Allows letters space and ' , - . in conjunction with letters.
    """

    error_message = NAME_CONSTRAINT_MSG % "last"


class IncorrectFundingProgramError(HyperwalletAPIError):
    """
    User created HW account with country A that belongs in HW program A.
    User changed Amuse user.country to B that belongs in HW program B
    """

    error_message = INCORRECT_FUNDING_PROGRAM_MSG


class InvalidWalletStatusError(HyperwalletAPIError):
    """
    Hyperwallet froze the user's account.
    """

    error_message = INVALID_WALLET_STATUS_MSG


class StoreInvalidCurrencyError(HyperwalletAPIError):
    """
    User's country does not support USD as a currency.
    """

    error_message = STORE_INVALID_CURRENCY_MSG


class DuplicateExtraIdTypeError(HyperwalletAPIError):
    """
    User's country does not support USD as a currency.
    """

    error_message = DUPLICATE_EXTRA_ID_TYPE_MSG
