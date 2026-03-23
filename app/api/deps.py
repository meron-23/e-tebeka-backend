from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from google.cloud.firestore import Client

from app.core.database import get_db
from app.core.config import settings
from pydantic import BaseModel

class UserAuth(BaseModel):
    id: str
    email: str
    full_name: str
    tier: str
    status: str
    is_admin: bool = False


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False  # Allow anonymous access
)

def get_current_user_optional(
    db: Client = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[UserAuth]:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    
    doc_ref = db.collection('users').document(user_id)
    doc_snap = doc_ref.get()
    
    if not doc_snap.exists:
        return None
    
    user_data = doc_snap.to_dict()
    # Handle cases where is_admin might not be present in migrated data
    user_data.setdefault('is_admin', False)
    
    return UserAuth(id=doc_snap.id, **user_data)

def get_current_user(
    current_user: UserAuth = Depends(get_current_user_optional)
) -> UserAuth:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
