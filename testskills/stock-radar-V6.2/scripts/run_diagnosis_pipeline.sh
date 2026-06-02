#!/usr/bin/env bash
# One-click post-bundle pipeline: validate → assemble → format IM → render HTML.
# Agent writes bundle only; this script owns all deterministic downstream steps.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVOCATION_DIR="$(pwd)"

BUNDLE_PATH=""
FETCH_DIR="${STOCK_RADAR_OUT_DIR:-/tmp/stock-radar}"

usage() {
  echo "Usage: bash scripts/run_diagnosis_pipeline.sh <agent.bundle.json> [--fetch-dir DIR]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fetch-dir)
      [[ $# -ge 2 ]] || usage
      FETCH_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      if [[ -z "$BUNDLE_PATH" ]]; then
        BUNDLE_PATH="$1"
      else
        echo "ERROR: unexpected argument: $1" >&2
        usage
      fi
      shift
      ;;
  esac
done

if [[ -z "$BUNDLE_PATH" ]]; then
  usage
fi

if [[ "$BUNDLE_PATH" != /* ]]; then
  BUNDLE_PATH="$INVOCATION_DIR/$BUNDLE_PATH"
fi

if [[ ! -f "$BUNDLE_PATH" ]]; then
  echo "ERROR: bundle file not found: $BUNDLE_PATH" >&2
  exit 2
fi

# Resolve to absolute path for clean delivery output
BUNDLE_PATH="$(cd "$(dirname "$BUNDLE_PATH")" && pwd)/$(basename "$BUNDLE_PATH")"

cd "$SCRIPT_DIR"

# 1. validate (fail-fast)
if ! python3 validate_bundle.py "$BUNDLE_PATH" 2>&1; then
  echo "ERROR: validate_bundle failed; fix bundle JSON and retry" >&2
  exit 1
fi

# 2. assemble
assembled=""
if ! assembled="$(python3 assemble_bundle.py "$BUNDLE_PATH" --fetch-dir "$FETCH_DIR")"; then
  echo "ERROR: assemble_bundle failed" >&2
  exit 1
fi

if [[ ! -f "$assembled" ]]; then
  echo "ERROR: assembled bundle missing: $assembled" >&2
  exit 1
fi

# 3. format IM
im_text=""
if ! im_text="$(python3 format_im_from_bundle.py "$assembled")"; then
  echo "ERROR: format_im_from_bundle failed" >&2
  exit 1
fi

# 4. persist IM (anti-truncation — Agent reads file and pastes verbatim)
code=""
im_target=""
html_target=""
code="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8'))['meta']['code'])" "$assembled")"
im_target="$(python3 -c "import sys; from pathlib import Path; from bundle_common import DEFAULT_OUTPUT_DIR; print(Path(DEFAULT_OUTPUT_DIR) / sys.argv[1] / 'latest.im.txt')" "$code")"
html_target="$(python3 -c "import sys; from pathlib import Path; from bundle_common import DEFAULT_OUTPUT_DIR; print(Path(DEFAULT_OUTPUT_DIR) / sys.argv[1] / 'latest.html')" "$code")"

mkdir -p "$(dirname "$im_target")"
printf '%s' "$im_text" > "$im_target"
if [[ "${im_text: -1}" != $'\n' ]]; then
  echo >> "$im_target"
fi

# 5. render HTML (graceful degradation — do not abort IM delivery)

html_path=""
html_warn=""
render_log=""
if render_log="$(python3 render_html.py "$assembled" -o "$html_target" 2>&1)"; then
  html_path="$html_target"
  if [[ ! -f "$html_path" ]]; then
    html_path=""
    html_warn="[HTML 渲染失败，仅交付文本]"
    echo "WARN: render_html reported success but file missing: $html_target" >&2
  fi
else
  html_warn="[HTML 渲染失败，仅交付文本]"
  echo "$render_log" >&2
fi

# Deliverables to stdout (Agent copies this block to user)
echo "===== IM 摘要内容 ====="
printf '%s' "$im_text"
if [[ "${im_text: -1}" != $'\n' ]]; then
  echo
fi
echo "======================="
echo "[交付物路径]"
echo "IM file: $im_target"
echo "Bundle (agent): $BUNDLE_PATH"
echo "Bundle (assembled): $assembled"
if [[ -n "$html_path" ]]; then
  echo "HTML: $html_path"
else
  echo "HTML: (未生成) $html_warn"
fi

exit 0
