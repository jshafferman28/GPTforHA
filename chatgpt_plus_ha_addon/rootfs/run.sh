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
    exec xvfb-run -a node server.js
fi
exec node server.js
