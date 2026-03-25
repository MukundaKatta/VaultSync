"""Configuration management for VaultSync."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_CONFIG_FILE = "vaultsync.toml"


class VaultSyncConfig(BaseModel):
    """Global configuration for VaultSync."""

    encryption_key: str | None = Field(
        default=None,
        description="Symmetric encryption key for vault operations.",
    )
    default_format: str = Field(
        default="json",
        description="Default export format (json, shell, yaml).",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level.",
    )
    env_dir: str = Field(
        default=".",
        description="Default directory to look for .env files.",
    )


def load_config(
    config_path: str | Path | None = None,
) -> VaultSyncConfig:
    """Load configuration from environment variables and optional config file.

    Priority (highest to lowest):
        1. Environment variables (VAULTSYNC_*)
        2. Config file values
        3. Defaults

    Args:
        config_path: Optional path to a TOML config file.

    Returns:
        Resolved VaultSyncConfig instance.
    """
    values: dict[str, str] = {}

    # Read from TOML file if it exists
    if config_path is None:
        config_path = Path(DEFAULT_CONFIG_FILE)
    else:
        config_path = Path(config_path)

    if config_path.exists():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        raw = config_path.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
        tool_section = data.get("tool", {}).get("vaultsync", data)
        values.update({k: str(v) for k, v in tool_section.items()})

    # Environment variables override file values
    env_map = {
        "VAULTSYNC_ENCRYPTION_KEY": "encryption_key",
        "VAULTSYNC_EXPORT_FORMAT": "default_format",
        "VAULTSYNC_LOG_LEVEL": "log_level",
        "VAULTSYNC_ENV_DIR": "env_dir",
    }
    for env_var, field_name in env_map.items():
        env_val = os.environ.get(env_var)
        if env_val is not None:
            values[field_name] = env_val

    return VaultSyncConfig(**values)
