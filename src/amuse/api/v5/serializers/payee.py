from rest_framework import serializers
from amuse.logging import logger
from payouts.models import Provider, Payee, Event
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from hyperwallet.exceptions import HyperwalletAPIException, HyperwalletException
from amuse.utils import check_swedish_pnr


class CreatePayeeSerializer(serializers.Serializer):
    address = serializers.CharField(required=True, max_length=125)
    address2 = serializers.CharField(required=False, allow_null=True, max_length=100)
    middle_name = serializers.CharField(required=False, allow_null=True, max_length=50)
    profile_type = serializers.CharField(required=True, max_length=20)
    dob = serializers.DateField(required=True)
    city = serializers.CharField(required=True, max_length=50)
    state_province = serializers.CharField(required=True, max_length=50)
    postal_code = serializers.CharField(required=True, max_length=30)
    government_id = serializers.CharField(
        required=False, max_length=30, allow_null=True
    )

    def validate(self, data):
        request = self.context['request']
        user = request.user
        if not user.phone_verified:
            raise serializers.ValidationError(
                detail=f"{user.id} does not have valid phone", code="UNVALIDATED_PHONE"
            )
        if user.country == "SE":
            government_id = data.get("government_id")
            if not check_swedish_pnr(government_id):
                raise serializers.ValidationError(
                    {
                        'government_id': ['government_id is not valid'],
                        'reason': {
                            "errors": [
                                {
                                    "message": "Please enter a valid ID number",
                                    "fieldName": "governmentId",
                                    "code": "invalid_government_id",
                                }
                            ]
                        },
                    }
                )

        return data

    def _get_create_payload(self, user, program_token):
        required_fields = {
            "clientUserId": str(user.id) + "_" + user.country,
            "profileType": self.validated_data["profile_type"],
            "firstName": user.first_name.strip(),
            "lastName": user.last_name.strip(),
            "dateOfBirth": str(self.validated_data["dob"]),
            "email": user.email.strip(),
            "addressLine1": self.validated_data["address"],
            "city": self.validated_data["city"],
            "stateProvince": self.validated_data["state_province"],
            "country": user.country.strip(),
            "postalCode": self.validated_data["postal_code"],
            "programToken": program_token,
            "phoneNumber": user.phone,
        }

        # Optional fields
        if self.validated_data.get('address2') is not None:
            required_fields["addressLine2"] = self.validated_data.get('address2')
        if self.validated_data.get('middle_name') is not None:
            required_fields["middleName"] = self.validated_data.get('middle_name')
        if self.validated_data.get('government_id') is not None:
            required_fields["governmentId"] = self.validated_data.get('government_id')
        return required_fields

    @staticmethod
    def _save_payee(amuse_user, hw_user, government_id=None):
        payee_type = Payee.TYPE_INDIVIDUAL
        if hw_user.profileType != "INDIVIDUAL":
            payee_type = Payee.TYPE_BUSINESS
        Payee.objects.create(
            user=amuse_user,
            external_id=hw_user.token,
            status=hw_user.status,
            verification_status=hw_user.verificationStatus,
            type=payee_type,
            provider=Provider.objects.get(external_id=hw_user.programToken),
            government_id=government_id,
        )

    @staticmethod
    def _save_event(hw_user):
        Event.objects.create(
            object_id=hw_user.token,
            reason="API call",
            initiator="SYSTEM",
            payload=hw_user._raw_json,
        )

    def save(self, **kwargs):
        request = self.context['request']
        amuse_user = request.user
        hw_client = HyperWalletEmbeddedClientFactory().create(
            country_code=amuse_user.country
        )
        payload = self._get_create_payload(request.user, hw_client.programToken)
        gov_id = payload.get('governmentId')
        logger.info(f'*** Payload {payload}')
        try:
            hw_user = hw_client.createUser(payload)
            self._save_event(hw_user=hw_user)
            self._save_payee(
                amuse_user=amuse_user, hw_user=hw_user, government_id=gov_id
            )
            logger.info(f"Hyperwallet Payee: {hw_user} created for User: {amuse_user}")
            return {"is_success": True, "data": hw_user._raw_json, "reason": None}
        except (HyperwalletAPIException, HyperwalletException) as e:
            logger.warn(
                f"HyperWallet update payee failed with HyperWallet error {e.message}"
            )
            return {"is_success": False, "data": None, "reason": e.message}
        except Exception as e:
            logger.warn(f"HyperWallet update payee failed with error {e.__str__()}")
            return {"is_success": False, "data": None, "reason": e.__str__()}


class GetPayeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payee
        fields = [
            'user_id',
            'external_id',
            'type',
            'status',
            'verification_status',
            'created',
        ]


class UpdatePayeeSerializer(serializers.Serializer):
    address = serializers.CharField(required=False, max_length=125)
    address2 = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=100
    )
    middle_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=50
    )
    profile_type = serializers.CharField(required=False, max_length=20)
    dob = serializers.DateField(required=False)
    city = serializers.CharField(required=False, max_length=30)
    state_province = serializers.CharField(required=False, max_length=30)
    postal_code = serializers.CharField(required=False, max_length=30)
    government_id = serializers.CharField(required=False, max_length=30)

    def validate(self, data):
        user = self.context['user']
        if user.country == "SE":
            government_id = data.get("government_id")
            if not check_swedish_pnr(government_id):
                raise serializers.ValidationError(
                    {
                        'government_id': ['government_id is not valid'],
                        'reason': {
                            "errors": [
                                {
                                    "message": "Please enter a valid ID number",
                                    "fieldName": "governmentId",
                                    "code": "invalid_government_id",
                                }
                            ]
                        },
                    }
                )

        return data

    def _get_update_payload(self, user):
        # Skip fields that should not be available for update?

        updatable_fields = {
            "dob": "dateOfBirth",
            "address": "addressLine1",
            "city": "city",
            "state_province": "stateProvince",
            "postal_code": "postalCode",
            "address2": "addressLine2",
            "middle_name": "middleName",
            "government_id": "governmentId",
        }

        fields_to_update = {}
        send_props = self.validated_data.keys()

        for field, hw_name in updatable_fields.items():
            data = self.validated_data.get(field)
            if field in send_props:
                fields_to_update[hw_name] = (
                    None if (data == "" or data is None) else str(data)
                )

        # Always send relevant user data for update
        fields_to_update['email'] = user.email
        fields_to_update['firstName'] = user.first_name.strip()
        fields_to_update['lastName'] = user.last_name.strip()
        fields_to_update['phone'] = user.phone

        return fields_to_update

    @staticmethod
    def _save_event(hw_user):
        Event.objects.create(
            object_id=hw_user.token,
            reason="API call UPDATE",
            initiator="SYSTEM",
            payload=hw_user._raw_json,
        )

    def _save_payee(self, instance):
        """
        Only updatable field over API in Payee model is government_id
        """
        gov_id = self.validated_data.get('government_id')
        instance.government_id = gov_id
        instance.save(update_fields=['government_id'])

    def update(self, instance, validated_data):
        hw_client = HyperWalletEmbeddedClientFactory().create(instance.user.country)
        payload = self._get_update_payload(instance.user)
        try:
            logger.info(
                f"HyperWallet Payee update for user_id: {instance.user.id} with new fields: {payload}"
            )
            hw_user = hw_client.updateUser(userToken=instance.external_id, data=payload)
            self._save_event(hw_user=hw_user)
            self._save_payee(instance)
            return {"is_success": True, "data": hw_user._raw_json, "reason": None}
        except (HyperwalletAPIException, HyperwalletException) as e:
            logger.warn(
                f"HyperWallet update payee failed with HyperWallet error {e.message}"
            )
            return {"is_success": False, "data": None, "reason": e.message}
        except Exception as e:
            logger.warn(f"HyperWallet update payee failed with error {e.__str__()}")
            return {"is_success": False, "data": None, "reason": e.__str__()}
