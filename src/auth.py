# -*- coding: utf-8 -*-
"""
Authentication helpers for cookie-backed multi-user web sessions.

Phase 2 keeps the existing admin credential file for bootstrap compatibility,
while normalizing runtime identity around ``app_users`` + signed session cookies.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)
from src.utils.dotenv_loader import read_dotenv_values
from src.multi_user import (
    BOOTSTRAP_ADMIN_DISPLAY_NAME,
    BOOTSTRAP_ADMIN_USER_ID,
    BOOTSTRAP_ADMIN_USERNAME,
    ROLE_ADMIN,
    normalize_role,
)

COOKIE_NAME = "dsa_session"
PBKDF2_ITERATIONS = 100_000
RATE_LIMIT_WINDOW_SEC = 300
RATE_LIMIT_MAX_FAILURES = 5
SESSION_MAX_AGE_HOURS_DEFAULT = 24
ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT = 120
ADMIN_UNLOCK_TOKEN_PURPOSE = "admin_settings_unlock"
MIN_PASSWORD_LEN = 6
SESSION_TOKEN_VERSION = "v2"
SESSION_KIND = "session"
ADMIN_UNLOCK_KIND = "admin_unlock"

# Lazy-loaded state
_auth_enabled: Optional[bool] = None
_session_secret: Optional[bytes] = None
_password_hash_salt: Optional[bytes] = None
_password_hash_stored: Optional[bytes] = None
_rate_limit: dict[str, Tuple[int, float]] = {}
_rate_limit_lock = None


@dataclass(frozen=True)
class SessionIdentity:
    """Resolved identity carried by a signed cookie or unlock token."""

    user_id: str
    username: str
    role: str
    session_id: Optional[str]
    issued_at: int
    expires_at: int
    token_kind: str = SESSION_KIND
    legacy_admin: bool = False
    transitional: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


def _get_lock():
    """Lazy init threading lock for rate limit dict."""
    global _rate_limit_lock
    if _rate_limit_lock is None:
        import threading
        _rate_limit_lock = threading.Lock()
    return _rate_limit_lock


def _ensure_env_loaded() -> None:
    """Ensure .env is loaded before reading config."""
    from src.config import setup_env
    setup_env()


def _get_data_dir() -> Path:
    """Return DATA_DIR as parent of DATABASE_PATH."""
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    return Path(db_path).resolve().parent


def _get_credential_path() -> Path:
    """Path to stored password hash file."""
    return _get_data_dir() / ".admin_password_hash"


def _is_auth_enabled_from_env() -> bool:
    """Read ADMIN_AUTH_ENABLED from .env file."""
    _ensure_env_loaded()
    env_file = os.getenv("ENV_FILE")
    env_path = Path(env_file) if env_file else Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return False
    values = read_dotenv_values(env_path)
    val = (values.get("ADMIN_AUTH_ENABLED") or "").strip().lower()
    return val in ("true", "1", "yes")


def rotate_session_secret() -> bool:
    """Rotate the session signing secret to invalidate all active sessions."""
    global _session_secret
    data_dir = _get_data_dir()
    secret_path = data_dir / ".session_secret"
    data_dir.mkdir(parents=True, exist_ok=True)
    new_secret = secrets.token_bytes(32)
    try:
        tmp_path = secret_path.with_suffix(".tmp")
        tmp_path.write_bytes(new_secret)
        tmp_path.chmod(0o600)
        tmp_path.replace(secret_path)
        _session_secret = new_secret
        logger.info("Session secret rotated successfully")
        return True
    except OSError as e:
        logger.error("Failed to rotate .session_secret: %s", e)
        return False


def _load_session_secret() -> Optional[bytes]:
    """Load or create session secret."""
    global _session_secret
    if _session_secret is not None:
        return _session_secret

    data_dir = _get_data_dir()
    secret_path = data_dir / ".session_secret"

    try:
        if secret_path.exists():
            _session_secret = secret_path.read_bytes()
            if len(_session_secret) != 32:
                logger.warning("Invalid .session_secret length, regenerating")
                _session_secret = None
                if rotate_session_secret():
                    return _session_secret
                return None
            return _session_secret

        data_dir.mkdir(parents=True, exist_ok=True)
        new_secret = secrets.token_bytes(32)
        try:
            with open(secret_path, "xb") as f:
                f.write(new_secret)
            secret_path.chmod(0o600)
        except FileExistsError:
            _session_secret = secret_path.read_bytes()
        else:
            _session_secret = new_secret
        return _session_secret
    except OSError as e:
        logger.error("Failed to create or read .session_secret: %s", e)
        return None


def _parse_password_hash(value: str) -> Optional[Tuple[bytes, bytes]]:
    """Parse salt_b64:hash_b64. Returns (salt, hash) or None."""
    if not value or ":" not in value:
        return None
    parts = value.strip().split(":", 1)
    if len(parts) != 2:
        return None
    try:
        salt_b64, hash_b64 = parts[0].strip(), parts[1].strip()
        salt = base64.standard_b64decode(salt_b64)
        stored_hash = base64.standard_b64decode(hash_b64)
        if salt and stored_hash:
            return (salt, stored_hash)
    except (ValueError, TypeError):
        pass
    return None


def _verify_password_hash(submitted: str, salt: bytes, stored_hash: bytes) -> bool:
    """Verify submitted password against stored pbkdf2 hash."""
    computed = hashlib.pbkdf2_hmac(
        "sha256",
        submitted.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(computed, stored_hash)


def _build_password_hash_entry(password: str) -> str:
    """Build the persisted salt:hash entry used by admin and app-user credentials."""
    salt = secrets.token_bytes(32)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.standard_b64encode(salt).decode("ascii")
    hash_b64 = base64.standard_b64encode(derived).decode("ascii")
    return f"{salt_b64}:{hash_b64}"


def verify_password_hash_string(submitted: str, stored_value: Optional[str]) -> bool:
    """Verify a password against a persisted app-user/admin hash string."""
    parsed = _parse_password_hash(str(stored_value or "").strip())
    if parsed is None:
        return False
    salt, stored_hash = parsed
    return _verify_password_hash(submitted, salt, stored_hash)


def hash_password_for_storage(password: str) -> str:
    """Create a persisted password-hash string for app users."""
    err = _validate_password(password)
    if err:
        raise ValueError(err)
    return _build_password_hash_entry(password)


def _load_credential_from_file() -> bool:
    """Load credential from file into module globals. Returns True if loaded."""
    global _password_hash_salt, _password_hash_stored

    path = _get_credential_path()
    if not path.exists():
        _password_hash_salt = None
        _password_hash_stored = None
        return False

    try:
        raw = path.read_text().strip()
        parsed = _parse_password_hash(raw)
        if parsed is None:
            logger.warning("Invalid .admin_password_hash format, ignoring")
            return False
        _password_hash_salt, _password_hash_stored = parsed
        return True
    except OSError as e:
        logger.error("Failed to read credential file: %s", e)
        return False


def refresh_auth_state() -> None:
    """Reload auth-related state from disk and env."""
    global _auth_enabled, _session_secret
    _auth_enabled = None
    _session_secret = None
    _load_credential_from_file()


def _sync_bootstrap_admin_password_hash(password_hash: Optional[str]) -> None:
    """Best-effort mirror of the legacy admin credential into app_users."""
    try:
        from src.storage import DatabaseManager

        db = DatabaseManager.get_instance()
        db.create_or_update_app_user(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username=BOOTSTRAP_ADMIN_USERNAME,
            role=ROLE_ADMIN,
            display_name=BOOTSTRAP_ADMIN_DISPLAY_NAME,
            password_hash=password_hash,
            is_active=True,
        )
    except Exception as exc:  # pragma: no cover - defensive sync path
        logger.warning("Failed to sync bootstrap admin credential into app_users: %s", exc)


def ensure_bootstrap_admin_user_password_hash() -> Optional[str]:
    """Mirror the legacy admin password file into the bootstrap admin user when available."""
    if not has_stored_password():
        return None
    path = _get_credential_path()
    try:
        stored_value = path.read_text().strip()
    except OSError:
        return None
    if not stored_value:
        return None
    _sync_bootstrap_admin_password_hash(stored_value)
    return stored_value


def is_auth_enabled() -> bool:
    """Return whether admin authentication is enabled (ADMIN_AUTH_ENABLED=true)."""
    global _auth_enabled
    if _auth_enabled is not None:
        return _auth_enabled
    _auth_enabled = _is_auth_enabled_from_env()
    return _auth_enabled


def has_stored_password() -> bool:
    """Return whether a valid stored password hash exists on disk."""
    return _load_credential_from_file()


def verify_stored_password(password: str) -> bool:
    """Verify password against stored credential even when auth is disabled."""
    if not has_stored_password():
        return False
    return _verify_password_hash(password, _password_hash_salt, _password_hash_stored)


def is_password_set() -> bool:
    """Return whether initial password has been set (credential file exists and valid)."""
    if not is_auth_enabled():
        return False
    return has_stored_password()


def is_password_changeable() -> bool:
    """Return whether password can be changed via web/CLI (always True when auth enabled)."""
    return is_auth_enabled()


def _get_session_secret() -> Optional[bytes]:
    """Return session signing secret."""
    if not is_auth_enabled():
        return None
    return _load_session_secret()


def _get_admin_unlock_secret() -> Optional[bytes]:
    """Return signing secret for admin unlock tokens."""
    return _load_session_secret()


def _get_admin_unlock_max_age_seconds() -> int:
    """Read unlock token ttl from env."""
    try:
        max_age_minutes = int(
            os.getenv("ADMIN_UNLOCK_MAX_AGE_MINUTES", str(ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT))
        )
    except ValueError:
        max_age_minutes = ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT
    return max(60, max_age_minutes * 60)


def _get_session_max_age_seconds() -> int:
    """Read session ttl from env."""
    try:
        max_age_hours = int(os.getenv("ADMIN_SESSION_MAX_AGE_HOURS", str(SESSION_MAX_AGE_HOURS_DEFAULT)))
    except ValueError:
        max_age_hours = SESSION_MAX_AGE_HOURS_DEFAULT
    return max(300, max_age_hours * 3600)


def get_session_expiry_datetime() -> datetime:
    """Return the UTC expiration timestamp for a newly created app-user session."""
    return datetime.now(timezone.utc) + timedelta(seconds=_get_session_max_age_seconds())


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _sign_payload(secret: bytes, payload: str) -> str:
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_token_payload(payload: dict) -> str:
    return _urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def _decode_token_payload(value: str) -> Optional[dict]:
    try:
        raw = _urlsafe_b64decode(value)
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _build_signed_token(payload: dict) -> str:
    secret = _get_session_secret()
    if not secret:
        return ""
    encoded_payload = _encode_token_payload(payload)
    signature = _sign_payload(secret, encoded_payload)
    return f"{SESSION_TOKEN_VERSION}.{encoded_payload}.{signature}"


def _build_identity_payload(
    *,
    token_kind: str,
    user_id: str,
    username: str,
    role: str,
    session_id: Optional[str],
    issued_at: Optional[int] = None,
    expires_at: Optional[int] = None,
) -> dict:
    issued_at = int(issued_at or time.time())
    if expires_at is None:
        ttl = _get_admin_unlock_max_age_seconds() if token_kind == ADMIN_UNLOCK_KIND else _get_session_max_age_seconds()
        expires_at = issued_at + ttl
    return {
        "kind": token_kind,
        "uid": user_id,
        "usr": username,
        "role": normalize_role(role, default=ROLE_ADMIN),
        "sid": session_id,
        "iat": issued_at,
        "exp": int(expires_at),
        "purpose": ADMIN_UNLOCK_TOKEN_PURPOSE if token_kind == ADMIN_UNLOCK_KIND else None,
    }


def _resolve_v2_identity(value: str, *, expected_kind: str) -> Optional[SessionIdentity]:
    secret = _get_session_secret()
    if not secret or not value:
        return None
    parts = value.split(".")
    if len(parts) != 3 or parts[0] != SESSION_TOKEN_VERSION:
        return None
    _, payload_b64, signature = parts
    expected_signature = _sign_payload(secret, payload_b64)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    payload = _decode_token_payload(payload_b64)
    if not payload:
        return None
    token_kind = str(payload.get("kind") or "").strip()
    if token_kind != expected_kind:
        return None
    if token_kind == ADMIN_UNLOCK_KIND and payload.get("purpose") != ADMIN_UNLOCK_TOKEN_PURPOSE:
        return None
    try:
        issued_at = int(payload.get("iat"))
        expires_at = int(payload.get("exp"))
    except (TypeError, ValueError):
        return None
    if time.time() > expires_at:
        return None
    user_id = str(payload.get("uid") or "").strip()
    username = str(payload.get("usr") or "").strip()
    if not user_id or not username:
        return None
    try:
        role = normalize_role(payload.get("role"), default=ROLE_ADMIN)
    except ValueError:
        return None
    session_id = str(payload.get("sid") or "").strip() or None

    if token_kind == SESSION_KIND and session_id:
        try:
            from src.storage import DatabaseManager

            db = DatabaseManager.get_instance()
            session_row = db.get_app_user_session(session_id)
            if session_row is None or session_row.user_id != user_id:
                return None
            if session_row.revoked_at is not None:
                return None
            expires_at_dt = getattr(session_row, "expires_at", None)
            if isinstance(expires_at_dt, datetime):
                now_utc = datetime.now(timezone.utc)
                expires_at_check = expires_at_dt if expires_at_dt.tzinfo else expires_at_dt.replace(tzinfo=timezone.utc)
                if now_utc > expires_at_check:
                    return None
        except Exception as exc:  # pragma: no cover - defensive validation path
            logger.warning("Failed to validate app_user_session %s: %s", session_id, exc)
            return None

    return SessionIdentity(
        user_id=user_id,
        username=username,
        role=role,
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
        token_kind=token_kind,
    )


def _resolve_legacy_admin_session(value: str) -> Optional[SessionIdentity]:
    secret = _get_session_secret()
    if not secret or not value:
        return None
    parts = value.split(".")
    if len(parts) != 3:
        return None
    nonce, ts_str, sig = parts
    payload = f"{nonce}.{ts_str}"
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        ts = int(ts_str)
    except ValueError:
        return None
    expires_at = ts + _get_session_max_age_seconds()
    if time.time() > expires_at:
        return None
    ensure_bootstrap_admin_user_password_hash()
    return SessionIdentity(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username=BOOTSTRAP_ADMIN_USERNAME,
        role=ROLE_ADMIN,
        session_id=None,
        issued_at=ts,
        expires_at=expires_at,
        token_kind=SESSION_KIND,
        legacy_admin=True,
    )


def get_session_identity(value: str) -> Optional[SessionIdentity]:
    """Resolve the signed cookie into a concrete current-user identity."""
    identity = _resolve_v2_identity(value, expected_kind=SESSION_KIND)
    if identity is not None:
        return identity
    return _resolve_legacy_admin_session(value)


def get_admin_unlock_identity(value: str) -> Optional[SessionIdentity]:
    """Resolve an admin unlock token into the issuing admin identity."""
    identity = _resolve_v2_identity(value, expected_kind=ADMIN_UNLOCK_KIND)
    if identity is not None and identity.is_admin:
        return identity

    secret = _get_admin_unlock_secret()
    if not secret or not value:
        return None

    parts = value.split(".")
    if len(parts) != 4:
        return None

    nonce, ts_str, purpose, sig = parts
    if purpose != ADMIN_UNLOCK_TOKEN_PURPOSE or not nonce:
        return None

    payload = f"{nonce}.{ts_str}.{purpose}"
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None

    try:
        ts = int(ts_str)
    except ValueError:
        return None

    expires_at = ts + _get_admin_unlock_max_age_seconds()
    if time.time() > expires_at:
        return None

    ensure_bootstrap_admin_user_password_hash()
    return SessionIdentity(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username=BOOTSTRAP_ADMIN_USERNAME,
        role=ROLE_ADMIN,
        session_id=None,
        issued_at=ts,
        expires_at=expires_at,
        token_kind=ADMIN_UNLOCK_KIND,
        legacy_admin=True,
    )


def _validate_password(pwd: str) -> Optional[str]:
    """Return error message if invalid, None if valid."""
    if not pwd or not pwd.strip():
        return "密码不能为空"
    if len(pwd) < MIN_PASSWORD_LEN:
        return f"密码至少 {MIN_PASSWORD_LEN} 位"
    return None


def set_initial_password(password: str) -> Optional[str]:
    """
    Set initial password (first-time setup). Returns error message or None on success.
    Atomic write with 0o600 permissions.
    """
    err = _validate_password(password)
    if err:
        return err

    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    cred_path = _get_credential_path()

    content = _build_password_hash_entry(password)

    try:
        tmp_path = cred_path.with_suffix(".tmp")
        tmp_path.write_text(content)
        tmp_path.chmod(0o600)
        tmp_path.replace(cred_path)
        _load_credential_from_file()
        _sync_bootstrap_admin_password_hash(content)
        return None
    except OSError as e:
        logger.error("Failed to write credential file: %s", e)
        return "密码保存失败"


def verify_password(password: str) -> bool:
    """Verify password against stored credential. Constant-time where applicable."""
    if not is_auth_enabled():
        return True
    return verify_stored_password(password)


def change_password(current: str, new: str) -> Optional[str]:
    """
    Change password. Verifies current, writes new hash. Returns error message or None on success.
    """
    if not is_auth_enabled():
        return "认证功能未启用"
    if not is_password_set():
        return "尚未设置密码"

    if not current or not current.strip():
        return "请输入当前密码"
    if not _verify_password_hash(current, _password_hash_salt, _password_hash_stored):
        return "当前密码错误"

    err = _validate_password(new)
    if err:
        return err

    cred_path = _get_credential_path()
    content = _build_password_hash_entry(new)

    try:
        tmp_path = cred_path.with_suffix(".tmp")
        tmp_path.write_text(content)
        tmp_path.chmod(0o600)
        tmp_path.replace(cred_path)
        # Reload into memory so subsequent verify_password uses new hash
        _load_credential_from_file()
        _sync_bootstrap_admin_password_hash(content)
        return None
    except OSError as e:
        logger.error("Failed to write credential file: %s", e)
        return "密码保存失败"


def create_session(
    *,
    user_id: str = BOOTSTRAP_ADMIN_USER_ID,
    username: str = BOOTSTRAP_ADMIN_USERNAME,
    role: str = ROLE_ADMIN,
    session_id: Optional[str] = None,
    issued_at: Optional[int] = None,
    expires_at: Optional[int] = None,
) -> str:
    """Create a signed identity-bearing session cookie."""
    payload = _build_identity_payload(
        token_kind=SESSION_KIND,
        user_id=user_id,
        username=username,
        role=role,
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return _build_signed_token(payload)


def create_admin_unlock_token(
    *,
    user_id: str = BOOTSTRAP_ADMIN_USER_ID,
    username: str = BOOTSTRAP_ADMIN_USERNAME,
    role: str = ROLE_ADMIN,
    issued_at: Optional[int] = None,
    expires_at: Optional[int] = None,
) -> str:
    """Create a signed admin-unlock token bound to an admin identity."""
    payload = _build_identity_payload(
        token_kind=ADMIN_UNLOCK_KIND,
        user_id=user_id,
        username=username,
        role=role,
        session_id=None,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return _build_signed_token(payload)


def verify_session(value: str) -> bool:
    """Verify session cookie and check expiry + revocation."""
    return get_session_identity(value) is not None


def verify_admin_unlock_token(value: str) -> bool:
    """Verify signed admin-unlock token and enforce expiry."""
    identity = get_admin_unlock_identity(value)
    return identity is not None and identity.is_admin


def get_client_ip(request) -> str:
    """Get client IP, respecting TRUST_X_FORWARDED_FOR."""
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "127.0.0.1"
    return "127.0.0.1"


def check_rate_limit(ip: str) -> bool:
    """Return True if under limit, False if rate limited."""
    lock = _get_lock()
    now = time.time()
    with lock:
        expired_keys = [k for k, (_, ts) in _rate_limit.items() if now - ts > RATE_LIMIT_WINDOW_SEC]
        for k in expired_keys:
            del _rate_limit[k]
        if ip in _rate_limit:
            count, first_ts = _rate_limit[ip]
            if count >= RATE_LIMIT_MAX_FAILURES:
                return False
        return True


def record_login_failure(ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    lock = _get_lock()
    now = time.time()
    with lock:
        if ip in _rate_limit:
            count, first_ts = _rate_limit[ip]
            if now - first_ts > RATE_LIMIT_WINDOW_SEC:
                _rate_limit[ip] = (1, now)
            else:
                _rate_limit[ip] = (count + 1, first_ts)
        else:
            _rate_limit[ip] = (1, now)


def clear_rate_limit(ip: str) -> None:
    """Clear rate limit for IP after successful login."""
    lock = _get_lock()
    with lock:
        _rate_limit.pop(ip, None)


def overwrite_password(new_password: str) -> Optional[str]:
    """
    Overwrite stored password without verifying current. For CLI reset only.
    Returns error message or None on success.
    """
    if not is_auth_enabled():
        return "认证功能未启用"
    err = _validate_password(new_password)
    if err:
        return err

    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    cred_path = _get_credential_path()

    content = _build_password_hash_entry(new_password)

    try:
        tmp_path = cred_path.with_suffix(".tmp")
        tmp_path.write_text(content)
        tmp_path.chmod(0o600)
        tmp_path.replace(cred_path)
        _load_credential_from_file()
        _sync_bootstrap_admin_password_hash(content)
        return None
    except OSError as e:
        logger.error("Failed to write credential file: %s", e)
        return "密码保存失败"


def reset_password_cli() -> int:
    """Interactive CLI to reset password. Returns exit code."""
    _ensure_env_loaded()
    if not _is_auth_enabled_from_env():
        print("Error: Auth is not enabled. Set ADMIN_AUTH_ENABLED=true in .env", file=sys.stderr)
        return 1

    print("Enter new admin password (will not echo):", end=" ")
    pwd = getpass.getpass("")
    err = _validate_password(pwd)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("Confirm new password:", end=" ")
    pwd2 = getpass.getpass("")
    if pwd != pwd2:
        print("Error: Passwords do not match", file=sys.stderr)
        return 1

    err = overwrite_password(pwd)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("Password has been reset successfully.")
    return 0


def _main() -> int:
    """CLI entry: reset_password subcommand."""
    if len(sys.argv) > 1 and sys.argv[1] == "reset_password":
        return reset_password_cli()
    print("Usage: python -m src.auth reset_password", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_main())
