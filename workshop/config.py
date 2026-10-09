"""Workshop-only configuration. Importing this module never contacts VSS."""
import math
import os
from urllib.parse import urlsplit


INTERNAL_VSS_URL = "http://video-backend-service.team-6.svc.cluster.local:8000"


def mode() -> str:
    value = os.getenv("WITNESS_WORKSHOP_MODE", "fixture")
    if value not in {"fixture", "vast"}:
        raise ValueError("WITNESS_WORKSHOP_MODE must be fixture or vast")
    return value


def vast_settings() -> tuple[str, str, str, float]:
    url = os.getenv("VSS_URL", "").rstrip("/")
    username = os.getenv("VSS_USERNAME", "")
    password = os.getenv("VSS_PASSWORD", "")
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("VSS_URL must be an HTTP(S) base URL without credentials or query")
    if not username.strip() or not password.strip():
        raise ValueError("VSS_USERNAME and VSS_PASSWORD are required")
    timeout = float(os.getenv("VSS_TIMEOUT_SECONDS", "60"))
    if not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("VSS_TIMEOUT_SECONDS must be finite and in (0, 300]")
    return url, username, password, timeout
