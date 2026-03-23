from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from google.cloud.firestore import Client
from google.cloud import firestore
from app.core.database import get_db
from app.core.gemini import extract_document_data
import uuid
import os
import shutil
from typing import List, Optional
import PyPDF2
import pdfplumber
import io
import json

router = APIRouter()

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Client = Depends(get_db)
):
    # Save file temporarily
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create upload job
    jobs_ref = db.collection('ocr_jobs')
    job_ref = jobs_ref.document()
    job_ref.set({
        "original_filename": file.filename,
        "status": "pending",
        "submitted_at": firestore.SERVER_TIMESTAMP
    })
    
    return {"job_id": job_ref.id, "filename": file.filename}

@router.post("/documents/process-gemini/{job_id}")
async def process_with_gemini(job_id: str, db: Client = Depends(get_db)):
    job_ref = db.collection('ocr_jobs').document(job_id)
    job_doc = job_ref.get()
    if not job_doc.exists:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = job_doc.to_dict()
    file_path = os.path.join("uploads", job_data.get('original_filename', ''))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Extract text from PDF
    text = ""
    try:
        # Try pdfplumber first (often better results)
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # If pdfplumber failed or got very little text, try PyPDF2
        if len(text.strip()) < 50:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
    except Exception as e:
        job_ref.update({
            "status": "failed",
            "gemini_response": {"error": f"Failed to extract text: {e}"}
        })
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {e}")
    
    # Send to Gemini
    gemini_data = extract_document_data(text)
    
    if "error" in gemini_data:
        job_ref.update({
            "status": "failed",
            "gemini_response": gemini_data
        })
        return gemini_data
    
    job_ref.update({
        "status": "completed",
        "gemini_response": gemini_data
    })
    
    return gemini_data

@router.post("/documents/confirm-upload/{job_id}")
async def confirm_upload(job_id: str, payload: Optional[dict] = None, db: Client = Depends(get_db)):
    job_ref = db.collection('ocr_jobs').document(job_id)
    job_doc = job_ref.get()
    
    if not job_doc.exists:
        raise HTTPException(status_code=400, detail="Job not found")
        
    job_data = job_doc.to_dict()
    if job_data.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not ready")
        
    data = payload if payload else job_data.get("gemini_response")
    
    # Save to proclamations
    doc_ref = db.collection('proclamations').document()
    doc_ref.set({
        "document_type": data.get("document_type", "proclamation"),
        "document_number": data.get("document_number"),
        "document_number_am": data.get("document_number_am"),
        "issuing_body_am": data.get("issuing_body_am"),
        "issuing_body_en": data.get("issuing_body_en"),
        "title_am": data.get("title_am"),
        "title_en": data.get("title_en"),
        "short_title_am": data.get("short_title_am"),
        "short_title_en": data.get("short_title_en"),
        "year_ec": data.get("year_ec"),
        "year_gregorian": data.get("year_gregorian"),
        "pdf_url": job_data.get("original_filename"),
        "status": "active",
        "categories": [c for c in data.get("categories", []) if c],
        "articles": data.get("articles", []),
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
def list_users(db: Client = Depends(get_db)):
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
def promote_to_admin(user_id: str, db: Client = Depends(get_db)):
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_ref.update({"is_admin": True})
    return {"message": f"User promoted to admin successfully"}

@router.patch("/users/{user_id}/status")
def update_user_status(user_id: str, status_data: dict, db: Client = Depends(get_db)):
    user_ref = db.collection('users').document(user_id)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_status = status_data.get("status")
    if new_status not in ["active", "suspended", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    user_ref.update({"status": new_status})
    return {"message": f"User status updated to {new_status}"}

@router.get("/verifications", response_model=List[dict])
def list_verifications(db: Client = Depends(get_db)):
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
                "student_id_number": profile.get("student_id"),
                "university": profile.get("university"),
                "status": profile.get("verification_status"),
                "submitted_at": data.get("created_at").isoformat() if hasattr(data.get("created_at"), 'isoformat') else str(data.get("created_at")),
                "document_path": profile.get("student_id_document")
            })
    return verifications

@router.patch("/verifications/{user_id}")
def update_verification_status(user_id: str, status_data: dict, db: Client = Depends(get_db)):
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    new_status = status_data.get("status")
    if new_status not in ["verified", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    updates = {"profile.verification_status": new_status}
    
    # If verified, activate the user
    if new_status == "verified":
        updates["status"] = "active"
            
    user_ref.update(updates)
    return {"message": f"Verification {new_status}"}

@router.get("/stats")
def get_admin_stats(db: Client = Depends(get_db)):
    docs = len(db.collection('proclamations').get())
    users = len(db.collection('users').get())
    pending = len(db.collection('users').where('profile.verification_status', '==', 'pending').get())
    
    return {
        "totalDocuments": str(docs),
        "totalUsers": str(users),
        "pendingVerifications": str(pending)
    }
