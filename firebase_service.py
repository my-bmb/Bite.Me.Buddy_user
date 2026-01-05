"""
Firebase Service Configuration
Bite Me Buddy Project
Render + Production Safe
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import pyrebase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ======================================================
# FIREBASE CONFIG
# ======================================================

class FirebaseConfig:
    # Project Info
    PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
    STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET")
    DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL")

    # Web SDK Config (Frontend)
    WEB_CONFIG = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": PROJECT_ID,
        "storageBucket": STORAGE_BUCKET,
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
        "databaseURL": DATABASE_URL,
    }

    # Admin SDK Config (Backend)
    SERVICE_ACCOUNT_PATH = os.getenv(
        "SERVICE_ACCOUNT_PATH",
        "bite-me-buddy-service-account-key.json"
    )

    APP_NAME = "bite-me-buddy-app"

# ======================================================
# INITIALIZE FIREBASE ADMIN (ONLY ONCE)
# ======================================================

def initialize_firebase_admin():
    """Initialize Firebase Admin SDK safely"""
    try:
        # Already initialized?
        if firebase_admin._apps:
            return firebase_admin.get_app(FirebaseConfig.APP_NAME)

        # 1️⃣ Local JSON file (development)
        if os.path.exists(FirebaseConfig.SERVICE_ACCOUNT_PATH):
            cred = credentials.Certificate(FirebaseConfig.SERVICE_ACCOUNT_PATH)

        # 2️⃣ JSON from ENV (Render / Production)
        elif os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY"):
            raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
            cred_dict = json.loads(raw)
            # Fix line breaks in private_key
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)

        else:
            raise RuntimeError(
                "Firebase service account not found. "
                "Set FIREBASE_SERVICE_ACCOUNT_KEY in ENV or SERVICE_ACCOUNT_PATH locally."
            )

        app = firebase_admin.initialize_app(
            cred,
            {
                "projectId": FirebaseConfig.PROJECT_ID,
                "storageBucket": FirebaseConfig.STORAGE_BUCKET,
                "databaseURL": FirebaseConfig.DATABASE_URL,
            },
            name=FirebaseConfig.APP_NAME,
        )

        print("✅ Firebase Admin initialized successfully")
        return app

    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        raise

# ======================================================
# CLIENT HELPERS
# ======================================================

def get_firestore_client():
    initialize_firebase_admin()
    return firestore.client()


def get_auth_client():
    initialize_firebase_admin()
    return auth


def get_storage_bucket():
    initialize_firebase_admin()
    return storage.bucket()


def get_pyrebase_client():
    """Frontend-like Firebase client (OTP / Login)"""
    return pyrebase.initialize_app(FirebaseConfig.WEB_CONFIG)

# ======================================================
# EXPORTS
# ======================================================

__all__ = [
    "initialize_firebase_admin",
    "get_firestore_client",
    "get_auth_client",
    "get_storage_bucket",
    "get_pyrebase_client",
]