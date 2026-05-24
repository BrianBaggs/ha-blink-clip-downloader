#!/command/with-contenv bashio
# ==============================================================================
# Blink Clip Downloader – main service entry point.
#
# `with-contenv` loads the supervisor environment (SUPERVISOR_TOKEN, etc.)
# before executing this script.  bashio provides structured logging.
# ==============================================================================
set -e

bashio::log.info "Starting Blink Clip Downloader..."
bashio::log.info "Download path : $(bashio::config 'download_path')"
bashio::log.info "Poll interval : $(bashio::config 'poll_interval') seconds"

exec python3 -m blink_downloader
