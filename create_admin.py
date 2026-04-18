"""
Script to create an admin user in Firebase
"""
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# Initialize Firebase
key_path = os.path.join(os.path.dirname(__file__), "..", "service-account-key.json")
cred = credentials.Certificate(key_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Admin user credentials
admin_email = "admin@etebeka.gov.et"
admin_password = "Admin123!"
admin_full_name = "System Administrator"
admin_tier = "C"  # General tier for admin

# Check if admin already exists
users_ref = db.collection('users')
existing_admin = users_ref.where('email', '==', admin_email).limit(1).get()

if existing_admin:
    print(f"Admin user already exists: {admin_email}")
    # Update to make sure is_admin is True
    admin_doc = existing_admin[0]
    admin_doc.reference.update({'is_admin': True, 'status': 'active'})
    print(f"Updated {admin_email} to admin status")
else:
    # Create admin user
    from app.core.security import get_password_hash
    hashed_password = get_password_hash(admin_password)
    
    new_admin_ref = users_ref.document()
    admin_data = {
        "email": admin_email,
        "password_hash": hashed_password,
        "full_name": admin_full_name,
        "phone": None,
        "tier": admin_tier,
        "status": "active",
        "email_verified": True,
        "mfa_enabled": False,
        "is_admin": True,
        "created_at": firestore.SERVER_TIMESTAMP,
        "profile": None
    }
    new_admin_ref.set(admin_data)
    print(f"Admin user created successfully!")
    print(f"Email: {admin_email}")
    print(f"Password: {admin_password}")
