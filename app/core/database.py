import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


BASE_DIR = Path(__file__).resolve().parents[2]  # e-tebeka-backend/
REPO_ROOT = Path(__file__).resolve().parents[3]  # e-tebeka/

# Check backend root first (when key is placed inside the backend folder),
# then fall back to the repo root (legacy location).
_backend_key = BASE_DIR / "service-account-key.json"
_repo_key = REPO_ROOT / "service-account-key.json"
SERVICE_ACCOUNT_PATH = _backend_key if _backend_key.exists() else _repo_key


def _get_firebase_credential() -> credentials.Certificate:
    firebase_config = os.getenv("FIREBASE_CONFIG")
    if firebase_config:
        return credentials.Certificate(json.loads(firebase_config))

    if SERVICE_ACCOUNT_PATH.exists():
        return credentials.Certificate(str(SERVICE_ACCOUNT_PATH))

    raise RuntimeError(
        "Firebase credentials not found. Expected FIREBASE_CONFIG env var or "
        f"'service-account-key.json' in backend root or repo root."
    )


if not firebase_admin._apps:
    firebase_admin.initialize_app(_get_firebase_credential())

db = firestore.client()


def get_db():
    yield db
