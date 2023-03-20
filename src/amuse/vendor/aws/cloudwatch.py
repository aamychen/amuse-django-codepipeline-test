import boto3
from django.conf import settings
from codes.models import UPC, ISRC


def available_upc_count(client):
    client.put_metric_data(
        Namespace='Amuse',
        MetricData=[
            {
                'MetricName': 'AvailableUPCCount',
                'Value': UPC.objects.filter(status=UPC.STATUS_UNUSED).count(),
            }
        ],
    )


def available_isrc_count(client):
    client.put_metric_data(
        Namespace='Amuse',
        MetricData=[
            {
                'MetricName': 'AvailableISRCCount',
                'Value': ISRC.objects.filter(status=ISRC.STATUS_UNUSED).count(),
            }
        ],
    )


def standard_resolution_job():
    client = boto3.client(
        'cloudwatch',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    available_upc_count(client)
    available_isrc_count(client)
