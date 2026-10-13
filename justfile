# Related Languages Resources — task runner.
#
#   just            list recipes
#   just setup      install everything (uv and the package)
#   just demo       run the demo UI and open it in your browser
#
# No `just`? `./run` does the same with plain bash.

set shell := ["bash", "-euo", "pipefail", "-c"]

port := "8765"

# List recipes.
default:
    @just --list --unsorted

# Install uv (if missing) and the package with the demo extra (plus `mt` when RLR_MT is set).
setup: _uv
    #!/usr/bin/env bash
    set -euo pipefail
    case "${RLR_MT:-none}" in
        none|"") uv sync --extra dev --extra demo ;;
        *)       uv sync --extra dev --extra demo --extra mt ;;
    esac

# Run the demo UI on http://127.0.0.1:8765 and open a browser.
demo: setup
    #!/usr/bin/env bash
    set -euo pipefail
    ( sleep 2; command -v xdg-open >/dev/null && xdg-open "http://127.0.0.1:{{port}}" || command -v open >/dev/null && open "http://127.0.0.1:{{port}}" ) >/dev/null 2>&1 &
    uv run rlr serve --port {{port}}

# Show a passage across related languages, e.g. `just brief ngq swh "MRK 1:3"`.
brief target lwc passage: setup
    uv run rlr brief --target {{target}} --lwc {{lwc}} --passage "{{passage}}"

# List the languages with Scripture that are closest to a target, e.g. `just languages ngq`.
languages target: setup
    uv run rlr languages --target {{target}}

# Lint, typecheck and test.
check: _uv
    uv sync --extra dev --extra demo
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy
    uv run pytest -q

# Re-record the narrated product demo (needs ffmpeg, Playwright, and the ElevenLabs demo key).
record:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --with playwright python -m playwright install chromium
    uv run --with playwright python demo/record.py --out demo/out

# Delete the download cache (Glottolog, eBible) so the next run refetches.
clean-cache:
    rm -rf "${RLR_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/rlr}"

_uv:
    #!/usr/bin/env bash
    if ! command -v uv >/dev/null; then
        echo "Installing uv (https://astral.sh/uv)…"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
