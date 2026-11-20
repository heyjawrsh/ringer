#!/bin/bash
# Ringer engine wrapper: run OpenCode under a macOS Seatbelt sandbox.
#
# OpenCode has no OS-level sandbox of its own — its --dangerously-skip-permissions
# flag (required for headless runs) disables ALL of its interactive approval
# prompts. This wrapper supplies the real containment: full network and reads,
# writes confined to the task dir, a per-run scratch/cache dir, and OpenCode's
# own state dirs.
#
# Usage (as a ringer engine bin):
#   opencode-sandboxed.sh <taskdir> [--no-sandbox] <opencode args...>
#
# The first argument is the task directory (pass "{taskdir}" first in
# args_template). "--no-sandbox" as the second argument skips Seatbelt entirely
# — wire it as the engine's full_access_args so ringer's allow_full_access gate
# still applies. macOS only (sandbox-exec); on other platforms only
# --no-sandbox mode works.
set -euo pipefail

TASKDIR="${1:?usage: opencode-sandboxed.sh <taskdir> [--no-sandbox] <args...>}"; shift
SANDBOX=1
if [ "${1:-}" = "--no-sandbox" ]; then SANDBOX=0; shift; fi

# Resolve SubQ credentials before either launch path so 1Password runs outside Seatbelt.
resolve_subq_api_key() {
  local model=
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -m|--model) model="${2:-}"; break ;;
      --model=*) model="${1#--model=}"; break ;;
      --) break ;;
    esac
    shift
  done

  if [[ "$model" != subq/* || -n "${SUBQ_API_KEY:-}" ]]; then
    return 0
  fi
  if [ -z "${SUBQ_OP_REF:-}" ]; then
    echo "opencode-sandboxed.sh: model $model needs SUBQ_API_KEY, or SUBQ_OP_REF naming its 1Password item" >&2
    exit 2
  fi
  if ! command -v op >/dev/null; then
    echo "opencode-sandboxed.sh: 1Password CLI op was not found on PATH" >&2
    exit 2
  fi
  # Absolute paths and builtins only: callers may hand this script a minimal PATH.
  local op_err reason="" line
  op_err="$(/usr/bin/mktemp -t ringer-op-err)"
  if ! SUBQ_API_KEY="$(op read "$SUBQ_OP_REF" 2>"$op_err")"; then
    # Relay op's own "[ERROR] ..." line ("authorization timeout" when 1Password is
    # locked) and nothing else, so stray stderr can never carry the secret out.
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in "[ERROR]"*) reason="${line#\[ERROR\] }" ;; esac
    done < "$op_err"
    /bin/rm -f "$op_err"
    echo "opencode-sandboxed.sh: could not read SUBQ_OP_REF with the 1Password CLI op${reason:+: ${reason:0:200}}" >&2
    exit 2
  fi
  /bin/rm -f "$op_err"
  export SUBQ_API_KEY
}
resolve_subq_api_key "$@"

# Resolve opencode without tripping `set -e` (command -v returns nonzero when absent).
if ! OPENCODE_BIN="$(command -v opencode)" || [ -z "$OPENCODE_BIN" ]; then
  echo "opencode-sandboxed.sh: opencode not found on PATH" >&2
  exit 127
fi

if [ "$SANDBOX" = "0" ]; then
  exec "$OPENCODE_BIN" "$@" < /dev/null
fi

if [ ! -x /usr/bin/sandbox-exec ]; then
  echo "opencode-sandboxed.sh: /usr/bin/sandbox-exec not available (macOS only)." >&2
  echo "Use the engine's full-access mode (--no-sandbox) or add your own sandbox." >&2
  exit 1
fi

TASKDIR_REAL="$(cd "$TASKDIR" && pwd -P)"

# Per-run scratch root — becomes both TMPDIR and XDG_CACHE_HOME for OpenCode, so
# we never have to open all of /private/tmp or ~/.cache to the sandboxed agent.
# Resolve to the real path (/var/folders symlinks to /private/var/folders);
# Seatbelt subpath matching needs the canonical path or writes EPERM-crash.
SCRATCH="$(cd "$(mktemp -d -t ringer-opencode-scratch)" && pwd -P)"
PROFILE="$(mktemp -t ringer-opencode-prof)"
cleanup() { rm -rf "$SCRATCH" "$PROFILE"; }
trap cleanup EXIT

# Paths are passed to the profile via sandbox-exec -D parameters, NOT string
# interpolation — a task dir containing quotes/parens/newlines can't inject rules.
cat > "$PROFILE" <<'SBEOF'
(version 1)
(allow default)
(deny file-write*)
(allow file-write*
  (subpath (param "TASKDIR"))
  (subpath (param "SCRATCH"))
  (subpath (param "OC_SHARE"))
  (subpath (param "OC_STATE"))
  (subpath (param "OC_CONFIG")))
; /dev is needed for /dev/null, /dev/urandom, etc.; writes there can't create
; persistent files without root, so a few literals are allowed rather than via param.
(allow file-write-data
  (literal "/dev/null")
  (literal "/dev/dtracehelper")
  (literal "/dev/tty"))
SBEOF

export TMPDIR="$SCRATCH"
export XDG_CACHE_HOME="$SCRATCH/cache"
mkdir -p "$XDG_CACHE_HOME"

# Run as a child (not exec) so the EXIT trap fires and cleans up the profile +
# scratch dir even on the success path; propagate the child's exit status.
set +e
/usr/bin/sandbox-exec \
  -D "TASKDIR=$TASKDIR_REAL" \
  -D "SCRATCH=$SCRATCH" \
  -D "OC_SHARE=$HOME/.local/share/opencode" \
  -D "OC_STATE=$HOME/.local/state/opencode" \
  -D "OC_CONFIG=$HOME/.config/opencode" \
  -f "$PROFILE" "$OPENCODE_BIN" "$@" < /dev/null
status=$?
set -e
exit "$status"
