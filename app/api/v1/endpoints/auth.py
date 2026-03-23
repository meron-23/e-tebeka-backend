from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from google.cloud import firestore
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    tier: str # 'A', 'B', 'C'
    # Extra fields for Tier B/A
    university: Optional[str] = None
    student_id: Optional[str] = None
    bar_number: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register_user(user_in: UserRegister, db: Client = Depends(get_db)):
    # Check if user exists
    users_ref = db.collection('users')
    existing_user = users_ref.where('email', '==', user_in.email).limit(1).get()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Password hashing
    hashed_password = get_password_hash(user_in.password)
    
    status_val = "active" if user_in.tier == "C" else "pending"
    
    # Create user
    new_user_ref = users_ref.document()
    user_data = {
        "email": user_in.email,
        "password_hash": hashed_password,
        "full_name": user_in.full_name,
        "phone": user_in.phone,
        "tier": user_in.tier,
        "status": status_val,
        "email_verified": False,
        "mfa_enabled": False,
        "is_admin": False,
        "created_at": firestore.SERVER_TIMESTAMP,
        "profile": {
            "university": user_in.university,
            "student_id": user_in.student_id,
            "bar_number": user_in.bar_number,
            "verification_status": "pending" if status_val == "pending" else None
        }
    }
    new_user_ref.set(user_data)
    
    return {"message": "User registered successfully", "user_id": new_user_ref.id}

@router.post("/login")
def login(user_in: UserLogin, db: Client = Depends(get_db)):
    users_ref = db.collection('users')
    docs = users_ref.where('email', '==', user_in.email).limit(1).get()
    
    if not docs:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    user_doc = docs[0]
    user_data = user_doc.to_dict()
    
    if not verify_password(user_in.password, user_data.get('password_hash')):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if user_data.get('status') == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Your account is pending approval. Please wait for an administrator to verify your credentials."
        )
    
    # Update last login
    user_doc.reference.update({'last_login': firestore.SERVER_TIMESTAMP})
    
    access_token = create_access_token(subject=user_doc.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_doc.id,
            "email": user_data.get('email'),
            "full_name": user_data.get('full_name'),
            "tier": user_data.get('tier'),
            "is_admin": user_data.get('is_admin', False)
        }
    }
