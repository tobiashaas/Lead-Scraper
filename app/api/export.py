"""
Export API Endpoints
Exportiert Companies in verschiedenen Formaten (CSV, Excel, JSON)
"""

import csv
import io
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.database.models import Company, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/companies/csv")
async def export_companies_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    lead_status: str | None = Query(None, description="Filter by lead status"),
    lead_quality: str | None = Query(None, description="Filter by lead quality"),
    limit: int = Query(1000, ge=1, le=10000, description="Max results"),
) -> StreamingResponse:
    """
    Exportiert Companies als CSV

    **Permissions:** Authenticated users only

    **Features:**
    - Filter by lead_status, lead_quality
    - Max 10,000 companies per export
    - Streaming response für große Datasets
    """
    try:
        # Query mit Filtern
        query = select(Company).limit(limit)

        if lead_status:
            query = query.where(Company.lead_status == lead_status)
        if lead_quality:
            query = query.where(Company.lead_quality == lead_quality)

        result = await db.execute(query)
        companies = result.scalars().all()

        logger.info(f"Exporting {len(companies)} companies to CSV (user: {current_user.username})")

        # CSV in Memory erstellen
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "ID",
                "Name",
                "City",
                "Street",
                "Postal Code",
                "Phone",
                "Email",
                "Website",
                "Industry",
                "Lead Status",
                "Lead Quality",
                "Lead Score",
                "Created At",
                "Updated At",
            ]
        )

        # Daten
        for company in companies:
            writer.writerow(
                [
                    company.id,
                    company.name,
                    company.city,
                    company.street,
                    company.postal_code,
                    company.phone,
                    company.email,
                    company.website,
                    company.industry,
                    company.lead_status,
                    company.lead_quality,
                    company.lead_score,
                    company.created_at.isoformat() if company.created_at else "",
                    company.updated_at.isoformat() if company.updated_at else "",
                ]
            )

        # Stream Response
        output.seek(0)

        filename = f"companies_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error(f"CSV export failed: {e}")
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}") from e


@router.get("/companies/json")
async def export_companies_json(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    lead_status: str | None = Query(None, description="Filter by lead status"),
    lead_quality: str | None = Query(None, description="Filter by lead quality"),
    limit: int = Query(1000, ge=1, le=10000, description="Max results"),
) -> dict[str, Any]:
    """
    Exportiert Companies als JSON

    **Permissions:** Authenticated users only

    **Features:**
    - Filter by lead_status, lead_quality
    - Max 10,000 companies per export
    - Strukturiertes JSON Format
    """
    try:
        # Query mit Filtern
        query = select(Company).limit(limit)

        if lead_status:
            query = query.where(Company.lead_status == lead_status)
        if lead_quality:
            query = query.where(Company.lead_quality == lead_quality)

        result = await db.execute(query)
        companies = result.scalars().all()

        logger.info(f"Exporting {len(companies)} companies to JSON (user: {current_user.username})")

        # Konvertiere zu Dict
        companies_data = []
        for company in companies:
            companies_data.append(
                {
                    "id": company.id,
                    "name": company.name,
                    "city": company.city,
                    "street": company.street,
                    "postal_code": company.postal_code,
                    "phone": company.phone,
                    "email": company.email,
                    "website": company.website,
                    "industry": company.industry,
                    "lead_status": company.lead_status,
                    "lead_quality": company.lead_quality,
                    "lead_score": company.lead_score,
                    "created_at": company.created_at.isoformat() if company.created_at else None,
                    "updated_at": company.updated_at.isoformat() if company.updated_at else None,
                }
            )

        return {
            "total": len(companies_data),
            "exported_at": datetime.now().isoformat(),
            "filters": {
                "lead_status": lead_status,
                "lead_quality": lead_quality,
                "limit": limit,
            },
            "companies": companies_data,
        }

    except Exception as e:
        logger.error(f"JSON export failed: {e}")
        raise HTTPException(status_code=500, detail=f"JSON export failed: {str(e)}") from e


@router.get("/companies/stats")
async def export_companies_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Exportiert Company Statistiken

    **Permissions:** Authenticated users only

    **Returns:**
    - Total companies
    - Breakdown by lead_status
    - Breakdown by lead_quality
    - Top industries
    - Top cities
    """
    try:
        from sqlalchemy import func

        # Total Count
        total_query = select(func.count(Company.id))
        total_result = await db.execute(total_query)
        total = total_result.scalar()

        # By Lead Status
        status_query = select(Company.lead_status, func.count(Company.id)).group_by(
            Company.lead_status
        )
        status_result = await db.execute(status_query)
        by_status = dict(status_result.all())

        # By Lead Quality
        quality_query = select(Company.lead_quality, func.count(Company.id)).group_by(
            Company.lead_quality
        )
        quality_result = await db.execute(quality_query)
        by_quality = dict(quality_result.all())

        # Top Industries
        industry_query = (
            select(Company.industry, func.count(Company.id))
            .where(Company.industry.isnot(None))
            .group_by(Company.industry)
            .order_by(func.count(Company.id).desc())
            .limit(10)
        )
        industry_result = await db.execute(industry_query)
        top_industries = [
            {"industry": industry, "count": count} for industry, count in industry_result.all()
        ]

        # Top Cities
        city_query = (
            select(Company.city, func.count(Company.id))
            .where(Company.city.isnot(None))
            .group_by(Company.city)
            .order_by(func.count(Company.id).desc())
            .limit(10)
        )
        city_result = await db.execute(city_query)
        top_cities = [{"city": city, "count": count} for city, count in city_result.all()]

        logger.info(f"Exported company stats (user: {current_user.username})")

        return {
            "total_companies": total,
            "by_lead_status": by_status,
            "by_lead_quality": by_quality,
            "top_industries": top_industries,
            "top_cities": top_cities,
            "exported_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Stats export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats export failed: {str(e)}") from e
