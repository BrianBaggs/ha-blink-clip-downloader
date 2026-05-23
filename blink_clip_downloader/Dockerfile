ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.12
FROM ${BUILD_FROM}

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

# S6 service scripts and any other rootfs files
COPY rootfs /

RUN chmod a+x \
    /etc/services.d/blink_downloader/run \
    /etc/services.d/blink_downloader/finish

LABEL \
    org.opencontainers.image.title="Blink Clip Downloader" \
    org.opencontainers.image.description="Continuously downloads Blink camera clips to local storage" \
    org.opencontainers.image.source="https://github.com/yourusername/ha-blink-clip-downloader" \
    org.opencontainers.image.licenses="MIT"
