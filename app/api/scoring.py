"""
Lead Scoring API Endpoints
Automatische Lead-Bewertung und Qualitätsanalyse
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.database.models import Company, LeadQuality, User
from app.utils.lead_scorer import LeadScorer, score_company

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scoring", tags=["Lead Scoring"])


def map_quality_to_enum(quality_str: str) -> LeadQuality:
    """Maps scoring quality string to LeadQuality enum"""
    quality_map = {
        "hot": LeadQuality.A,
        "warm": LeadQuality.B,
        "cold": LeadQuality.C,
        "low_quality": LeadQuality.D,
    }
    return quality_map.get(quality_str, LeadQuality.UNKNOWN)


class BulkScoreRequest(BaseModel):
    """Bulk Score Request Schema"""

    company_ids: list[int] | None = None

    model_config = {"extra": "allow"}


@router.post("/companies/{company_id}")
async def score_single_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Bewertet eine einzelne Company und updated den Score

    **Permissions:** Authenticated users only

    **Returns:**
    - score: Lead Score (0-100)
    - quality: Qualitätskategorie (hot/warm/cold/low_quality)
    - breakdown: Detaillierte Score-Aufschlüsselung
    - recommendations: Verbesserungsvorschläge
    """
    try:
        # Company laden
        result = db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Company Daten für Scoring vorbereiten
        # Build address string safely
        address_parts = []
        if company.street:
            address_parts.append(company.street)
        if company.postal_code or company.city:
            city_part = f"{company.postal_code or ''} {company.city or ''}".strip()
            if city_part:
                address_parts.append(city_part)
        address = ", ".join(address_parts) if address_parts else None

        company_data = {
            "name": company.company_name,
            "email": company.email,
            "phone": company.phone,
            "website": company.website,
            "address": address,
            "city": company.city,
            "industry": company.industry,
            "team_size": company.team_size,
            "technologies": company.technologies or [],
            "directors": company.directors or [],
        }

        # Lead Scoring durchführen
        scoring_result = score_company(company_data)

        # Score in DB speichern
        company.lead_score = scoring_result["score"]
        company.lead_quality = map_quality_to_enum(scoring_result["quality"])

        db.commit()
        db.refresh(company)

        logger.info(
            f"Company scored: {company.company_name} (ID: {company_id}) - "
            f"Score: {scoring_result['score']} ({scoring_result['quality']})"
        )

        return {
            "company_id": company_id,
            "company_name": company.company_name,
            **scoring_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scoring failed for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}") from e


@router.post("/companies/bulk")
async def score_multiple_companies(
    request: BulkScoreRequest = Body(default=BulkScoreRequest()),
    lead_status: str | None = Query(None, description="Filter by lead status"),
    lead_quality: str | None = Query(None, description="Filter by lead quality"),
    limit: int = Query(100, ge=1, le=1000, description="Max companies to score"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Bewertet mehrere Companies auf einmal

    **Permissions:** Authenticated users only

    **Options:**
    - Specific company_ids: Score nur diese Companies
    - Filters: Score alle Companies die Filter matchen
    - Limit: Max Anzahl zu bewertender Companies

    **Returns:**
    - total_scored: Anzahl bewerteter Companies
    - results: Liste mit Scoring-Ergebnissen
    - stats: Statistiken über Scoring-Verteilung
    """
    try:
        scorer = LeadScorer()
        results = []

        # Query aufbauen
        if request.company_ids:
            # Spezifische Companies
            query = select(Company).where(Company.id.in_(request.company_ids))
        else:
            # Mit Filtern
            query = select(Company).limit(limit)

            if lead_status:
                query = query.where(Company.lead_status == lead_status)
            if lead_quality:
                query = query.where(Company.lead_quality == lead_quality)

        result = db.execute(query)
        companies = result.scalars().all()

        logger.info(f"Bulk scoring {len(companies)} companies...")

        # Alle Companies bewerten
        for company in companies:
            # Build address string safely
            address_parts = []
            if company.street:
                address_parts.append(company.street)
            if company.postal_code or company.city:
                city_part = f"{company.postal_code or ''} {company.city or ''}".strip()
                if city_part:
                    address_parts.append(city_part)
            address = ", ".join(address_parts) if address_parts else None

            company_data = {
                "name": company.company_name,
                "email": company.email,
                "phone": company.phone,
                "website": company.website,
                "address": address,
                "city": company.city,
                "industry": company.industry,
                "team_size": company.team_size,
                "technologies": company.technologies or [],
                "directors": company.directors or [],
            }

            scoring_result = scorer.score_lead(company_data)

            # Score in DB speichern
            company.lead_score = scoring_result["score"]
            company.lead_quality = map_quality_to_enum(scoring_result["quality"])

            results.append(
                {
                    "company_id": company.id,
                    "company_name": company.company_name,
                    "score": scoring_result["score"],
                    "quality": scoring_result["quality"],
                }
            )

        # Commit alle Änderungen
        db.commit()

        # Statistiken
        stats = scorer.get_stats()

        logger.info(f"Bulk scoring completed: {len(results)} companies scored")

        return {
            "total_scored": len(results),
            "results": results,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Bulk scoring failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk scoring failed: {str(e)}") from e


@router.get("/stats")
async def get_scoring_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Gibt Lead Scoring Statistiken zurück

    **Permissions:** Authenticated users only

    **Returns:**
    - Distribution nach Quality
    - Durchschnittlicher Score
    - Top/Bottom Companies
    """
    try:
        from sqlalchemy import func

        # Total Companies
        total_query = select(func.count(Company.id))
        total_result = db.execute(total_query)
        total = total_result.scalar()

        # Average Score
        avg_query = select(func.avg(Company.lead_score))
        avg_result = db.execute(avg_query)
        avg_score = avg_result.scalar() or 0

        # Distribution by Quality
        quality_query = select(Company.lead_quality, func.count(Company.id)).group_by(
            Company.lead_quality
        )
        quality_result = db.execute(quality_query)
        by_quality = dict(quality_result.all())

        # Top 10 Companies
        top_query = (
            select(Company)
            .where(Company.lead_score.isnot(None))
            .order_by(Company.lead_score.desc())
            .limit(10)
        )
        top_result = db.execute(top_query)
        top_companies = [
            {
                "id": c.id,
                "name": c.company_name,
                "score": c.lead_score,
                "quality": c.lead_quality,
            }
            for c in top_result.scalars().all()
        ]

        # Bottom 10 Companies
        bottom_query = (
            select(Company)
            .where(Company.lead_score.isnot(None))
            .order_by(Company.lead_score.asc())
            .limit(10)
        )
        bottom_result = db.execute(bottom_query)
        bottom_companies = [
            {
                "id": c.id,
                "name": c.company_name,
                "score": c.lead_score,
                "quality": c.lead_quality,
            }
            for c in bottom_result.scalars().all()
        ]

        return {
            "total_companies": total,
            "average_score": round(avg_score, 2),
            "distribution_by_quality": by_quality,
            "top_companies": top_companies,
            "bottom_companies": bottom_companies,
        }

    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}") from e
