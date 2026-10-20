#!/usr/bin/env bash
# The commands GNU and BSD spell differently. Source it; do not run it.
#
#     . "$SCRIPT_DIR/portable.sh"
#
# macOS ships BSD userland: no `mv -T`, no `stat -c`, no `timeout`. Every
# script that needs one of them calls the helper here instead, so the
# platform check lives in one place.

# Rename $1 to $2. When $2 is a symlink to a directory, the link itself is
# replaced; $1 is never moved into the directory the link points at. GNU mv
# spells that -T and BSD mv spells it -h. It is still a single rename(2), so
# swapping `current` stays atomic. Ask mv which one it is rather than the OS:
# a Mac with Homebrew's GNU coreutils first in PATH has a GNU mv.
airlock_rename() {
  if mv --version >/dev/null 2>&1; then
    mv -T "$1" "$2"
    return
  fi
  case "$(uname -s)" in
    Darwin|*BSD) mv -h "$1" "$2" ;;
    *) mv -T "$1" "$2" ;;
  esac
}

# Print "<owner uid> <octal mode>" for $1, the shape GNU `stat -c '%u %a'`
# prints. BSD stat takes -f, and %Lp is its octal permission bits.
airlock_owner_mode() {
  stat -c '%u %a' "$1" 2>/dev/null || stat -f '%u %Lp' "$1" 2>/dev/null
}

# Run "$@" for at most $1 seconds, and exit 124 on a timeout, as GNU
# `timeout` does. macOS has no `timeout`; Python is already required by
# the kit, so it stands in there.
airlock_timeout() {
  local secs="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
    return
  fi
  "${PY:-python3}" -I -c '
import subprocess, sys
try:
    sys.exit(subprocess.call(sys.argv[2:], timeout=float(sys.argv[1])))
except subprocess.TimeoutExpired:
    sys.exit(124)
' "$secs" "$@"
}
