#!/usr/bin/env bash
# cortex-context-usage-statusline.sh — tee-style context-occupancy producer.
#
# Reads the harness statusline JSON on stdin, snapshots its context_window
# usage into the project's Cortex cache, and passes stdin through to stdout
# UNCHANGED so an existing statusline renderer downstream still works.
#
# Wiring (Claude Code settings.json):
#
#   Compose with an existing statusline command (recommended):
#     {
#       "statusLine": {
#         "type": "command",
#         "command": "/abs/path/to/Cortex/scripts/cortex-context-usage-statusline.sh | /abs/path/to/existing-statusline.sh"
#       }
#     }
#
#   Telemetry-only (no statusline rendered):
#     "command": "/abs/path/to/Cortex/scripts/cortex-context-usage-statusline.sh > /dev/null"
#
# The snapshot lands in $PROJECT_DIR/.cortex/.cache/session/context-usage-<sid>.json
# — ONE FILE PER HARNESS SESSION (sid = payload session_id, sanitized), so
# concurrent windows never overwrite each other; the Python reader attributes
# occupancy only while exactly one session has TTL-fresh snapshots and fails
# closed (UNAVAILABLE) when two do. Snapshots older than the reader TTL
# (900s) are pruned best-effort on write.
# (schema: {session_id, used_tokens, limit_tokens, used_percentage, as_of,
# source}); the MCP server reads it back for session() health occupancy.
# PROJECT_DIR derives from the payload's .workspace.project_dir (falling back
# to .cwd — the statusline cwd is not guaranteed to be the project root).
# Set CORTEX_CONTEXT_USAGE_PROJECT_DIR to pin the project dir explicitly.
#
# BELIEF: writes use temp file + atomic mv WITHOUT the Python-side cache lock
# (rename is atomic; per-session latest-wins is fine for warn-only telemetry
# — cross-SESSION overwrites cannot happen because filenames are per
# session_id). BELIEF: a payload without a usable context_window OR
# session_id writes nothing (occupancy stays UNAVAILABLE — fail-visible,
# not fail-wrong).
# Every step is best-effort: telemetry failures never break the statusline,
# so `set -e` is intentionally not used.

set -u

TMP_IN="$(mktemp 2>/dev/null)" || { cat; exit 0; }
TMP_OUT=""
cleanup() {
  [ -n "$TMP_IN" ] && rm -f "$TMP_IN"
  [ -n "$TMP_OUT" ] && rm -f "$TMP_OUT"
  return 0
}
trap cleanup EXIT
cat > "$TMP_IN" || { cat "$TMP_IN"; exit 0; }

if command -v jq >/dev/null 2>&1; then
  # First payload's project dir: statusline sends one JSON object per tick;
  # a multi-object stream (as in the committed capture fixture) still works.
  PROJECT_DIR="${CORTEX_CONTEXT_USAGE_PROJECT_DIR:-$(jq -rs \
    '(.[0].workspace.project_dir // .[0].cwd // "") | select(. != "")' \
    "$TMP_IN" 2>/dev/null)}" || PROJECT_DIR=""
  if [ -n "$PROJECT_DIR" ] && [ -d "$PROJECT_DIR" ]; then
    OUT_DIR="$PROJECT_DIR/.cortex/.cache/session"
    if mkdir -p "$OUT_DIR" 2>/dev/null; then
      TMP_OUT="$(mktemp "$OUT_DIR/.context-usage.XXXXXX" 2>/dev/null)" || TMP_OUT=""
      if [ -n "$TMP_OUT" ]; then
        if jq -cs --arg as_of "$(date +%s)" '
          # BELIEF: usage nests under context_window; totals must be numbers.
          # A stream (multi-line capture) keeps only the LAST usable payload
          # — latest-wins, one JSON object per write.
          def usable: has("context_window")
            and ((.session_id // "") != "")
            and (.context_window.total_input_tokens | type == "number")
            and (.context_window.total_output_tokens | type == "number");
          map(select(usable)) | if length == 0 then empty else .[-1] | {
            session_id: (.session_id // ""),
            used_tokens: (.context_window.total_input_tokens
                          + .context_window.total_output_tokens),
            limit_tokens: (if (.context_window.context_window_size | type) == "number"
                           then .context_window.context_window_size
                           else 200000 end),
            used_percentage: (if (.context_window.context_window_size | type) == "number"
                              and .context_window.context_window_size > 0
                              then ((.context_window.total_input_tokens
                                     + .context_window.total_output_tokens)
                                    / .context_window.context_window_size * 100)
                              else null end),
            as_of: ($as_of | tonumber),
            source: "statusline"
          } end' "$TMP_IN" > "$TMP_OUT" 2>/dev/null && [ -s "$TMP_OUT" ]; then
          SID="$(jq -r '.session_id // ""' "$TMP_OUT" 2>/dev/null)" || SID=""
          # AI: per-host-session filename — concurrent windows keep separate
          # files; the Python reader refuses ambiguity (UNAVAILABLE).
          SAFE_SID="$(printf '%s' "$SID" | tr -c 'A-Za-z0-9._-' '-' | cut -c1-64)"
          if [ -n "$SAFE_SID" ]; then
            mv -f "$TMP_OUT" "$OUT_DIR/context-usage-${SAFE_SID}.json"
            TMP_OUT=""
            # AI: prune snapshots older than the reader TTL (900s = 15 min,
            # CONTEXT_USAGE_STALE_AFTER_SECONDS) so files do not accumulate.
            find "$OUT_DIR" -maxdepth 1 -name 'context-usage-*.json' \
              -mmin +15 -delete 2>/dev/null
          else
            rm -f "$TMP_OUT"
            TMP_OUT=""
          fi
        else
          rm -f "$TMP_OUT"
          TMP_OUT=""
        fi
      fi
    fi
  fi
fi

cat "$TMP_IN"
