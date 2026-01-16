"""Constants for the ChatGPT Plus HA integration."""

DOMAIN = "chatgpt_plus_ha"

# Configuration keys
CONF_SIDECAR_URL = "sidecar_url"

# Default values
DEFAULT_SIDECAR_URL = "http://chatgpt_plus_ha:3000"

# API endpoints
API_HEALTH = "/health"
API_STATUS = "/api/status"
API_CHAT = "/api/chat"
API_NEW_CONVERSATION = "/api/conversation/new"
