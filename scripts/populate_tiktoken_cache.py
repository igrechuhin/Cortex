#!/usr/bin/env python3
"""Script to populate bundled tiktoken cache with encoding files.

This script downloads common tiktoken encoding files and stores them
in the bundled cache directory for offline use.

Run this script during package build to include encoding files in distribution.
"""

import hashlib
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.core.tiktoken_cache import get_bundled_cache_dir


def get_encoding_url(encoding_name: str) -> str:
    """Get URL for tiktoken encoding file.

    Args:
        encoding_name: Name of encoding (e.g., 'cl100k_base')

    Returns:
        URL to encoding file
    """
    return f"https://openaipublic.blob.core.windows.net/encodings/{encoding_name}.tiktoken"


def get_cache_filename(url: str) -> str:
    """Get cache filename for tiktoken encoding file.

    Tiktoken uses SHA-1 hash of the URL as the cache filename.

    Args:
        url: URL to encoding file

    Returns:
        SHA-1 hash of URL (cache filename)
    """
    return hashlib.sha1(url.encode()).hexdigest()


def download_encoding(encoding_name: str, cache_dir: Path) -> bool:
    """Download encoding file and save to cache directory.

    Args:
        encoding_name: Name of encoding (e.g., 'cl100k_base')
        cache_dir: Directory to save cached file

    Returns:
        True if download successful, False otherwise
    """
    import ssl
    import urllib.error
    import urllib.request

    url = get_encoding_url(encoding_name)
    cache_filename = get_cache_filename(url)
    cache_path = cache_dir / cache_filename

    # Skip if already cached
    if cache_path.exists():
        print(f"  ✓ {encoding_name} already cached")
        return True

    try:
        print(f"  Downloading {encoding_name}...")
        # Use urlopen with ssl context to handle certificate verification
        import ssl

        ssl_context = ssl.create_default_context()
        # For development, allow unverified context if default fails
        try:
            with urllib.request.urlopen(url, context=ssl_context) as response:
                with open(cache_path, "wb") as f:
                    f.write(response.read())
        except urllib.error.URLError as ssl_error:
            if "CERTIFICATE" in str(ssl_error).upper():
                # Fallback: use unverified context (for development only)
                print(f"  Warning: SSL verification failed, using unverified context")
                unverified_context = ssl._create_unverified_context()
                with urllib.request.urlopen(url, context=unverified_context) as response:
                    with open(cache_path, "wb") as f:
                        f.write(response.read())
            else:
                raise

        print(f"  ✓ {encoding_name} cached successfully")
        return True
    except Exception as e:
        print(f"  ✗ Failed to download {encoding_name}: {e}")
        return False


def populate_cache(encoding_names: list[str] | None = None) -> bool:
    """Populate bundled cache with encoding files.

    Args:
        encoding_names: List of encoding names to download.
            If None, downloads common encodings: cl100k_base, o200k_base, p50k_base

    Returns:
        True if all downloads successful, False otherwise
    """
    if encoding_names is None:
        encoding_names = ["cl100k_base", "o200k_base", "p50k_base"]

    cache_dir = get_bundled_cache_dir()
    if cache_dir is None:
        print("Error: Bundled cache directory not found")
        return False

    # Ensure cache directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"Populating tiktoken cache in: {cache_dir}")
    print(f"Encoding files to download: {', '.join(encoding_names)}")

    success_count = 0
    for encoding_name in encoding_names:
        if download_encoding(encoding_name, cache_dir):
            success_count += 1

    print(f"\nCompleted: {success_count}/{len(encoding_names)} encodings cached")
    return success_count == len(encoding_names)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Populate bundled tiktoken cache with encoding files"
    )
    parser.add_argument(
        "--encodings",
        nargs="+",
        help="Encoding names to download (default: cl100k_base o200k_base p50k_base)",
    )
    args = parser.parse_args()

    success = populate_cache(args.encodings)
    sys.exit(0 if success else 1)
