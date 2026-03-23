import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

if not firebase_admin._apps:
    try:
        # Try to get Firebase config from environment variable first (for production)
        firebase_config = os.getenv("FIREBASE_CONFIG")
        if firebase_config:
            # Parse JSON from environment variable
            cred_dict = json.loads(firebase_config)
            cred = credentials.Certificate(cred_dict)
        else:
            # Fallback to local file for development
            key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "service-account-key.json")
            cred = credentials.Certificate(key_path)
        
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Error initializing Firebase Admin: {e}")

db = firestore.client()

def get_db():
    yield db
