# Bundled Tiktoken Cache

This directory contains bundled tiktoken encoding files for offline operation.

## Purpose

When Cortex is used in environments where network access to OpenAI's blob storage is unavailable (e.g., certain VPNs, firewalls, or offline environments), these bundled encoding files allow tiktoken to work without network access.

## Populating the Cache

To populate this cache with encoding files, run:

```bash
python scripts/populate_tiktoken_cache.py
```

This will download common encoding files:

- `cl100k_base` - GPT-4, GPT-3.5-turbo, text-embedding-ada-002
- `o200k_base` - GPT-4o models
- `p50k_base` - Codex models

To download specific encodings:

```bash
python scripts/populate_tiktoken_cache.py --encodings cl100k_base o200k_base
```

## How It Works

1. When `TokenCounter` is initialized, it automatically checks for bundled cache
2. If bundled cache exists and contains files, `TIKTOKEN_CACHE_DIR` is set to this directory
3. Tiktoken will use cached files instead of downloading from network
4. If network is unavailable and cache exists, tiktoken works offline

## Package Distribution

When building the Cortex package, ensure this directory is included:

```toml
[tool.setuptools.package-data]
cortex = [
    "resources/tiktoken_cache/*",
]
```

The cache files are automatically included in the package distribution, allowing offline operation out of the box.

## Fallback Behavior

If bundled cache is not available or empty:

- Tiktoken will attempt to download encoding files from network
- If network is unavailable, falls back to word-based token estimation
- System continues to function with reduced accuracy
