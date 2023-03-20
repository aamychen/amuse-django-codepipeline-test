from rest_framework import serializers
import datetime
from django.conf import settings
import json
from amuse.logging import logger
from amuse.vendor.gcp import pubsub
from payouts.models import Provider, Payee, Event
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from hyperwallet.exceptions import HyperwalletAPIException, HyperwalletException


class CreateStatementRequestSerializer(serializers.Serializer):
    file_format = serializers.CharField(required=False, max_length=16, default="xlsx")
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)

    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        file_format = data.get('file_format')
        supported_formats = ('xlsx', 'csv')

        if file_format and file_format not in ('xlsx', 'csv'):
            raise serializers.ValidationError(
                detail=f"Unsupported file format {file_format}. accepted formats are {supported_formats}",
                code="INVALID_FILE_FORMAT",
            )

        if end_date <= start_date:
            raise serializers.ValidationError(
                detail=f"End date has to be after start date", code="INVALID_DATE_RANGE"
            )

        return data

    def request_statement(self, **kwargs):
        request = self.context['request']
        user = request.user
        start_date = self.validated_data["start_date"]
        end_date = self.validated_data["end_date"]
        file_format = self.validated_data["file_format"]
        statement_request_payload = {
            "user_id": user.id,
            "date_start": start_date.strftime("%Y-%m-%d"),
            "date_end": end_date.strftime("%Y-%m-%d"),
            "recipient_email": user.email,
            "format": file_format,
            "date_mode": "display",
        }

        try:
            publisher = pubsub.PubSubClient(settings.PUBSUB_TRANSACTION_STATEMENT_TOPIC)
            publisher.publish(json.dumps(statement_request_payload))
            logger.info(
                f"Get statement request for user {user.id} for period {start_date} - {end_date} published to PubSub"
            )
            return {"is_success": True}

        except Exception as e:
            logger.warn(f"Get statement request failed with exception: {e}")
            return {"is_success": False}
