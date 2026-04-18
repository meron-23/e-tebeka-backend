from fastapi import APIRouter, Depends, HTTPException, Request
from google.cloud.firestore import Client
from google.cloud import firestore
from app.core.database import get_db
from app.api.deps import get_current_user, get_current_user_optional, UserAuth
from datetime import datetime, timezone
from typing import List, Optional

router = APIRouter()

@router.get("/")
@router.get("/me")
def get_users_profile(current_user: UserAuth = Depends(get_current_user)):
    return current_user

@router.get("/me/stats")
def get_user_stats(
    request: Request,
    db: Client = Depends(get_db),
    current_user: Optional[UserAuth] = Depends(get_current_user_optional)
):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    if current_user:
        search_limit = 5 if current_user.tier == "C" else -1
        history_ref = db.collection('users').document(current_user.id).collection('search_history')
        docs = history_ref.get()
        search_count = sum(1 for d in docs if d.to_dict().get('date') == today_start.strftime('%Y-%m-%d') or (d.to_dict().get('searched_at') and getattr(d.to_dict().get('searched_at'), 'timestamp', lambda: 0)() and d.to_dict().get('searched_at') >= today_start))
        views_limit = 10 if current_user.tier == "C" else -1
    else:
        search_limit = 5
        ip = request.client.host
        anon_ref = db.collection('anonymous_searches')
        today_str = today_start.strftime('%Y-%m-%d')
        all_ip_docs = anon_ref.where('ip_address', '==', ip).get()
        search_count = sum(1 for d in all_ip_docs if d.to_dict().get('date') == today_str)
        views_limit = 5
        
    return {
        "searches_today": search_count,
        "search_limit": search_limit,
        "views_today": 0,
        "views_limit": views_limit
    }

@router.get("/me/history")
def get_user_history(
    limit: int = 5,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    history_ref = db.collection('users').document(current_user.id).collection('search_history')
    docs = history_ref.order_by('searched_at', direction=firestore.Query.DESCENDING).limit(limit).get()
    
    history = []
    for doc in docs:
        data = doc.to_dict()
        history.append({
            "id": doc.id,
            "query": data.get("query"),
            "searched_at": data.get("searched_at")
        })
        
    return history


@router.get("/me/downloads")
def get_user_downloads(
    limit: int = 5,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    downloads_ref = db.collection('users').document(current_user.id).collection('download_history')
    docs = downloads_ref.order_by('downloaded_at', direction=firestore.Query.DESCENDING).limit(limit).get()

    downloads = []
    for doc in docs:
        data = doc.to_dict()
        downloads.append({
            "id": doc.id,
            "document_title": data.get("document_title"),
            "document_number": data.get("document_number"),
            "downloaded_at": data.get("downloaded_at"),
            "file_size": data.get("file_size", 0)
        })

    return downloads

@router.get("/me/bookmarks")
def get_user_bookmarks(
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    bookmarks_ref = db.collection('users').document(current_user.id).collection('bookmarks')
    docs = bookmarks_ref.order_by('created_at', direction=firestore.Query.DESCENDING).get()
    
    bookmarks = []
    for doc in docs:
        data = doc.to_dict()
        bookmarks.append({
            "id": doc.id,
            "document_id": data.get("document_id"),
            "title_en": data.get("title_en"),
            "title_am": data.get("title_am"),
            "document_number": data.get("document_number"),
            "created_at": data.get("created_at")
        })
        
    return bookmarks

@router.post("/me/bookmarks")
def add_bookmark(
    bookmark_data: dict,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    document_id = bookmark_data.get("document_id")
    if not document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    
    # Check if document exists
    doc_ref = db.collection('proclamations').document(document_id)
    doc_doc = doc_ref.get()
    if not doc_doc.exists:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc_data = doc_doc.to_dict()
    
    # Check if already bookmarked
    bookmarks_ref = db.collection('users').document(current_user.id).collection('bookmarks')
    existing = bookmarks_ref.where('document_id', '==', document_id).limit(1).get()
    if len(existing) > 0:
        raise HTTPException(status_code=409, detail="Document already bookmarked")
    
    # Add bookmark
    bookmark_ref = bookmarks_ref.document()
    bookmark_ref.set({
        "document_id": document_id,
        "title_en": doc_data.get("title_en"),
        "title_am": doc_data.get("title_am"),
        "document_number": doc_data.get("document_number"),
        "created_at": firestore.SERVER_TIMESTAMP
    })
    
    return {"message": "Bookmark added successfully", "bookmark_id": bookmark_ref.id}

@router.delete("/me/bookmarks/{document_id}")
def remove_bookmark(
    document_id: str,
    db: Client = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user)
):
    bookmarks_ref = db.collection('users').document(current_user.id).collection('bookmarks')
    existing = bookmarks_ref.where('document_id', '==', document_id).limit(1).get()
    
    if not len(existing):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    
    existing.docs[0].reference.delete()
    return {"message": "Bookmark removed successfully"}
