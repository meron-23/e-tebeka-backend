import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


BASE_DIR = Path(__file__).resolve().parents[3]
SERVICE_ACCOUNT_PATH = BASE_DIR / "service-account-key.json"


def _get_firebase_credential() -> credentials.Certificate:
    firebase_config = os.getenv("FIREBASE_CONFIG")
    if firebase_config:
        return credentials.Certificate(json.loads(firebase_config))

    if SERVICE_ACCOUNT_PATH.exists():
        return credentials.Certificate(str(SERVICE_ACCOUNT_PATH))

    raise RuntimeError(
        "Firebase credentials not found. Expected FIREBASE_CONFIG or "
        f"'{SERVICE_ACCOUNT_PATH}'."
    )


if not firebase_admin._apps:
    firebase_admin.initialize_app(_get_firebase_credential())

db = firestore.client()


def get_db():
    yield db
