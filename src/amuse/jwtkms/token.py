import json
import base64
import collections

from .kms import KmsManager

TokenHeader = collections.namedtuple("TokenHeader", ["alg", "typ"])
TokenPayload = collections.namedtuple("TokenPayload", ["sub", "exp"])


class Token:
    def __init__(self, kms: KmsManager, header: TokenHeader, payload: TokenPayload):
        """Token that can be signed/verified using KMS

        :param kms: Manager for interacting with AWS KMS
        :param header: Token Header
        :param payload: Token Payload
        """

        self.kms = kms
        self.header = header
        self.payload = payload

    @staticmethod
    def serialize(segment) -> str:
        """Serialize the given segment

        :param segment: Token Segment to serialize
        :return: Serialized segment
        """

        obj = json.dumps(segment).encode()
        return base64.urlsafe_b64encode(obj).decode().rstrip("=")

    @property
    def signature(self) -> bytes:
        """Returns signature of the configured Header and Payload"""
        return self.kms.sign(self.unsigned)

    @property
    def unsigned(self) -> str:
        """Returns an unsigned JWT"""
        header = self.serialize(self.header._asdict())
        payload = self.serialize(self.payload._asdict())
        return f"{header}.{payload}"

    @property
    def signed(self):
        """Returns the signed JWT"""
        signature = base64.urlsafe_b64encode(self.signature).decode()
        return f"{self.unsigned}.{signature}"
