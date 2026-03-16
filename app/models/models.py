from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, Text, ForeignKey, Date, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50))
    tier = Column(String(1), nullable=False) # 'A', 'B', 'C'
    status = Column(String(20), default="pending") # 'pending', 'active', 'suspended'
    email_verified = Column(Boolean, default=False)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    profile = relationship("UserProfile", back_populates="user", uselist=False)
    saved_items = relationship("SavedItem", back_populates="user")
    searches = relationship("SearchHistory", back_populates="user")
    downloads = relationship("DownloadLog", back_populates="user")
    verification = relationship("StudentVerification", back_populates="user", uselist=False)

class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    organization = Column(String(255))
    bar_number = Column(String(100))
    student_id = Column(String(100))
    student_id_document = Column(String(500))
    university = Column(String(255))
    verification_status = Column(String(20), default="pending") # 'pending', 'verified', 'rejected'
    verified_by = Column(UUID(as_uuid=True))
    verified_at = Column(DateTime)
    daily_view_count = Column(Integer, default=0)
    last_view_reset = Column(Date, default=datetime.utcnow().date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")

class LegalDocument(Base):
    __tablename__ = "legal_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type = Column(String(20), nullable=False) # 'proclamation', 'regulation'
    document_number = Column(String(50), nullable=False)
    document_number_am = Column(String(50))
    issuing_body_am = Column(Text)
    issuing_body_en = Column(Text)
    title_am = Column(Text, nullable=False)
    title_en = Column(Text, nullable=False)
    short_title_am = Column(Text)
    short_title_en = Column(Text)
    year_ec = Column(Integer)
    year_gregorian = Column(Integer)
    date_issued_ec = Column(String(50))
    date_issued_gregorian = Column(Date)
    date_published_ec = Column(String(50))
    date_published_gregorian = Column(Date)
    gazette_year = Column(Integer)
    gazette_number = Column(Integer)
    page_start = Column(Integer)
    page_end = Column(Integer)
    status = Column(String(20), default="active") # 'active', 'amended', 'repealed'
    pdf_url = Column(Text)
    word_count = Column(Integer)
    page_count = Column(Integer)
    signed_by_am = Column(Text)
    signed_by_en = Column(Text)
    signed_title_am = Column(Text)
    signed_title_en = Column(Text)
    legal_basis_am = Column(Text)
    legal_basis_en = Column(Text)
    parent_proclamation_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"))
    amends_document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))

    sections = relationship("DocumentSection", back_populates="document")
    categories = relationship("Category", secondary="document_categories", back_populates="documents")

class DocumentSection(Base):
    __tablename__ = "document_sections"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), nullable=False)
    parent_section_id = Column(UUID(as_uuid=True), ForeignKey("document_sections.id"))
    section_type = Column(String(20), nullable=False)
    section_number = Column(String(50))
    section_number_am = Column(String(50))
    title_am = Column(Text)
    title_en = Column(Text)
    content_am = Column(Text)
    content_en = Column(Text)
    sequence_order = Column(Integer, nullable=False)
    level = Column(Integer, default=1)
    word_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("LegalDocument", back_populates="sections")

class Category(Base):
    __tablename__ = "categories"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_am = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    description_am = Column(Text)
    description_en = Column(Text)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("LegalDocument", secondary="document_categories", back_populates="categories")

class DocumentCategory(Base):
    __tablename__ = "document_categories"
    document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), primary_key=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SavedItem(Base):
    __tablename__ = "saved_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), nullable=False)
    section_id = Column(UUID(as_uuid=True), ForeignKey("document_sections.id"))
    notes = Column(Text)
    saved_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="saved_items")

class SearchHistory(Base):
    __tablename__ = "search_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    query = Column(Text, nullable=False)
    ip_address = Column(String(50))
    filters = Column(JSONB)
    result_count = Column(Integer)
    searched_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="searches")

class DownloadLog(Base):
    __tablename__ = "download_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), nullable=False)
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(INET)

    user = relationship("User", back_populates="downloads")

class StudentVerification(Base):
    __tablename__ = "student_verifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    student_id_number = Column(String(100), nullable=False)
    university = Column(String(255), nullable=False)
    document_path = Column(String(500), nullable=False)
    status = Column(String(20), default="pending")
    reviewed_by = Column(UUID(as_uuid=True))
    review_notes = Column(Text)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)

    user = relationship("User", back_populates="verification")

class UploadJob(Base):
    __tablename__ = "upload_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = Column(String(500))
    status = Column(String(20), default="pending")
    gemini_response = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

class Admin(Base):
    __tablename__ = "admins"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
