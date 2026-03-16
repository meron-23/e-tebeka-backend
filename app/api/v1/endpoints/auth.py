from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.models import User, UserProfile
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
def register_user(user_in: UserRegister, db: Session = Depends(get_db)):
    # Check if user exists
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Password hashing
    hashed_password = get_password_hash(user_in.password)
    
    # Create user
    new_user = User(
        email=user_in.email,
        password_hash=hashed_password,
        full_name=user_in.full_name,
        phone=user_in.phone,
        tier=user_in.tier,
        status="active" if user_in.tier == "C" else "pending"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create profile
    profile = UserProfile(
        user_id=new_user.id,
        university=user_in.university,
        student_id=user_in.student_id,
        bar_number=user_in.bar_number
    )
    db.add(profile)
    db.commit()
    
    return {"message": "User registered successfully", "user_id": new_user.id}

@router.post("/login")
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if user.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Your account is pending approval. Please wait for an administrator to verify your credentials."
        )
    
    access_token = create_access_token(subject=user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "tier": user.tier,
            "is_admin": user.is_admin
        }
    }
