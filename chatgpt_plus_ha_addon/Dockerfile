ARG BUILD_FROM
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install Node.js and dependencies
RUN \
    apk add --no-cache \
    nodejs \
    npm \
    bash \
    && npm install -g pnpm

# Install Playwright dependencies (Chromium)
# We need to install specific packages for Alpine/Playwright compatibility
RUN apk add --no-cache \
    udev \
    ttf-freefont \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ca-certificates \
    ttf-freefont

# Set working directory
WORKDIR /app

# Copy rootfs
COPY rootfs /

# Ensure scripts are executable and line endings are Unix
RUN sed -i 's/\r$//' /run.sh \
    && chmod +x /run.sh

# Set environment variables before npm install
ENV \
    NODE_ENV=production \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

# Install app dependencies
WORKDIR /app
RUN npm install --only=production

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    maintainer="jshafferman28" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Add-ons" \
    org.opencontainers.image.authors="jshafferman28" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/jshafferman28/chatgpt-plus-ha" \
    org.opencontainers.image.source="https://github.com/jshafferman28/chatgpt-plus-ha" \
    org.opencontainers.image.documentation="https://github.com/jshafferman28/chatgpt-plus-ha/blob/main/README.md" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${BUILD_REF}" \
    org.opencontainers.image.version="${BUILD_VERSION}"

# Start script
CMD [ "/run.sh" ]
