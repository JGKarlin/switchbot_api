"""Constants for the SwitchBot API integration."""

DOMAIN = "switchbot_api"
API_BASE_URL = "https://api.switch-bot.com/v1.1"

CONF_TOKEN = "token"
CONF_SECRET = "secret"

SCAN_INTERVAL_SECONDS = 55  # Refresh auth headers before 60-second timeout
AUTH_HEADER_TTL_SECONDS = 60
AUTH_CHECK_INTERVAL_SECONDS = 600  # Validate credentials against API every 10 minutes
