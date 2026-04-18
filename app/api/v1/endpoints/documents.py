from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from google.cloud.firestore import Client
from google.cloud import firestore
from app.core.database import get_db
from app.api.deps import get_current_user_optional, UserAuth
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import os

router = APIRouter()

class DocumentSummary(BaseModel):
    id: uuid.UUID
    title_en: str
    title_am: str
    document_number: str
    document_type: str
    year_gregorian: Optional[int]
    status: str
    pdf_url: Optional[str] = None

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
def list_categories(db: Client = Depends(get_db)):
    docs = db.collection('categories').get()
    categories = []
    for doc in docs:
        cat_data = doc.to_dict()
        categories.append(CategoryDetail(id=doc.id, **cat_data))
    return categories

@router.get("/", response_model=List[DocumentSummary])
def browse_documents(
    skip: int = 0, 
    limit: int = 20, 
    doc_type: Optional[str] = None,
    db: Client = Depends(get_db)
):
    query = db.collection('proclamations')
    if doc_type:
        query = query.where('document_type', '==', doc_type)
    
    docs = query.offset(skip).limit(limit).get()
    
    documents = []
    for doc in docs:
        documents.append(DocumentSummary(id=doc.id, **doc.to_dict()))
    return documents

@router.get("/search", response_model=SearchResponse)
def search_documents(
    request: Request,
    q: str = Query(..., min_length=2),
    category_id: Optional[uuid.UUID] = Query(None),
    page: int = 1,
    limit: int = 10,
    db: Client = Depends(get_db),
    current_user: Optional[UserAuth] = Depends(get_current_user_optional)
):
    search_limit = 5
    is_unlimited = False
    
    if current_user and (current_user.tier in ["A", "B"] or current_user.is_admin):
        is_unlimited = True
        search_limit = 999999
    
    # Check current searches today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    search_count = 0
    if current_user:
        history_ref = db.collection('users').document(current_user.id).collection('search_history')
        try:
            # Fetch all history for user, filter by date in Python to avoid missing index errors
            all_docs = history_ref.get()
            for d in all_docs:
                doc_data = d.to_dict()
                # Check if we have the date string (for newly added)
                today_str = today_start.strftime('%Y-%m-%d')
                if doc_data.get('date') == today_str:
                    search_count += 1
                elif doc_data.get('searched_at') and hasattr(doc_data['searched_at'], 'timestamp'):
                    if doc_data['searched_at'] >= today_start:
                        search_count += 1
        except Exception as e:
            print(f"User search tracking failed: {e}")
            search_count = 999
    else:
        # For anonymous users, use IP-based tracking in a simple collection
        ip = request.client.host
        anon_ref = db.collection('anonymous_searches')
        try:
            # Fetch by IP only to avoid compound index requirements, then filter by date in Python
            today_str = today_start.strftime('%Y-%m-%d')
            all_ip_docs = anon_ref.where('ip_address', '==', ip).get()
            search_count = sum(1 for d in all_ip_docs if d.to_dict().get('date') == today_str)
        except Exception as e:
            # If it still fails, heavily penalize or just assume they have reached the limit to prevent abuse bypassing the limit
            print(f"Anonymous search tracking failed: {e}")
            search_count = 999
        
    if search_count >= search_limit and not is_unlimited:
        raise HTTPException(
            status_code=429, 
            detail="Daily search limit reached. Please register or log in for more access."
        )
    
    # Resolve category name if category_id provided
    category_name = None
    if category_id:
        cat_doc = db.collection('categories').document(str(category_id)).get()
        if cat_doc.exists:
            category_name = cat_doc.to_dict().get("name_en")

    # Client-side filtering for MVP (since document count is low)
    all_docs = db.collection('proclamations').get()
    results = []
    
    q_lower = q.lower()
    for doc in all_docs:
        data = doc.to_dict()
        
        # Category filter
        cats = data.get('categories', [])
        if category_name and category_name not in cats:
            continue
            
        # Search match
        title_en = data.get('title_en', '').lower()
        title_am = data.get('title_am', '').lower()
        doc_num = data.get('document_number', '').lower()
        
        if q_lower in title_en or q_lower in title_am or q_lower in doc_num:
            results.append(DocumentSummary(id=doc.id, **data))
    
    # Pagination
    offset = (page - 1) * limit
    paginated_results = results[offset:offset + limit]

    # Log the search
    if current_user:
        history_ref = db.collection('users').document(current_user.id).collection('search_history')
        today_str = today_start.strftime('%Y-%m-%d')
        history_ref.add({
            "query": q,
            "filters": {"category_id": str(category_id)} if category_id else {},
            "result_count": len(results),
            "date": today_str,
            "searched_at": firestore.SERVER_TIMESTAMP
        })
    else:
        # Log anonymous search for tracking
        ip = request.client.host
        today_str = today_start.strftime('%Y-%m-%d')
        anon_ref = db.collection('anonymous_searches')
        try:
            anon_ref.add({
                "ip_address": ip,
                "date": today_str,
                "query": q,
                "result_count": len(results),
                "searched_at": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            print(f"Failed to log anonymous search: {e}")

    
    return {
        "query": q,
        "page": page,
        "limit": limit,
        "results": paginated_results,
        "searches_left": -1 if is_unlimited else max(0, search_limit - (search_count + 1))
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
def get_document_detail(document_id: str, db: Client = Depends(get_db)):
    doc_ref = db.collection('proclamations').document(document_id)
    doc_snap = doc_ref.get()
    
    if not doc_snap.exists:
        raise HTTPException(status_code=404, detail="Document not found")
    
    data = doc_snap.to_dict()
    
    # Extract sections from the 'articles' array embedded in the document
    sections_data = data.get('articles', [])
    sections = []
    
    for i, sec in enumerate(sections_data):
        sections.append(SectionDetail(
            section_type=sec.get('section_type', 'article'),
            section_number=sec.get('section_number'),
            section_number_am=sec.get('section_number_am'),
            title_am=sec.get('title_am'),
            title_en=sec.get('title_en'),
            content_am=sec.get('content_am'),
            content_en=sec.get('content_en'),
            sequence_order=sec.get('sequence_order', i)
        ))
        
    document_summary = DocumentSummary(id=doc_ref.id, **data)
    
    return {
        "document": document_summary,
        "sections": sections
    }

@router.get("/uploads/{filename}")
def download_file(filename: str):
    file_path = os.path.join("uploads", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type='application/pdf',
        filename=filename
    )
