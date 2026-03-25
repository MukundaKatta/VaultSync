"""CLI interface for VaultSync powered by Typer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from vaultsync.config import load_config
from vaultsync.core import VaultSync

app = typer.Typer(
    name="vaultsync",
    help="Manage, encrypt, and sync environment variables across projects.",
    add_completion=False,
)


def _get_vs(key: Optional[str] = None) -> VaultSync:
    """Create a VaultSync instance using config + optional CLI key."""
    cfg = load_config()
    encryption_key = key or cfg.encryption_key
    return VaultSync(encryption_key=encryption_key)


@app.command()
def encrypt(
    value: str = typer.Argument(..., help="Plaintext value to encrypt."),
    key: str = typer.Option(..., "--key", "-k", help="Encryption key."),
) -> None:
    """Encrypt a single value."""
    vs = _get_vs(key)
    result = vs.encrypt_value(value)
    typer.echo(result)


@app.command()
def decrypt(
    value: str = typer.Argument(..., help="Encrypted value to decrypt."),
    key: str = typer.Option(..., "--key", "-k", help="Encryption key."),
) -> None:
    """Decrypt a single value."""
    vs = _get_vs(key)
    result = vs.decrypt_value(value)
    typer.echo(result)


@app.command()
def diff(
    file1: Path = typer.Argument(..., help="First .env file."),
    file2: Path = typer.Argument(..., help="Second .env file."),
) -> None:
    """Show differences between two .env files."""
    vs = _get_vs()
    env1 = vs.load_env(file1)
    env2 = vs.load_env(file2)
    report = vs.diff_report(env1, env2)
    typer.echo(report)


@app.command()
def sync(
    source: Path = typer.Argument(..., help="Source .env file."),
    target: Path = typer.Argument(..., help="Target .env file."),
) -> None:
    """Sync source env vars into target (source wins)."""
    vs = _get_vs()
    result = vs.sync(source, target)
    added = len(result.get("added", {}))
    changed = len(result.get("changed", {}))
    typer.echo(f"Synced: {added} added, {changed} changed.")


@app.command()
def validate(
    env_file: Path = typer.Argument(..., help="Path to .env file."),
    schema: Path = typer.Option(..., "--schema", "-s", help="Path to JSON schema file."),
) -> None:
    """Validate an env file against a JSON schema."""
    vs = _get_vs()
    env_vars = vs.load_env(env_file)
    schema_data = json.loads(schema.read_text(encoding="utf-8"))
    errors = vs.validate_env(env_vars, schema_data)
    if errors:
        for err in errors:
            typer.echo(f"  ERROR: {err}", err=True)
        raise typer.Exit(code=1)
    typer.echo("Validation passed.")


@app.command()
def export(
    env_file: Path = typer.Argument(..., help="Path to .env file."),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, shell, yaml."),
) -> None:
    """Export env vars to a specific format."""
    vs = _get_vs()
    env_vars = vs.load_env(env_file)
    output = vs.export(env_vars, format)
    typer.echo(output)


@app.command()
def stats(
    env_file: Path = typer.Argument(..., help="Path to .env file."),
) -> None:
    """Show statistics for an env file."""
    vs = _get_vs()
    env_vars = vs.load_env(env_file)
    st = vs.get_stats(env_vars)
    typer.echo(f"Total variables : {st.total_vars}")
    typer.echo(f"Encrypted       : {st.encrypted_count}")
    typer.echo(f"Empty           : {st.empty_count}")
    typer.echo(f"Avg value length: {st.avg_value_length}")
    typer.echo(f"Prefixes        : {', '.join(st.unique_prefixes) or '(none)'}")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
