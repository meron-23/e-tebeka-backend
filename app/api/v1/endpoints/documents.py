from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.core.database import get_db
from app.models.models import LegalDocument, DocumentSection, User, UserProfile, SearchHistory, Category
from app.api.deps import get_current_user_optional
from typing import List, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime

router = APIRouter()

class DocumentSummary(BaseModel):
    id: uuid.UUID
    title_en: str
    title_am: str
    document_number: str
    document_type: str
    year_gregorian: Optional[int]
    status: str

class CategoryDetail(BaseModel):
    id: uuid.UUID
    name_en: str
    name_am: str

class SearchResponse(BaseModel):
    query: str
    page: int
    limit: int
    results: List[DocumentSummary]
    searches_left: int

@router.get("/categories", response_model=List[CategoryDetail])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()

@router.get("/", response_model=List[DocumentSummary])
def browse_documents(
    skip: int = 0, 
    limit: int = 20, 
    doc_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(LegalDocument)
    if doc_type:
        query = query.filter(LegalDocument.document_type == doc_type)
    
    documents = query.offset(skip).limit(limit).all()
    return documents

@router.get("/search", response_model=SearchResponse)
def search_documents(
    request: Request,
    q: str = Query(..., min_length=2),
    category_id: Optional[uuid.UUID] = Query(None),
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    # Determine search limit
    search_limit = 100 # Temporarily increased for debugging from 5
    is_unlimited = False
    
    if current_user:
        if current_user.tier in ["A", "B"] or current_user.is_admin:
            is_unlimited = True
            search_limit = 999999
    
    # Check current searches today
    today = datetime.utcnow().date()
    
    if current_user:
        search_count = db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id,
            func.date(SearchHistory.searched_at) == today
        ).count()
    else:
        ip = request.client.host
        search_count = db.query(SearchHistory).filter(
            SearchHistory.ip_address == ip,
            SearchHistory.user_id == None,
            func.date(SearchHistory.searched_at) == today
        ).count()
        
    if search_count >= search_limit and not is_unlimited:
        raise HTTPException(
            status_code=429, 
            detail="Daily search limit reached. Please register or log in for more access."
        )
    
    # Search logic across title and content
    offset = (page - 1) * limit
    
    query_obj = db.query(LegalDocument)
    
    # Apply category filter if provided
    if category_id:
        query_obj = query_obj.join(LegalDocument.categories).filter(Category.id == category_id)
    
    results = query_obj.filter(
        or_(
            LegalDocument.title_en.ilike(f"%{q}%"),
            LegalDocument.title_am.ilike(f"%{q}%"),
            LegalDocument.document_number.ilike(f"%{q}%")
        )
    ).offset(offset).limit(limit).all()

    # Log the search
    new_search = SearchHistory(
        user_id=current_user.id if current_user else None,
        query=q,
        ip_address=request.client.host if not current_user else None,
        result_count=len(results)
    )
    db.add(new_search)
    db.commit()
    
    return {
        "query": q,
        "page": page,
        "limit": limit,
        "results": results,
        "searches_left": max(0, search_limit - search_count - 1) if not is_unlimited else 999
    }

class SectionDetail(BaseModel):
    section_type: str
    section_number: Optional[str]
    section_number_am: Optional[str]
    title_am: Optional[str]
    title_en: Optional[str]
    content_am: Optional[str]
    content_en: Optional[str]
    sequence_order: int

class DocumentDetailResponse(BaseModel):
    document: DocumentSummary
    sections: List[SectionDetail]

@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    sections = db.query(DocumentSection).filter(DocumentSection.document_id == document_id).order_by(DocumentSection.sequence_order).all()
    
    return {
        "document": document,
        "sections": sections
    }
