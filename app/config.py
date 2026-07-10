from __future__ import annotations

from redberry_webkit.config import ConfigManager

# Runtime-editable defaults (hot-reload via mtime polling, see app/main.py's lifespan).
# A project derived from this skeleton extends this dict with its own runtime-editable
# settings before constructing ConfigManager — no subclassing needed, the constructor
# already accepts an arbitrary defaults dict:
#
#   _DEFAULTS = {**_SKELETON_DEFAULTS, "MY_APP_SETTING": "default-value"}
#   _SECRET_KEYS = _SKELETON_SECRET_KEYS | {"MY_APP_API_KEY"}
#   config = ConfigManager(defaults=_DEFAULTS, secret_keys=_SECRET_KEYS)
_DEFAULTS: dict[str, str] = {
    "REFRESH_ENABLED": "true",
    "REFRESH_INTERVAL": "5",
    "RATE_LIMIT": "20/minute",
}
_SECRET_KEYS: set[str] = set()

config = ConfigManager(defaults=_DEFAULTS, secret_keys=_SECRET_KEYS)
