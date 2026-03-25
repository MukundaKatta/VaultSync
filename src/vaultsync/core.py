"""Core VaultSync engine for managing, encrypting, and syncing environment variables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError, create_model

from vaultsync.utils import (
    decrypt_symmetric,
    encrypt_symmetric,
    generate_diff_report,
    parse_env_file,
    serialize_env_file,
)


class EnvStats(BaseModel):
    """Statistics about a set of environment variables."""

    total_vars: int = 0
    encrypted_count: int = 0
    empty_count: int = 0
    unique_prefixes: list[str] = []
    avg_value_length: float = 0.0


class VaultSync:
    """Main class for environment variable management, encryption, and syncing.

    Provides methods to load, save, encrypt, decrypt, diff, merge,
    validate, sync, and export environment variables.

    Args:
        encryption_key: The symmetric key used for encrypt/decrypt operations.
                        If not provided, encrypt/decrypt will raise an error.
    """

    ENCRYPTED_PREFIX = "vault:"

    def __init__(self, encryption_key: str | None = None) -> None:
        self._encryption_key = encryption_key

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def load_env(self, path: str | Path) -> dict[str, str]:
        """Load environment variables from a .env file.

        Args:
            path: Path to the .env file.

        Returns:
            Dictionary of variable name to value.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Env file not found: {filepath}")
        content = filepath.read_text(encoding="utf-8")
        return parse_env_file(content)

    def save_env(self, vars: dict[str, str], path: str | Path) -> Path:
        """Save environment variables to a .env file.

        Args:
            vars: Dictionary of variable name to value.
            path: Destination file path.

        Returns:
            The Path object of the written file.
        """
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        content = serialize_env_file(vars)
        filepath.write_text(content, encoding="utf-8")
        return filepath

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------

    def _require_key(self) -> str:
        if self._encryption_key is None:
            raise ValueError("Encryption key is required. Pass it to VaultSync(encryption_key=...).")
        return self._encryption_key

    def encrypt_value(self, value: str, key: str | None = None) -> str:
        """Encrypt a single value using symmetric encryption.

        Args:
            value: The plaintext value to encrypt.
            key: Optional override key. Falls back to instance key.

        Returns:
            Encrypted string prefixed with ``vault:``.
        """
        actual_key = key or self._require_key()
        encrypted = encrypt_symmetric(value, actual_key)
        return f"{self.ENCRYPTED_PREFIX}{encrypted}"

    def decrypt_value(self, encrypted: str, key: str | None = None) -> str:
        """Decrypt a value previously encrypted by :meth:`encrypt_value`.

        Args:
            encrypted: The encrypted string (with or without ``vault:`` prefix).
            key: Optional override key. Falls back to instance key.

        Returns:
            The original plaintext value.
        """
        actual_key = key or self._require_key()
        raw = encrypted.removeprefix(self.ENCRYPTED_PREFIX)
        return decrypt_symmetric(raw, actual_key)

    # ------------------------------------------------------------------
    # Diff & Merge
    # ------------------------------------------------------------------

    def diff_envs(self, env1: dict[str, str], env2: dict[str, str]) -> dict[str, Any]:
        """Compute the difference between two sets of environment variables.

        Returns a dict with keys ``added``, ``removed``, ``changed``, ``unchanged``.
        """
        all_keys = set(env1.keys()) | set(env2.keys())
        added: dict[str, str] = {}
        removed: dict[str, str] = {}
        changed: dict[str, dict[str, str]] = {}
        unchanged: list[str] = []

        for k in sorted(all_keys):
            in1 = k in env1
            in2 = k in env2
            if in1 and not in2:
                removed[k] = env1[k]
            elif in2 and not in1:
                added[k] = env2[k]
            elif env1[k] != env2[k]:
                changed[k] = {"from": env1[k], "to": env2[k]}
            else:
                unchanged.append(k)

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged": unchanged,
        }

    def merge_envs(
        self, base: dict[str, str], override: dict[str, str]
    ) -> dict[str, str]:
        """Merge two env dicts. Values in *override* take precedence.

        Args:
            base: The base set of variables.
            override: Variables that override the base.

        Returns:
            Merged dictionary.
        """
        merged = dict(base)
        merged.update(override)
        return merged

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_env(
        self, vars: dict[str, str], schema: dict[str, Any]
    ) -> list[str]:
        """Validate env vars against a JSON-style schema.

        The schema is a dict mapping variable names to their expected type
        string (``"str"``, ``"int"``, ``"bool"``) or a dict with ``type``
        and ``required`` keys.

        Args:
            vars: The env vars to validate.
            schema: The validation schema.

        Returns:
            A list of error messages (empty if valid).
        """
        errors: list[str] = []

        for var_name, rule in schema.items():
            if isinstance(rule, str):
                rule = {"type": rule, "required": True}

            required = rule.get("required", True)
            expected_type = rule.get("type", "str")

            if var_name not in vars:
                if required:
                    errors.append(f"Missing required variable: {var_name}")
                continue

            value = vars[var_name]

            if expected_type == "int":
                try:
                    int(value)
                except ValueError:
                    errors.append(f"{var_name}: expected int, got '{value}'")
            elif expected_type == "bool":
                if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
                    errors.append(f"{var_name}: expected bool, got '{value}'")

        return errors

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync(self, source: str | Path, target: str | Path) -> dict[str, Any]:
        """Sync environment variables from source into target.

        Loads both files, merges source into target (source wins), and
        writes the result back to the target path.

        Args:
            source: Path to the source .env file.
            target: Path to the target .env file.

        Returns:
            The diff that was applied.
        """
        source_vars = self.load_env(source)

        target_path = Path(target)
        if target_path.exists():
            target_vars = self.load_env(target)
        else:
            target_vars = {}

        diff = self.diff_envs(target_vars, source_vars)
        merged = self.merge_envs(target_vars, source_vars)
        self.save_env(merged, target)
        return diff

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self, vars: dict[str, str] | None = None) -> EnvStats:
        """Return statistics about a set of environment variables.

        Args:
            vars: Dictionary of env vars. If None, returns empty stats.
        """
        if not vars:
            return EnvStats()

        prefixes: set[str] = set()
        encrypted_count = 0
        empty_count = 0
        total_length = 0

        for key, value in vars.items():
            parts = key.split("_", 1)
            if len(parts) > 1:
                prefixes.add(parts[0])

            if value.startswith(self.ENCRYPTED_PREFIX):
                encrypted_count += 1
            if not value:
                empty_count += 1

            total_length += len(value)

        avg_length = total_length / len(vars) if vars else 0.0

        return EnvStats(
            total_vars=len(vars),
            encrypted_count=encrypted_count,
            empty_count=empty_count,
            unique_prefixes=sorted(prefixes),
            avg_value_length=round(avg_length, 2),
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self, vars: dict[str, str], format: str = "json") -> str:
        """Export environment variables to a string in the given format.

        Supported formats: ``json``, ``shell``, ``yaml``.

        Args:
            vars: The env vars to export.
            format: One of ``json``, ``shell``, ``yaml``.

        Returns:
            Formatted string representation.

        Raises:
            ValueError: If the format is not supported.
        """
        fmt = format.lower()

        if fmt == "json":
            return json.dumps(vars, indent=2, sort_keys=True)

        if fmt == "shell":
            lines = [f'export {k}="{v}"' for k, v in sorted(vars.items())]
            return "\n".join(lines) + "\n"

        if fmt == "yaml":
            lines = [f"{k}: \"{v}\"" for k, v in sorted(vars.items())]
            return "\n".join(lines) + "\n"

        raise ValueError(f"Unsupported export format: {format!r}. Use json, shell, or yaml.")

    # ------------------------------------------------------------------
    # Diff report (text)
    # ------------------------------------------------------------------

    def diff_report(self, env1: dict[str, str], env2: dict[str, str]) -> str:
        """Generate a human-readable diff report between two env sets."""
        diff = self.diff_envs(env1, env2)
        return generate_diff_report(diff)
