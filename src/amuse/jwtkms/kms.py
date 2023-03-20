import base64

from django.core.cache import cache
from django.conf import settings


class KmsManager:
    def __init__(self, client, arn):
        self.client = client
        self.arn = arn

    @property
    def public_key(self) -> str:
        """KMS Public Key

        Base64-encodes retrieved public key from KMS, decodes it and returns
        the resulting string.

        :return: Public Key (string)
        """

        cache_key = f"pk_{self.arn}"
        if pk := cache.get(cache_key):
            return pk

        response = self.client.get_public_key(KeyId=self.arn)
        pk = base64.urlsafe_b64encode(response["PublicKey"]).decode()
        cache.set(cache_key, pk, settings.JWT_KMS_PUBKEY_CACHE_TTL_SECS)
        return pk

    def sign(self, unsigned: str) -> bytes:
        """Signs the given data and returns the signature encoded in bytes

        :param unsigned: Data to sign
        :return: Signature encoded in bytes
        """

        return self.client.sign(
            KeyId=self.arn,
            Message=unsigned,
            MessageType="RAW",
            SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256",
        )["Signature"]

    def verify(self, token: str) -> bool:
        """Extract signature and verify header+payload

        :param token: Token string
        :return: True if valid, otherwise false
        """

        token, signature = token.rsplit(".", 1)

        return self.client.verify(
            KeyId=self.arn,
            Message=token,
            MessageType="RAW",
            Signature=base64.urlsafe_b64decode(signature),
            SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256",
        )["SignatureValid"]
