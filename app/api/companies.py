"""
Companies API Endpoints
CRUD operations for companies/leads
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.schemas import CompanyCreate, CompanyList, CompanyResponse, CompanyUpdate
from app.core.dependencies import get_current_active_user
from app.database.database import get_db
from app.database.models import Company, LeadQuality, LeadStatus, User
from app.utils.cache import cache_result, invalidate_pattern

router = APIRouter()


@router.get("/", response_model=CompanyList, response_model_exclude_none=True)
async def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    city: str | None = None,
    industry: str | None = None,
    lead_status: LeadStatus | None = None,
    lead_quality: LeadQuality | None = None,
    search: str | None = None,
    include_total: bool = Query(
        True,
        description="Return total count of results. Disable for faster pagination.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List companies with filters and pagination
    """
    query = db.query(Company).filter(Company.is_active)

    # Filters
    if city:
        query = query.filter(Company.city.ilike(f"%{city}%"))

    if industry:
        query = query.filter(Company.industry.ilike(f"%{industry}%"))

    if lead_status:
        query = query.filter(Company.lead_status == lead_status)

    if lead_quality:
        query = query.filter(Company.lead_quality == lead_quality)

    if search:
        query = query.filter(
            or_(
                Company.company_name.ilike(f"%{search}%"),
                Company.email.ilike(f"%{search}%"),
                Company.website.ilike(f"%{search}%"),
            )
        )

    total: int | None = query.count() if include_total else None

    companies = query.offset(skip).limit(limit).all()

    response_payload = {"skip": skip, "limit": limit, "items": companies}
    if include_total:
        response_payload["total"] = total

    return response_payload


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get company by ID
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with id {company_id} not found"
        )

    return company


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create new company
    """
    # Check if company already exists
    existing = (
        db.query(Company)
        .filter(Company.company_name == company.company_name, Company.city == company.city)
        .first()
    )

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company already exists")

    # Create company
    db_company = Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    await invalidate_pattern("company_stats_overview*")
    await invalidate_pattern("export_company_stats*")
    return db_company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    company_update: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update company
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with id {company_id} not found"
        )

    # Update fields
    update_data = company_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)
    await invalidate_pattern("company_stats_overview*")
    await invalidate_pattern("export_company_stats*")
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete company (soft delete)
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with id {company_id} not found"
        )

    # Soft delete
    company.is_active = False
    db.commit()
    await invalidate_pattern("company_stats_overview*")
    await invalidate_pattern("export_company_stats*")
    return None


@router.get("/stats/overview")
@cache_result(ttl=300, key_prefix="company_stats_overview")
async def get_stats(db: Session = Depends(get_db)):
    """
    Get statistics overview
    """
    total_companies = db.query(func.count(Company.id)).filter(Company.is_active).scalar()

    by_status = (
        db.query(Company.lead_status, func.count(Company.id))
        .filter(Company.is_active)
        .group_by(Company.lead_status)
        .all()
    )

    by_quality = (
        db.query(Company.lead_quality, func.count(Company.id))
        .filter(Company.is_active)
        .group_by(Company.lead_quality)
        .all()
    )

    by_city = (
        db.query(Company.city, func.count(Company.id))
        .filter(Company.is_active)
        .group_by(Company.city)
        .order_by(func.count(Company.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total_companies": total_companies,
        "by_status": {str(status): count for status, count in by_status},
        "by_quality": {str(quality): count for quality, count in by_quality},
        "top_cities": [{"city": city, "count": count} for city, count in by_city],
    }
