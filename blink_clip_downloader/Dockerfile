ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# BUILD_ARCH is injected by the HA build system for multi-arch images.
ARG BUILD_ARCH
ARG BUILD_VERSION=2.2.1

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

# Copy rootfs overlay (s6-rc.d service definition + run.sh reference)
COPY rootfs /
# Belt-and-suspenders chmod — git already tracks 100755, but Docker layer
# copies preserve the bit; this is a safety net for CI/CD pipelines that
# might not preserve git file modes.
RUN chmod a+x /run.sh \
    && chmod a+x /etc/s6-overlay/s6-rc.d/blink-downloader/run \
    && chmod a+x /etc/s6-overlay/s6-rc.d/blink-downloader/finish

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
