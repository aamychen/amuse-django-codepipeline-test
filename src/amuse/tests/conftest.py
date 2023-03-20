import os
import time

import pytest
import boto3

from moto import mock_kms

from amuse.jwtkms import Token, TokenHeader, TokenPayload, KmsManager


@pytest.fixture
def aws_config():
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def kms(aws_config):
    with mock_kms():
        client = boto3.client("kms", region_name="us-east-1")
        key = client.create_key(Description="sign-verify", KeyUsage="SIGN_VERIFY")
        yield client, key["KeyMetadata"]["Arn"]


@pytest.fixture
def token(kms):
    yield Token(
        kms=KmsManager(*kms),
        header=TokenHeader(alg="RS256", typ="JWT"),
        payload=TokenPayload(exp=int(time.time() + 300), sub="user123"),
    )
