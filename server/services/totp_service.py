import base64
import hashlib
import hmac
import secrets
import time


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")


def get_totp_uri(email: str, secret: str, issuer: str = "AI-CyberSentinel") -> str:
    import urllib.parse
    params = {
        "secret": secret,
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": 6,
        "period": 30,
    }
    params_str = "&".join(f"{k}={v}" for k, v in params.items())
    return f"otpauth://totp/{urllib.parse.quote(issuer)}:{urllib.parse.quote(email)}?{params_str}"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    if not secret or not code:
        return False
    if not code.isdigit() or len(code) != 6:
        return False

    try:
        decoded_secret = base64.b32decode(secret.upper() + "=" * (8 - len(secret) % 8))
    except Exception:
        return False

    current_time = int(time.time())
    for offset in range(-window, window + 1):
        time_step = (current_time + offset * 30) // 30
        expected = _hotp(decoded_secret, time_step)
        if hmac.compare_digest(code, expected):
            return True
    return False


def _hotp(secret: bytes, counter: int) -> str:
    counter_bytes = counter.to_bytes(8, "big")
    mac = hmac.new(secret, counter_bytes, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    truncated = int.from_bytes(mac[offset:offset + 4], "big") & 0x7FFFFFFF
    return str(truncated % 10**6).zfill(6)


def generate_backup_codes(count: int = 8) -> list[str]:
    codes = []
    for _ in range(count):
        code = "-".join([
            secrets.token_hex(2).upper(),
            secrets.token_hex(2).upper(),
            secrets.token_hex(2).upper(),
        ])
        codes.append(code)
    return codes


def hash_backup_code(code: str) -> str:
    normalized = code.replace("-", "").upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_backup_code(stored_hash: str, code: str) -> bool:
    return hmac.compare_digest(stored_hash, hash_backup_code(code))
