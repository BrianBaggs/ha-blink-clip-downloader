ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# BUILD_ARCH is injected by the HA build system for multi-arch images.
ARG BUILD_ARCH
ARG BUILD_VERSION=2.1.2

# Install C build tools needed by some Python wheels
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

# Install Python dependencies first (Docker layer cache)
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Install the app package so `python3 -m blink_downloader` works anywhere
COPY pyproject.toml /app/pyproject.toml
COPY blink_downloader/ /app/blink_downloader/
RUN pip3 install --no-cache-dir /app \
    && rm -rf /app

# Copy rootfs overlay (S6v3 service definitions + run.sh helper)
COPY rootfs /
# Mark both entry points executable.
# The canonical service entry is the S6-overlay v3 longrun definition at
#   /etc/s6-overlay/s6-rc.d/blink-downloader/run
# /run.sh is kept as a plain-shell fallback reference but is NOT used as CMD.
RUN chmod a+x /run.sh \
    && chmod a+x /etc/s6-overlay/s6-rc.d/blink-downloader/run

LABEL \
    org.opencontainers.image.title="Blink Clip Downloader" \
    org.opencontainers.image.description="Continuously downloads Blink camera clips to local HA storage" \
    org.opencontainers.image.source="https://github.com/yourusername/ha-blink-clip-downloader" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.version="${BUILD_VERSION}" \
    io.hass.name="Blink Clip Downloader" \
    io.hass.description="Download, browse and stream Blink camera clips in Home Assistant" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}"
