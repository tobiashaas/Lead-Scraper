"""
Pydantic Schemas for API
Request/Response models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, HttpUrl, Field

from app.database.models import LeadStatus, LeadQuality


# Base Schemas
class CompanyBase(BaseModel):
    """Base company schema"""
    company_name: str = Field(..., min_length=1, max_length=255)
    legal_form: Optional[str] = Field(None, max_length=50)
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    website: Optional[str] = Field(None, max_length=500)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    street: Optional[str] = Field(None, max_length=255)
    postal_code: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: str = Field(default="Deutschland", max_length=100)


class CompanyCreate(CompanyBase):
    """Schema for creating company"""
    directors: Optional[List[str]] = None
    team_size: Optional[int] = None
    services: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    extra_data: Optional[Dict[str, Any]] = None


class CompanyUpdate(BaseModel):
    """Schema for updating company"""
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    legal_form: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    lead_status: Optional[LeadStatus] = None
    lead_quality: Optional[LeadQuality] = None
    lead_score: Optional[float] = Field(None, ge=0, le=100)
    directors: Optional[List[str]] = None
    services: Optional[List[str]] = None
    technologies: Optional[List[str]] = None


class CompanyResponse(CompanyBase):
    """Schema for company response"""
    id: int
    directors: Optional[List[str]] = None
    team_size: Optional[int] = None
    team_members: Optional[List[Dict[str, Any]]] = None
    services: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    google_place_id: Optional[str] = None
    google_rating: Optional[float] = None
    google_reviews_count: Optional[int] = None
    register_number: Optional[str] = None
    register_court: Optional[str] = None
    lead_status: LeadStatus
    lead_quality: LeadQuality
    lead_score: float
    first_scraped_at: datetime
    last_updated_at: datetime
    is_active: bool
    extra_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class CompanyList(BaseModel):
    """Schema for paginated company list"""
    total: int
    skip: int
    limit: int
    items: List[CompanyResponse]


# Scraping Job Schemas
class ScrapingJobCreate(BaseModel):
    """Schema for creating scraping job"""
    job_name: Optional[str] = None
    source_name: str = Field(..., description="Source name (e.g., '11880', 'gelbe_seiten')")
    city: str = Field(..., min_length=1)
    industry: str = Field(..., min_length=1)
    max_pages: int = Field(default=5, ge=1, le=50)
    use_tor: bool = Field(default=True)
    use_ai: bool = Field(default=True, description="Use AI for data extraction")


class ScrapingJobResponse(BaseModel):
    """Schema for scraping job response"""
    id: int
    job_name: Optional[str]
    city: str
    industry: str
    status: str
    progress: float
    results_count: int
    new_companies: int
    updated_companies: int
    errors_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ScrapingJobList(BaseModel):
    """Schema for paginated scraping job list"""
    total: int
    skip: int
    limit: int
    items: List[ScrapingJobResponse]


# Note Schemas
class NoteCreate(BaseModel):
    """Schema for creating note"""
    title: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=1)
    note_type: Optional[str] = Field(None, max_length=50)


class NoteResponse(BaseModel):
    """Schema for note response"""
    id: int
    company_id: int
    title: Optional[str]
    content: str
    note_type: Optional[str]
    created_at: datetime
    created_by: Optional[str]
    
    class Config:
        from_attributes = True
