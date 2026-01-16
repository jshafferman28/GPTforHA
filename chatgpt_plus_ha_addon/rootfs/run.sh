#!/usr/bin/with-contenv bashio

# Set environment variables from Add-on config
export HEADLESS
HEADLESS="$(bashio::config 'headless')"
export PORT=3000
export SESSION_DIR="/config/chatgpt_sessions"

# Ensure session directory exists in persistent storage
if [ ! -d "$SESSION_DIR" ]; then
    bashio::log.info "Creating session directory at $SESSION_DIR"
    mkdir -p "$SESSION_DIR"
fi

bashio::log.info "Starting ChatGPT Plus Sidecar..."
bashio::log.info "Headless mode: $HEADLESS"

# Start application
cd /app
if [ "$HEADLESS" = "false" ]; then
    if ! command -v Xvfb >/dev/null 2>&1; then
        bashio::log.error "Xvfb not found. Please reinstall the add-on."
        exit 1
    fi
    bashio::log.info "Starting virtual display (Xvfb)"
    Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
    export DISPLAY=:99
    sleep 1
    exec node server.js
fi
exec node server.js
