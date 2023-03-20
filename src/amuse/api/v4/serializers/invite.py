import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class InviteSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_null=True)

    # TODO: adding custom PhoneNumberField to the serializer as ultimate
    # solution, along side a validation helper function.
    def validate_phone_number(self, value):
        """
        Validates phone number which is provided as a string.

        In case None was provided the same value will be returned.

        Args:
        ----
            value (str or None): Phone number as a string or None if it was
                not specified.

        Returns:
        -------
            value (str or None): The same as the input if the value is valid or
                None.

        Raises:
        ------
            ValidationError: Only raised when the value in different than None
                and invalid phone number.
        """
        if value is not None:
            try:
                parsed_phone = phonenumbers.parse(value)

                if not phonenumbers.is_valid_number(parsed_phone):
                    raise ValidationError('Enter a valid phone number.')
            except NumberParseException:
                raise ValidationError('Enter a valid phone number.')

        return value

    def validate(self, attrs):
        """
        Validates the serializer attributes.

        Raises:
        -------
            ValidationError: Only raised when both email and phone number are
                equal to None.
        """
        if attrs.get('email') is None and attrs.get('phone_number') is None:
            raise ValidationError("Both email and phone_number are empty")
        return attrs
