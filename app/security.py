import secrets

from flask import session
from itsdangerous import BadSignature, URLSafeSerializer


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def _serializer(secret_key: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret_key, salt="wht-csrf")


def generate_csrf_token(secret_key: str) -> str:
    token = _serializer(secret_key).dumps({"nonce": secrets.token_hex(16)})
    session["csrf_token"] = token
    return token


def validate_csrf_token(secret_key: str, token: str | None) -> bool:
    if not token:
        return False
    try:
        _serializer(secret_key).loads(token)
    except BadSignature:
        return False
    return session.get("csrf_token") == token
