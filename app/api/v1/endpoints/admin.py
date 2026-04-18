from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from google.cloud.firestore import Client
from google.cloud import firestore
from app.core.database import get_db
from app.api.deps import get_current_user, UserAuth
from app.core.config import settings
import uuid
import os
import requests
import shutil
from typing import List, Optional

router = APIRouter()

EMAILJS_ENDPOINT = "https://api.emailjs.com/api/v1.0/email/send"
EMAILJS_SERVICE_ID = settings.EMAILJS_SERVICE_ID or "service_c2ui0om"
EMAILJS_TEMPLATE_ID = settings.EMAILJS_TEMPLATE_ID or "template_t11rarq"
EMAILJS_PUBLIC_KEY = settings.EMAILJS_PUBLIC_KEY or "UCMBkkWS1bxKc5ujR"
EMAILJS_PRIVATE_KEY = settings.EMAILJS_PRIVATE_KEY
FRONTEND_LOGIN_URL = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')}/login"


def require_admin(current_user: UserAuth = Depends(get_current_user)) -> UserAuth:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


def send_student_approval_email(user_email: str, user_name: str):
    # Extract first name from full name
    first_name = user_name.split(" ")[0] if user_name else "Student"
    
    payload = {
        "service_id": EMAILJS_SERVICE_ID,
        "template_id": EMAILJS_TEMPLATE_ID,
        "user_id": EMAILJS_PUBLIC_KEY,
        "template_params": {
            "to_email": user_email,
            "to_name": first_name,
            "user_name": first_name,
            "email": user_email,
            "website_link": FRONTEND_LOGIN_URL,
            "company_email": "noreply@e-tebeka.gov.et",
        },
    }
    if EMAILJS_PRIVATE_KEY:
        payload["accessToken"] = EMAILJS_PRIVATE_KEY

    response = requests.post(
        EMAILJS_ENDPOINT,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    response.raise_for_status()

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    # Save file permanently
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "file_path": file_path}

@router.post("/documents/create")
async def create_document(
    payload: dict,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    if not payload:
        raise HTTPException(status_code=400, detail="Document metadata is required")

    data = payload
    
    # Save to proclamations
    doc_ref = db.collection('proclamations').document()
    doc_ref.set({
        "document_type": data.get("document_type", "proclamation"),
        "document_number": data.get("document_number"),
        "document_number_am": data.get("document_number_am", ""),
        "issuing_body_am": data.get("issuing_body_am", ""),
        "issuing_body_en": data.get("issuing_body_en", ""),
        "title_am": data.get("title_am", ""),
        "title_en": data.get("title_en", ""),
        "short_title_am": data.get("short_title_am", ""),
        "short_title_en": data.get("short_title_en", ""),
        "year_ec": data.get("year_ec", ""),
        "year_gregorian": data.get("year_gregorian"),
        "pdf_url": data.get("pdf_url", ""),
        "status": "active",
        "categories": [c for c in data.get("categories", []) if c],
        "articles": data.get("articles", []),
        "uploaded_by": current_user.id,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    
    # Add any missing categories
    categories_ref = db.collection('categories')
    for cat_name in data.get("categories", []):
        if not cat_name: continue
        # Check if category exists
        cat_docs = categories_ref.where('name_en', '==', cat_name).limit(1).get()
        if not len(cat_docs):
            categories_ref.add({
                "name_en": cat_name,
                "name_am": cat_name,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            
    return {"message": "Document created successfully", "document_id": doc_ref.id}

@router.get("/users", response_model=List[dict])
def list_users(
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    users_docs = db.collection('users').get()
    return [
        {
            "id": u.id,
            "email": u.to_dict().get("email"),
            "full_name": u.to_dict().get("full_name"),
            "tier": u.to_dict().get("tier"),
            "status": u.to_dict().get("status"),
            "is_admin": u.to_dict().get("is_admin", False),
            "created_at": u.to_dict().get("created_at")
        } for u in users_docs
    ]

@router.patch("/users/{user_id}/admin")
def promote_to_admin(
    user_id: str,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_ref.update({"is_admin": True})
    return {"message": f"User promoted to admin successfully"}

@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: str,
    status_data: dict,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    user_ref = db.collection('users').document(user_id)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_status = status_data.get("status")
    if new_status not in ["active", "suspended", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    user_ref.update({"status": new_status})
    return {"message": f"User status updated to {new_status}"}

@router.get("/verifications", response_model=List[dict])
def list_verifications(
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    users_ref = db.collection('users')
    docs = users_ref.where('profile.verification_status', 'in', ['pending', 'verified', 'rejected']).get()
    
    verifications = []
    for doc in docs:
        data = doc.to_dict()
        profile = data.get('profile', {})
        if profile.get('verification_status'):
            verifications.append({
                "id": doc.id,
                "user_id": doc.id,
                "user_name": data.get("full_name"),
                "user_email": data.get("email"),
                "student_id_number": profile.get("student_id"),
                "university": profile.get("university"),
                "status": profile.get("verification_status"),
                "submitted_at": data.get("created_at").isoformat() if hasattr(data.get("created_at"), 'isoformat') else str(data.get("created_at")),
                "document_path": profile.get("student_id_document")
            })
    return verifications

@router.patch("/verifications/{user_id}")
def update_verification_status(
    user_id: str,
    status_data: dict,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    print(f"=== VERIFICATION UPDATE START ===")
    print(f"User ID: {user_id}")
    print(f"Status data: {status_data}")
    
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    new_status = status_data.get("status")
    if new_status not in ["verified", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    user_data = user_doc.to_dict()
    updates = {"profile.verification_status": new_status}
    
    # If verified, activate the user
    if new_status == "verified":
        updates["status"] = "active"
            
    user_ref.update(updates)
    email_sent = False
    if new_status == "verified" and user_data.get("email"):
        try:
            print(f"Attempting to send email to: {user_data['email']}")
            print(f"User name: {user_data.get('full_name') or user_data['email']}")
            send_student_approval_email(
                user_email=user_data["email"],
                user_name=user_data.get("full_name") or user_data["email"],
            )
            print("Email sent successfully")
            email_sent = True
        except requests.RequestException as e:
            print(f"EmailJS RequestException: {e}")
            print(f"Response status: {e.response.status_code if hasattr(e, 'response') and e.response else 'N/A'}")
            print(f"Response text: {e.response.text if hasattr(e, 'response') and e.response else 'N/A'}")
            email_sent = False
        except Exception as e:
            print(f"Unexpected error sending email: {e}")
            import traceback
            traceback.print_exc()
            email_sent = False
    else:
        print(f"Email not sent - status: {new_status}, has email: {bool(user_data.get('email'))}")

    return {"message": f"Verification {new_status}", "email_sent": email_sent}

@router.get("/stats")
def get_admin_stats(
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(require_admin)
):
    docs = len(db.collection('proclamations').get())
    users = len(db.collection('users').get())
    pending = len(db.collection('users').where('profile.verification_status', '==', 'pending').get())
    
    return {
        "totalDocuments": str(docs),
        "totalUsers": str(users),
        "pendingVerifications": str(pending)
    }
