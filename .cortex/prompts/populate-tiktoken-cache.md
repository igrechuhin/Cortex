# Populate Tiktoken Cache

**AI EXECUTION COMMAND**: Populate bundled tiktoken cache with encoding files for offline operation.

**CRITICAL**: This command is ONLY executed when explicitly invoked by the user or when tiktoken cache is missing. Once invoked, execute all steps AUTOMATICALLY without asking for additional permission or confirmation.

**Tooling Note**: Use standard Cursor tools (`Read`, `ApplyPatch`, `Write`, `LS`, `Glob`, `Grep`) by default; MCP filesystem tools are optional fallbacks only when standard tools are unavailable or explicitly requested.

## When This Prompt Appears

This prompt is conditionally registered and only appears when:

- Bundled tiktoken cache is not available or empty
- Token counting may be slower or less accurate without cached encoding files
- Network access may be restricted (VPN, offline environments)

## Steps

1. **Check cache status** - Verify bundled cache directory exists and check if it's empty:
   - Check if `src/cortex/resources/tiktoken_cache/` directory exists
   - List files in cache directory to see if it's empty
   - If directory doesn't exist, create it

2. **Download encoding files** - Download common tiktoken encoding files:
   - Run `python3 scripts/populate_tiktoken_cache.py` to download default encodings:
     - `cl100k_base` (used by GPT-4, Claude, most modern models)
     - `o200k_base` (used by some newer models)
     - `p50k_base` (legacy encoding)
   - Or specify custom encodings: `python3 scripts/populate_tiktoken_cache.py --encodings cl100k_base o200k_base`

3. **Verify cache population** - Confirm files were downloaded:
   - List files in `src/cortex/resources/tiktoken_cache/` directory
   - Verify cache files exist (tiktoken uses SHA-1 hash of URL as filename)
   - Check file sizes are reasonable (encoding files are typically 100KB-500KB)

4. **Test token counting** - Verify token counter works with cached files:
   - Import TokenCounter and test with a sample string
   - Verify no network requests are made (if network unavailable)
   - Confirm token counts are accurate

## Expected Output

After successful cache population:

```json
{
  "status": "success",
  "message": "Tiktoken cache populated successfully",
  "cache_directory": "src/cortex/resources/tiktoken_cache/",
  "encodings_downloaded": ["cl100k_base", "o200k_base", "p50k_base"],
  "files_created": 3,
  "total_size_bytes": 524288
}
```

## Error Handling

If download fails:

- Check network connectivity
- Verify URLs are accessible
- Try downloading encodings one at a time
- Report which encodings failed and why

If cache directory creation fails:

- Check file system permissions
- Verify project structure is correct
- Report specific error message

## Notes

- Cache files are stored in `src/cortex/resources/tiktoken_cache/`
- Tiktoken automatically uses cached files if `TIKTOKEN_CACHE_DIR` environment variable is set
- Cache files are included in package distribution via `pyproject.toml` resources
- Running this script during package build ensures encoding files are bundled with distribution
