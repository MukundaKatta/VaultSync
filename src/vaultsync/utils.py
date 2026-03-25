"""Utility functions: env file parsing, encryption helpers, diff generation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any


# ---------------------------------------------------------------------------
# Env file parsing
# ---------------------------------------------------------------------------


def parse_env_file(content: str) -> dict[str, str]:
    """Parse a .env file content string into a dictionary.

    Supports:
      - ``KEY=VALUE`` pairs
      - Quoted values (single and double quotes are stripped)
      - Comments (lines starting with ``#``)
      - Blank lines (ignored)
      - Inline comments after unquoted values

    Args:
        content: Raw text of a .env file.

    Returns:
        Ordered dict of variable names to values.
    """
    result: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        else:
            # Remove inline comments for unquoted values
            if " #" in value:
                value = value[: value.index(" #")].rstrip()

        result[key] = value
    return result


def serialize_env_file(vars: dict[str, str]) -> str:
    """Serialize a dictionary of env vars into .env file content.

    Args:
        vars: Dictionary of variable names to values.

    Returns:
        String content suitable for writing to a .env file.
    """
    lines: list[str] = []
    for key in sorted(vars.keys()):
        value = vars[key]
        # Quote values that contain spaces, quotes, or special chars
        needs_quoting = any(c in value for c in (" ", '"', "'", "#", "\n"))
        if needs_quoting:
            escaped = value.replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Encryption helpers (simple symmetric using hashlib)
# ---------------------------------------------------------------------------

_SALT_LENGTH = 16
_KEY_LENGTH = 32
_ITERATIONS = 100_000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a passphrase using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations=_ITERATIONS,
        dklen=_KEY_LENGTH,
    )


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR data with a repeating key (simple symmetric cipher)."""
    key_len = len(key)
    return bytes(d ^ key[i % key_len] for i, d in enumerate(data))


def encrypt_symmetric(plaintext: str, passphrase: str) -> str:
    """Encrypt plaintext using a passphrase-derived key.

    Scheme:
        1. Generate random salt.
        2. Derive key via PBKDF2-HMAC-SHA256.
        3. XOR plaintext bytes with derived key.
        4. Compute HMAC-SHA256 over ciphertext for integrity.
        5. Encode ``salt + hmac + ciphertext`` as URL-safe base64.

    Args:
        plaintext: The string to encrypt.
        passphrase: The passphrase / key.

    Returns:
        Base64-encoded encrypted string.
    """
    salt = os.urandom(_SALT_LENGTH)
    derived = _derive_key(passphrase, salt)
    plaintext_bytes = plaintext.encode("utf-8")

    ciphertext = _xor_bytes(plaintext_bytes, derived)

    mac = hmac.new(derived, ciphertext, hashlib.sha256).digest()

    payload = salt + mac + ciphertext
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_symmetric(encoded: str, passphrase: str) -> str:
    """Decrypt a string encrypted by :func:`encrypt_symmetric`.

    Args:
        encoded: The base64-encoded ciphertext.
        passphrase: The passphrase / key used during encryption.

    Returns:
        The original plaintext.

    Raises:
        ValueError: If the integrity check fails or data is malformed.
    """
    try:
        payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception as exc:
        raise ValueError("Invalid encrypted payload: cannot decode base64.") from exc

    if len(payload) < _SALT_LENGTH + 32:
        raise ValueError("Invalid encrypted payload: too short.")

    salt = payload[:_SALT_LENGTH]
    stored_mac = payload[_SALT_LENGTH : _SALT_LENGTH + 32]
    ciphertext = payload[_SALT_LENGTH + 32 :]

    derived = _derive_key(passphrase, salt)

    expected_mac = hmac.new(derived, ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(stored_mac, expected_mac):
        raise ValueError("Decryption failed: integrity check failed (wrong key?).")

    plaintext_bytes = _xor_bytes(ciphertext, derived)
    return plaintext_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# Diff generation
# ---------------------------------------------------------------------------


def generate_diff_report(diff: dict[str, Any]) -> str:
    """Generate a human-readable diff report from a diff dictionary.

    Args:
        diff: Output of :meth:`VaultSync.diff_envs`.

    Returns:
        Multi-line string report.
    """
    lines: list[str] = []
    lines.append("=== VaultSync Diff Report ===")
    lines.append("")

    added = diff.get("added", {})
    removed = diff.get("removed", {})
    changed = diff.get("changed", {})
    unchanged = diff.get("unchanged", [])

    if added:
        lines.append(f"+ Added ({len(added)}):")
        for k, v in sorted(added.items()):
            lines.append(f"  + {k}={_mask(v)}")
        lines.append("")

    if removed:
        lines.append(f"- Removed ({len(removed)}):")
        for k, v in sorted(removed.items()):
            lines.append(f"  - {k}={_mask(v)}")
        lines.append("")

    if changed:
        lines.append(f"~ Changed ({len(changed)}):")
        for k, info in sorted(changed.items()):
            lines.append(f"  ~ {k}: {_mask(info['from'])} -> {_mask(info['to'])}")
        lines.append("")

    lines.append(f"  Unchanged: {len(unchanged)} variable(s)")
    lines.append("")
    lines.append(f"  Total differences: {len(added) + len(removed) + len(changed)}")

    return "\n".join(lines)


def _mask(value: str, visible: int = 4) -> str:
    """Mask a value for display, showing only the first few characters."""
    if len(value) <= visible:
        return value
    return value[:visible] + "****"
