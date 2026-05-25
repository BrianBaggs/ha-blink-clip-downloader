#!/bin/sh
# ==============================================================================
# Blink Clip Downloader – container ENTRYPOINT wrapper.
#
# WHY THIS EXISTS
# ---------------
# The HA Supervisor sometimes restarts a container in-place
# (docker container.restart()) rather than stopping + removing + recreating it.
# In-place restarts preserve the container's writable overlay layer, which
# includes /run — a directory that is NOT a tmpfs in Docker's default config.
#
# When s6-overlay's preinit tries to initialise /run/service on a layer that
# still holds a lock file from the previous s6-svscan run, it fails with:
#
#   s6-svscan: fatal: another instance of s6-svscan is already running
#   s6-linux-init (child): warning: s6-svscan failed to send a notification byte!
#
# The container then exits, the Supervisor restarts it again in-place, and the
# cycle repeats indefinitely — producing the "App not running — Start?" loop in
# the HA sidebar.
#
# THE FIX
# -------
# This wrapper runs first as PID 1, removes any stale s6 runtime state, then
# hands off to the real /init (s6-overlay) via exec — so s6-overlay replaces
# this script as PID 1 and the rest of the startup proceeds normally.
# ==============================================================================

# Clear any stale s6 runtime state from a previous in-place container restart.
# These directories are recreated by s6-overlay's own preinit; deleting them
# here simply prevents s6-svscan from finding the old lock file.
rm -rf /run/s6 /run/service /run/s6-rc* 2>/dev/null || true

# Exec /init so it becomes PID 1 (replaces this script in the process table).
# All arguments passed to this script are forwarded as-is.
exec /init "$@"
