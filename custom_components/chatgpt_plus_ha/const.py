"""Constants for the ChatGPT Plus HA integration."""

DOMAIN = "chatgpt_plus_ha"

# Configuration keys
CONF_SIDECAR_URL = "sidecar_url"
CONF_CONTEXT_ENABLED = "context_enabled"
CONF_INCLUDE_HISTORY = "include_history"
CONF_INCLUDE_LOGBOOK = "include_logbook"
CONF_HISTORY_HOURS = "history_hours"
CONF_ALLOWLIST_DOMAINS = "allowlist_domains"
CONF_DENYLIST_DOMAINS = "denylist_domains"
CONF_ALLOWLIST_ENTITIES = "allowlist_entities"
CONF_DENYLIST_ENTITIES = "denylist_entities"
CONF_MAX_CONTEXT_ENTITIES = "max_context_entities"
CONF_SUMMARY_CACHE_TTL = "summary_cache_ttl"
CONF_INCOGNITO_MODE = "incognito_mode"

# Default values
DEFAULT_SIDECAR_PORT = 3000
ADDON_SLUG_BASE = "chatgpt_plus_ha"
SUPERVISOR_URL = "http://supervisor"
DEFAULT_SIDECAR_URL = "http://chatgpt_plus_ha:3000"
DEFAULT_CONTEXT_ENABLED = True
DEFAULT_INCLUDE_HISTORY = True
DEFAULT_INCLUDE_LOGBOOK = True
DEFAULT_HISTORY_HOURS = 6
DEFAULT_ALLOWLIST_DOMAINS: list[str] = []
DEFAULT_DENYLIST_DOMAINS: list[str] = []
DEFAULT_ALLOWLIST_ENTITIES: list[str] = []
DEFAULT_DENYLIST_ENTITIES: list[str] = []
DEFAULT_MAX_CONTEXT_ENTITIES = 30
DEFAULT_SUMMARY_CACHE_TTL = 300
DEFAULT_INCOGNITO_MODE = False

# Conversation policy
CONVERSATION_IDLE_MINUTES = 30

# API endpoints
API_HEALTH = "/health"
API_STATUS = "/api/status"
API_CHAT = "/api/chat"
API_NEW_CONVERSATION = "/api/conversation/new"
