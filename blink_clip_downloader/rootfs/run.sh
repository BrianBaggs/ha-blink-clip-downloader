#!/command/with-contenv bashio
# ==============================================================================
# Reference script — not called by s6-overlay.
#
# The actual service entry point is:
#   /etc/s6-overlay/s6-rc.d/blink-downloader/run
#
# s6-overlay is started by the base image's own ENTRYPOINT ["/init"].
# Do NOT call s6-svscan, s6-rc, or /init from any script — the base image
# already does this exactly once.  Adding another call produces the fatal:
#   "s6-svscan: another instance of s6-svscan is already running"
# ==============================================================================
exec python3 -m blink_downloader
