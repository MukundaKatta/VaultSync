# VaultSync Architecture

## Overview

VaultSync is a Python CLI tool for managing, encrypting, and syncing environment variables across projects and environments. It is designed to be lightweight, secure, and easy to integrate into existing DevOps workflows.

## Module Structure

```
src/vaultsync/
  __init__.py    # Package entry, exports VaultSync class
  cli.py         # Typer-based CLI commands
  core.py        # VaultSync class with all business logic
  config.py      # Configuration loading (env vars, TOML files)
  utils.py       # Low-level utilities: parsing, encryption, diff rendering
```

## Core Components

### VaultSync Class (`core.py`)

The central class providing all operations:

| Method           | Description                                      |
|------------------|--------------------------------------------------|
| `load_env()`     | Parse a `.env` file into a dictionary            |
| `save_env()`     | Write a dictionary back to a `.env` file         |
| `encrypt_value()`| Encrypt a value using symmetric encryption       |
| `decrypt_value()`| Decrypt a previously encrypted value             |
| `diff_envs()`    | Compute added/removed/changed/unchanged keys     |
| `merge_envs()`   | Merge two env dicts (override wins)              |
| `validate_env()` | Validate vars against a type schema              |
| `sync()`         | Load source, merge into target, write result     |
| `get_stats()`    | Compute statistics about a set of env vars       |
| `export()`       | Serialize env vars to JSON, YAML, or shell       |

### Encryption Scheme (`utils.py`)

VaultSync uses a simple but effective symmetric encryption approach:

1. **Key Derivation**: PBKDF2-HMAC-SHA256 with a random 16-byte salt and 100,000 iterations produces a 256-bit derived key.
2. **Encryption**: Plaintext is XOR-ed with the derived key (repeating).
3. **Integrity**: HMAC-SHA256 is computed over the ciphertext using the derived key.
4. **Encoding**: `salt + hmac + ciphertext` is base64url-encoded.

Encrypted values are prefixed with `vault:` for easy identification.

### Configuration (`config.py`)

Configuration is resolved in priority order:

1. Environment variables (`VAULTSYNC_ENCRYPTION_KEY`, etc.)
2. TOML config file (`vaultsync.toml`)
3. Built-in defaults

### CLI (`cli.py`)

Built with Typer, exposing commands: `encrypt`, `decrypt`, `diff`, `sync`, `validate`, `export`, `stats`.

## Data Flow

```
.env file  -->  parse_env_file()  -->  dict[str, str]
                                            |
                          +---------+-------+-------+---------+
                          |         |               |         |
                       encrypt   diff/merge     validate   export
                          |         |               |         |
                       vault:...  report/dict    errors     JSON/YAML/shell
```

## Security Considerations

- Encryption keys are never stored in env files or committed to version control.
- HMAC integrity checks prevent tampering with encrypted values.
- PBKDF2 with 100k iterations provides brute-force resistance.
- The `vault:` prefix makes it easy to audit which values are encrypted.

## Testing

Tests are written with pytest and cover encryption round-trips, file I/O, diffing, merging, validation, syncing, export, and stats.
