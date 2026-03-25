"""Tests for VaultSync core functionality."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from vaultsync.core import VaultSync


@pytest.fixture
def vs() -> VaultSync:
    return VaultSync(encryption_key="test-secret-key-2026")


@pytest.fixture
def sample_env(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgres://localhost/db\n"
        "API_KEY=secret123\n"
        "DEBUG=true\n"
        "EMPTY_VAR=\n"
    )
    return env_file


# ------------------------------------------------------------------
# Test: encrypt / decrypt round-trip
# ------------------------------------------------------------------


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self, vs: VaultSync) -> None:
        original = "my-super-secret-password"
        encrypted = vs.encrypt_value(original)
        assert encrypted.startswith("vault:")
        decrypted = vs.decrypt_value(encrypted)
        assert decrypted == original

    def test_encrypt_with_custom_key(self, vs: VaultSync) -> None:
        value = "another-secret"
        custom_key = "custom-key-override"
        encrypted = vs.encrypt_value(value, key=custom_key)
        decrypted = vs.decrypt_value(encrypted, key=custom_key)
        assert decrypted == value

    def test_decrypt_wrong_key_fails(self, vs: VaultSync) -> None:
        encrypted = vs.encrypt_value("secret")
        wrong_vs = VaultSync(encryption_key="wrong-key")
        with pytest.raises(ValueError, match="integrity check failed"):
            wrong_vs.decrypt_value(encrypted)

    def test_encrypt_requires_key(self) -> None:
        vs_no_key = VaultSync()
        with pytest.raises(ValueError, match="Encryption key is required"):
            vs_no_key.encrypt_value("test")


# ------------------------------------------------------------------
# Test: load / save env files
# ------------------------------------------------------------------


class TestEnvIO:
    def test_load_env(self, vs: VaultSync, sample_env: Path) -> None:
        env_vars = vs.load_env(sample_env)
        assert env_vars["DATABASE_URL"] == "postgres://localhost/db"
        assert env_vars["API_KEY"] == "secret123"
        assert env_vars["DEBUG"] == "true"
        assert env_vars["EMPTY_VAR"] == ""

    def test_save_and_reload(self, vs: VaultSync, tmp_path: Path) -> None:
        original = {"FOO": "bar", "BAZ": "qux with spaces"}
        out_path = tmp_path / "out.env"
        vs.save_env(original, out_path)
        reloaded = vs.load_env(out_path)
        assert reloaded["FOO"] == "bar"
        assert reloaded["BAZ"] == "qux with spaces"

    def test_load_missing_file_raises(self, vs: VaultSync) -> None:
        with pytest.raises(FileNotFoundError):
            vs.load_env("/nonexistent/.env")


# ------------------------------------------------------------------
# Test: diff, merge, validate
# ------------------------------------------------------------------


class TestDiffMergeValidate:
    def test_diff_envs(self, vs: VaultSync) -> None:
        env1 = {"A": "1", "B": "2", "C": "3"}
        env2 = {"A": "1", "B": "changed", "D": "4"}
        diff = vs.diff_envs(env1, env2)
        assert "C" in diff["removed"]
        assert "D" in diff["added"]
        assert "B" in diff["changed"]
        assert "A" in diff["unchanged"]

    def test_merge_envs(self, vs: VaultSync) -> None:
        base = {"A": "1", "B": "2"}
        override = {"B": "override", "C": "3"}
        merged = vs.merge_envs(base, override)
        assert merged == {"A": "1", "B": "override", "C": "3"}

    def test_validate_env_missing_required(self, vs: VaultSync) -> None:
        vars = {"PORT": "8080"}
        schema = {"PORT": "int", "DATABASE_URL": "str"}
        errors = vs.validate_env(vars, schema)
        assert any("DATABASE_URL" in e for e in errors)

    def test_validate_env_type_mismatch(self, vs: VaultSync) -> None:
        vars = {"PORT": "not-a-number"}
        schema = {"PORT": "int"}
        errors = vs.validate_env(vars, schema)
        assert any("expected int" in e for e in errors)

    def test_validate_env_passes(self, vs: VaultSync) -> None:
        vars = {"PORT": "8080", "DEBUG": "true"}
        schema = {"PORT": "int", "DEBUG": "bool"}
        errors = vs.validate_env(vars, schema)
        assert errors == []


# ------------------------------------------------------------------
# Test: sync
# ------------------------------------------------------------------


class TestSync:
    def test_sync_creates_target(self, vs: VaultSync, sample_env: Path, tmp_path: Path) -> None:
        target = tmp_path / "target.env"
        diff = vs.sync(sample_env, target)
        assert target.exists()
        target_vars = vs.load_env(target)
        assert "DATABASE_URL" in target_vars

    def test_sync_merges(self, vs: VaultSync, tmp_path: Path) -> None:
        src = tmp_path / "src.env"
        tgt = tmp_path / "tgt.env"
        src.write_text("A=from_source\nB=new\n")
        tgt.write_text("A=from_target\nC=existing\n")
        vs.sync(src, tgt)
        result = vs.load_env(tgt)
        assert result["A"] == "from_source"
        assert result["B"] == "new"
        assert result["C"] == "existing"


# ------------------------------------------------------------------
# Test: export and stats
# ------------------------------------------------------------------


class TestExportStats:
    def test_export_json(self, vs: VaultSync) -> None:
        vars = {"KEY": "value"}
        output = vs.export(vars, "json")
        parsed = json.loads(output)
        assert parsed["KEY"] == "value"

    def test_export_shell(self, vs: VaultSync) -> None:
        output = vs.export({"MY_VAR": "hello"}, "shell")
        assert 'export MY_VAR="hello"' in output

    def test_export_invalid_format(self, vs: VaultSync) -> None:
        with pytest.raises(ValueError):
            vs.export({}, "xml")

    def test_get_stats(self, vs: VaultSync) -> None:
        vars = {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "API_KEY": "vault:encrypted",
            "EMPTY": "",
        }
        stats = vs.get_stats(vars)
        assert stats.total_vars == 4
        assert stats.encrypted_count == 1
        assert stats.empty_count == 1
        assert "DB" in stats.unique_prefixes
