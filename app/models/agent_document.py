# backend/app/models/agent_document.py - RAG TRAINING DOCUMENTS

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from bson import ObjectId
import mimetypes


class AgentDocument(BaseModel):
    """
    Training Document Model for RAG
    Stores uploaded documents and their embeddings for agent knowledge
    """
    
    # ============================================
    # IDENTIFICATION
    # ============================================
    id: Optional[str] = Field(None, alias="_id")
    agent_id: str = Field(..., description="Agent this document belongs to")
    user_id: str = Field(..., description="User who uploaded the document")
    
    # ============================================
    # FILE INFORMATION
    # ============================================
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Storage path on server")
    file_type: str = Field(..., description="MIME type (pdf, docx, txt)")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    
    # ============================================
    # CONTENT & EMBEDDINGS
    # ============================================
    extracted_text: Optional[str] = Field(
        None,
        description="Full extracted text from document"
    )
    
    chunks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Text chunks with embeddings. Format: [{'text': '', 'embedding': [], 'chunk_id': ''}]"
    )
    
    total_chunks: int = Field(
        default=0,
        description="Total number of chunks"
    )
    
    # ============================================
    # PROCESSING STATUS
    # ============================================
    processing_status: str = Field(
        default="pending",
        description="Processing status: 'pending', 'processing', 'completed', 'failed'"
    )
    
    processing_error: Optional[str] = Field(
        None,
        description="Error message if processing failed"
    )
    
    # ============================================
    # METADATA
    # ============================================
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (page count, word count, etc.)"
    )
    
    # ============================================
    # USAGE TRACKING
    # ============================================
    usage_count: int = Field(
        default=0,
        description="Number of times document was queried"
    )
    
    last_used: Optional[datetime] = Field(
        None,
        description="Last time document was queried"
    )
    
    # ============================================
    # TIMESTAMPS
    # ============================================
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # ============================================
    # VALIDATORS
    # ============================================
    @validator('file_type')
    def validate_file_type(cls, v):
        allowed_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # docx
            'application/msword',  # doc
            'text/plain',
            'text/markdown'
        ]
        if v not in allowed_types:
            raise ValueError(f"Unsupported file type: {v}. Allowed: PDF, DOCX, TXT, MD")
        return v
    
    @validator('processing_status')
    def validate_processing_status(cls, v):
        if v not in ['pending', 'processing', 'completed', 'failed']:
            raise ValueError("Invalid processing status")
        return v
    
    @validator('file_size')
    def validate_file_size(cls, v):
        # Max 10MB per file
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if v > max_size:
            raise ValueError(f"File size exceeds maximum allowed size of 10MB")
        return v
    
    @validator('chunks')
    def validate_chunks(cls, v):
        """Validate chunk structure"""
        for chunk in v:
            if 'text' not in chunk or 'embedding' not in chunk:
                raise ValueError("Each chunk must have 'text' and 'embedding' fields")
            if not isinstance(chunk['embedding'], list):
                raise ValueError("Embedding must be a list of floats")
        return v
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "agent_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "filename": "product_catalog.pdf",
                "file_path": "/uploads/docs/agent_123/product_catalog.pdf",
                "file_type": "application/pdf",
                "file_size": 2048576,
                "total_chunks": 45,
                "processing_status": "completed",
                "metadata": {
                    "page_count": 12,
                    "word_count": 3500
                }
            }
        }


class DocumentChunk(BaseModel):
    """Individual text chunk with embedding"""
    chunk_id: str
    text: str
    embedding: List[float]
    chunk_index: int
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)