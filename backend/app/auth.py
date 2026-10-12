import threading
import time
from dataclasses import dataclass

import requests
from google.auth import jwt

from . import config

CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
CERTS_TTL_SECONDS = 3600

_cache = {"certs": None, "expires": 0.0}
_lock = threading.Lock()


@dataclass
class Identity:
    id: str
    member: bool
    guest_id: str
    email: str = ""


def _fetch_certs():
    with _lock:
        if _cache["certs"] and time.time() < _cache["expires"]:
            return _cache["certs"]
        response = requests.get(CERTS_URL, timeout=5)
        response.raise_for_status()
        _cache["certs"] = response.json()
        _cache["expires"] = time.time() + CERTS_TTL_SECONDS
        return _cache["certs"]


def verify(token):
    project = config.FIREBASE_PROJECT_ID
    if not project or not token:
        return None
    try:
        claims = jwt.decode(token, certs=_fetch_certs(), audience=project)
    except Exception as exc:
        print(f"Token rejected: {type(exc).__name__}")
        return None
    if claims.get("iss") != f"https://securetoken.google.com/{project}" or not claims.get("sub"):
        return None
    return claims


def identify(request):
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    guest = f"ip:{ip}"

    if config.ENV == "dev":
        debug_user = request.headers.get("x-debug-user")
        if debug_user:
            name = f"debug:{debug_user[:32]}"
            return Identity(name, False, name)

    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        claims = verify(header[7:].strip())
        if claims:
            return Identity(f"uid:{claims['sub']}", True, guest, claims.get("email", ""))
    return Identity(guest, False, guest)
