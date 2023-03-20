from decimal import Decimal
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from users.models.user import User

from amuse.api.v4.serializers.invite import InviteSerializer


class RoyaltySplitSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False, allow_null=True)
    rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0.0001'),
        max_value=Decimal('1.0'),
    )
    invite = InviteSerializer(required=False, allow_null=True)

    def validate(self, attrs):
        """
        Validates the serializer attributes.

        Raises:
        -------
            ValidationError: Raised either when both user_id and invite are
            equal to None or user_id does not exist
        """
        user_id = attrs.get('user_id')
        invite = attrs.get('invite')

        if user_id is not None:
            if not User.objects.filter(pk=user_id).exists():
                raise ValidationError('User does not exist')

        if user_id is None and invite is None:
            raise ValidationError('Both user_id and invite are empty.')
        return attrs
