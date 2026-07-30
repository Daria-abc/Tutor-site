import hashlib
import secrets


def hash_password(password: str) -> str:
    """Хешируем пароль с солью через PBKDF2 (без внешних зависимостей)."""
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, hex_digest = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return secrets.compare_digest(digest.hex(), hex_digest)


def generate_hex_id() -> str:
    """16 шестнадцатеричных символов - уникальный ID, который система хранит,
    но никогда не показывает пользователю."""
    return secrets.token_hex(8)


def generate_session_token() -> str:
    return secrets.token_hex(32)
