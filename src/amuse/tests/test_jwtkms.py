import pytest

from amuse.jwtkms import KmsManager
from amuse.tokens import KmsJwtManager

# Verify via KMS (get_public_key not available with `moto`)
KmsJwtManager.kms_verify = True


def test_decode_get_sub(kms):
    user_id = "test123"
    KmsJwtManager._kms = KmsManager(*kms)
    token = KmsJwtManager.make_access_token(user_id=user_id)
    assert KmsJwtManager.get_user_id(token) == user_id


def test_decode_at(kms):
    KmsJwtManager._kms = KmsManager(*kms)
    token = KmsJwtManager.make_access_token(user_id="test123")
    decoded = KmsJwtManager._decode_token(token)
    assert decoded.keys() >= {"exp", "sub"}


def test_decode_rt(kms):
    KmsJwtManager._kms = KmsManager(*kms)
    token = KmsJwtManager.make_refresh_token(user_id="test123")
    decoded = KmsJwtManager._decode_token(token)
    assert decoded.keys() >= {"exp", "sub"}


def test_sign_ok(token, kms):
    assert KmsManager(*kms).sign(token.unsigned)


def test_verify_ok(token, kms):
    assert KmsManager(*kms).verify(token.signed)


def test_verify_cached(token, kms):
    with pytest.raises(NotImplementedError):
        assert KmsManager(*kms).public_key


def test_verify_invalid_signature(token, kms):
    assert not KmsManager(*kms).verify(token.unsigned + ".asdf")
