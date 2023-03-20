from uuid import uuid4
from datetime import datetime, timedelta

import jwt
import boto3

from django.contrib.auth import tokens
from django.utils.crypto import constant_time_compare, salted_hmac
from django.conf import settings
from jwt.exceptions import (
    ExpiredSignature,
    InvalidSignatureError,
    MissingRequiredClaimError,
    DecodeError,
)

from amuse.jwtkms import Token, TokenHeader, TokenPayload, KmsManager


class EmailVerificationTokenGenerator:
    key_salt = 'amuse.tokens.EmailVerificationTokenGenerator'

    def make_token(self, user):
        return salted_hmac(
            self.key_salt, str(user.id) + str(user.email_verified) + user.email
        ).hexdigest()[::2]

    def check_token(self, user, token):
        if not (user and token):
            return False
        return constant_time_compare(self.make_token(user), token)


class WithdrawalVerificationTokenGenerator:
    key_salt = 'amuse.tokens.WithdrawalVerificationTokenGenerator'

    def make_token(self, transaction):
        return salted_hmac(
            self.key_salt,
            f'{transaction.id}{transaction.amount}{transaction.withdrawal.email}',
        ).hexdigest()[::2]

    def check_token(self, transaction, token):
        if not (transaction and token):
            return False
        return constant_time_compare(self.make_token(transaction), token)


class PasswordResetTokenGenerator(tokens.PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        """
        The system does not track the last login timestamp, so we override
        this method so that it does not take it into account.
        """
        return str(user.pk) + user.password + str(timestamp)


class UserInvitationTokenGenerator:
    secret = settings.JWT_SECRET

    def make_token(self, payload):
        # Add 'jti' and 'iat' claims to the token
        if isinstance(payload, dict):
            if 'jti' not in payload:
                payload['jti'] = uuid4().hex[::4]
            if 'iat' not in payload:
                payload['iat'] = datetime.utcnow()
        return jwt.encode(payload, self.secret, algorithm='HS256').decode('utf-8')

    def decode_token(self, token):
        try:
            return jwt.decode(token, self.secret, algorithms=['HS256'])
        except:
            return None


class PaymentSuccessTransactionIDTokenGenerator:
    secret = settings.JWT_SECRET

    def make_token(self, payload):
        return jwt.encode(payload, self.secret, algorithm='HS256').decode('utf-8')


class OtpTokenGenerator:
    secret = settings.OTP_JWT_SECRET

    def make_token(self, user_id) -> str:
        expr = datetime.utcnow() + timedelta(minutes=int(settings.OTP_JWT_EXP_MINUTES))
        payload = {"exp": expr, "user_id": user_id}
        return jwt.encode(payload, self.secret, algorithm='HS256').decode('utf-8')

    def _decode_token(self, token):
        try:
            return jwt.decode(
                token,
                self.secret,
                algorithms=['HS256'],
                options={"require": ["exp", "user_id"]},
            )
        except (
            ExpiredSignature,
            MissingRequiredClaimError,
            InvalidSignatureError,
            DecodeError,
        ):
            return {}

    def get_user_id(self, token):
        payload = self._decode_token(token)
        return payload.get('user_id')


class AuthTokenGenerator:
    signing_key = settings.AUTH_SIGNING_KEY
    verifying_key = settings.AUTH_VERIFY_KEY

    @classmethod
    def make_token(cls, payload: dict) -> str:
        if payload.get('exp') is None:
            raise MissingRequiredClaimError("exp")
        if payload.get('user_id') is None:
            raise MissingRequiredClaimError("user_id")
        return jwt.encode(payload, cls.signing_key, algorithm='RS256').decode('utf-8')

    @classmethod
    def make_pair(cls, user_id) -> dict:
        return {
            'access': cls.make_access_token(user_id),
            'refresh': cls.make_refresh_token(user_id),
        }

    @classmethod
    def make_access_token(cls, user_id):
        payload = dict()
        payload['user_id'] = user_id
        payload['exp'] = datetime.utcnow() + timedelta(
            minutes=int(settings.ACCESS_TOKEN_EXP_MINUTES)
        )
        return cls.make_token(payload)

    @classmethod
    def make_refresh_token(cls, user_id):
        payload = dict()
        payload['user_id'] = user_id
        payload['exp'] = datetime.utcnow() + timedelta(
            minutes=int(settings.REFRESH_TOKEN_EXP_DAYS)
        )
        return cls.make_token(payload)

    @classmethod
    def _decode_token(cls, token):
        try:
            return jwt.decode(
                token,
                cls.verifying_key,
                algorithms=['RS256'],
                options={"require": ["exp", "user_id"]},
            )
        except (
            ExpiredSignature,
            MissingRequiredClaimError,
            InvalidSignatureError,
            DecodeError,
        ):
            return {}

    @classmethod
    def get_user_id(cls, token):
        payload = cls._decode_token(token)
        return payload.get('user_id')


class KmsJwtManager(AuthTokenGenerator):
    signing_key = None  # Uses KMS SK
    verifying_key = None  # Uses KMS PK
    kms_verify = False  # Whether to verify via KMS

    _kms = KmsManager(
        client=boto3.client("kms", region_name=settings.AWS_REGION),
        arn=settings.JWT_SIGN_VERIFY_KMS_ARN,
    )

    @classmethod
    def make_token(cls, payload: dict) -> str:
        return Token(
            kms=cls._kms,
            header=TokenHeader(alg="RS256", typ="JWT"),
            payload=TokenPayload(
                exp=datetime.timestamp(payload["exp"]), sub=payload["user_id"]
            ),
        ).signed

    @classmethod
    def _decode_token(cls, token):
        try:
            if cls.kms_verify:
                cls._kms.verify(token)
                return jwt.decode(token, verify=False)
            else:
                return jwt.decode(token, key=cls._kms.public_key, verify=True)
        except Exception as e:
            # @TODO: Add logging
            return {}

    @classmethod
    def get_user_id(cls, token):
        decoded = cls._decode_token(token)
        return decoded.get("sub")


email_verification_token_generator = EmailVerificationTokenGenerator()
withdrawal_verification_token_generator = WithdrawalVerificationTokenGenerator()
password_reset_token_generator = PasswordResetTokenGenerator()
user_invitation_token_generator = UserInvitationTokenGenerator()
payment_success_token_generator = PaymentSuccessTransactionIDTokenGenerator()
otp_token_generator = OtpTokenGenerator()
