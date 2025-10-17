"""
Pydantic Schemas for API
Request/Response models
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.database.models import LeadQuality, LeadStatus


# Base Schemas
class CompanyBase(BaseModel):
    """Base company schema"""

    company_name: str = Field(..., min_length=1, max_length=255)
    legal_form: str | None = Field(None, max_length=50)
    industry: str | None = Field(None, max_length=100)
    description: str | None = None
    website: str | None = Field(None, max_length=500)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    street: str | None = Field(None, max_length=255)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    country: str = Field(default="Deutschland", max_length=100)


class CompanyCreate(CompanyBase):
    """Schema for creating company"""

    directors: list[str] | None = None
    team_size: int | None = None
    services: list[str] | None = None
    technologies: list[str] | None = None
    extra_data: dict[str, Any] | None = None


class CompanyUpdate(BaseModel):
    """Schema for updating company"""

    company_name: str | None = Field(None, min_length=1, max_length=255)
    legal_form: str | None = None
    industry: str | None = None
    description: str | None = None
    website: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    lead_status: LeadStatus | None = None
    lead_quality: LeadQuality | None = None
    lead_score: float | None = Field(None, ge=0, le=100)
    directors: list[str] | None = None
    services: list[str] | None = None
    technologies: list[str] | None = None


class CompanyResponse(CompanyBase):
    """Schema for company response"""

    id: int
    directors: list[str] | None = None
    team_size: int | None = None
    team_members: list[dict[str, Any]] | None = None
    services: list[str] | None = None
    technologies: list[str] | None = None
    google_place_id: str | None = None
    google_rating: float | None = None
    google_reviews_count: int | None = None
    register_number: str | None = None
    register_court: str | None = None
    lead_status: LeadStatus
    lead_quality: LeadQuality
    lead_score: float
    first_scraped_at: datetime
    last_updated_at: datetime
    is_active: bool
    extra_data: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class CompanyList(BaseModel):
    """Schema for paginated company list"""

    total: int
    skip: int
    limit: int
    items: list[CompanyResponse]


# Scraping Job Schemas
class ScrapingJobCreate(BaseModel):
    """Schema for creating scraping job"""

    job_name: str | None = None
    source_name: str = Field(..., description="Source name (e.g., '11880', 'gelbe_seiten')")
    city: str = Field(..., min_length=1)
    industry: str = Field(..., min_length=1)
    max_pages: int = Field(default=5, ge=1, le=50)
    use_tor: bool = Field(default=True)
    use_ai: bool = Field(default=True, description="Use AI for data extraction")


class ScrapingJobResponse(BaseModel):
    """Schema for scraping job response"""

    id: int
    job_name: str | None
    city: str
    industry: str
    status: str
    progress: float
    results_count: int
    new_companies: int
    updated_companies: int
    errors_count: int
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ScrapingJobList(BaseModel):
    """Schema for paginated scraping job list"""

    total: int
    skip: int
    limit: int
    items: list[ScrapingJobResponse]


# Note Schemas
class NoteCreate(BaseModel):
    """Schema for creating note"""

    title: str | None = Field(None, max_length=255)
    content: str = Field(..., min_length=1)
    note_type: str | None = Field(None, max_length=50)


class NoteResponse(BaseModel):
    """Schema for note response"""

    id: int
    company_id: int
    title: str | None
    content: str
    note_type: str | None
    created_at: datetime
    created_by: str | None

    class Config:
        from_attributes = True
