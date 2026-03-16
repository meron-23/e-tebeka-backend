from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.core.database import get_db
from app.models.models import LegalDocument, DocumentSection, Category, UploadJob, User, StudentVerification
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
    db: Session = Depends(get_db)
):
    # Save file temporarily
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create upload job
    job = UploadJob(
        original_filename=file.filename,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return {"job_id": job.id, "filename": file.filename}

@router.post("/documents/process-gemini/{job_id}")
async def process_with_gemini(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(UploadJob).filter(UploadJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    file_path = ord_path = os.path.join("uploads", job.original_filename)
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
        job.status = "failed"
        job.gemini_response = {"error": f"Failed to extract text: {e}"}
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {e}")
    
    # Send to Gemini
    gemini_data = extract_document_data(text)
    
    if "error" in gemini_data:
        job.status = "failed"
        job.gemini_response = gemini_data
        db.commit()
        return gemini_data
    
    job.status = "completed"
    job.gemini_response = gemini_data
    db.commit()
    
    return gemini_data

@router.post("/documents/confirm-upload/{job_id}")
async def confirm_upload(job_id: uuid.UUID, payload: Optional[dict] = None, db: Session = Depends(get_db)):
    job = db.query(UploadJob).filter(UploadJob.id == job_id).first()
    if not job or job.status != "completed":
        raise HTTPException(status_code=400, detail="Job not ready or not found")
    
    # Use payload if provided, otherwise fall back to gemini_response
    data = payload if payload else job.gemini_response
    
    # Create legal document
    doc = LegalDocument(
        document_type=data.get("document_type", "proclamation"),
        document_number=data.get("document_number"),
        document_number_am=data.get("document_number_am"),
        issuing_body_am=data.get("issuing_body_am"),
        issuing_body_en=data.get("issuing_body_en"),
        title_am=data.get("title_am"),
        title_en=data.get("title_en"),
        short_title_am=data.get("short_title_am"),
        short_title_en=data.get("short_title_en"),
        year_ec=data.get("year_ec"),
        year_gregorian=data.get("year_gregorian"),
        pdf_url=job.original_filename, # Use filename as relative path
        status="active"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # Process Categories
    categories_list = data.get("categories", [])
    for cat_name in categories_list:
        if not cat_name: continue
        # Find or create category
        category = db.query(Category).filter(
            func.lower(Category.name_en) == cat_name.lower()
        ).first()
        
        if not category:
            category = Category(
                name_en=cat_name,
                name_am=cat_name, # Placeholder Amharic
                id=uuid.uuid4()
            )
            db.add(category)
            db.commit()
            db.refresh(category)
        
        # Link document to category
        # Check if table document_categories is accessible via relationship
        # Or manual insert if needed. Based on model (lines 88, 120):
        # categories = relationship("Category", secondary="document_categories", back_populates="documents")
        doc.categories.append(category)
    
    # Create sections
    for i, section in enumerate(data.get("articles", [])):
        ds = DocumentSection(
            document_id=doc.id,
            section_type=section.get("section_type", "article"),
            section_number=section.get("section_number"),
            section_number_am=section.get("section_number_am"),
            title_am=section.get("title_am"),
            title_en=section.get("title_en"),
            content_am=section.get("content_am"),
            content_en=section.get("content_en"),
            sequence_order=i
        )
        db.add(ds)
    
    db.commit()
    return {"message": "Document created successfully", "document_id": doc.id}

@router.get("/users", response_model=List[dict])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "tier": u.tier,
            "status": u.status,
            "is_admin": u.is_admin
        } for u in users
    ]

@router.patch("/users/{user_id}/status")
def update_user_status(user_id: uuid.UUID, status_data: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_status = status_data.get("status")
    if new_status not in ["active", "suspended", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    user.status = new_status
    db.commit()
    return {"message": f"User status updated to {new_status}"}

@router.get("/verifications", response_model=List[dict])
def list_verifications(db: Session = Depends(get_db)):
    items = db.query(StudentVerification).all()
    return [
        {
            "id": str(v.id),
            "user_id": str(v.user_id),
            "student_id_number": v.student_id_number,
            "university": v.university,
            "status": v.status,
            "submitted_at": v.submitted_at.isoformat(),
            "document_path": v.document_path
        } for v in items
    ]

@router.patch("/verifications/{verification_id}")
def update_verification_status(verification_id: uuid.UUID, status_data: dict, db: Session = Depends(get_db)):
    verification = db.query(StudentVerification).filter(StudentVerification.id == verification_id).first()
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    new_status = status_data.get("status")
    if new_status not in ["verified", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    verification.status = new_status
    
    # If verified, activate the user
    if new_status == "verified":
        user = db.query(User).filter(User.id == verification.user_id).first()
        if user:
            user.status = "active"
            
    db.commit()
    return {"message": f"Verification {new_status}"}

@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    doc_count = db.query(LegalDocument).count()
    user_count = db.query(User).count()
    pending_verif = db.query(StudentVerification).filter(StudentVerification.status == "pending").count()
    
    return {
        "totalDocuments": str(doc_count),
        "totalUsers": str(user_count),
        "pendingVerifications": str(pending_verif)
    }
