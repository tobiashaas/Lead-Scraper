"""
Lead Scoring API Endpoints
Automatische Lead-Bewertung und Qualitätsanalyse
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.models.company import Company
from app.models.user import User
from app.utils.lead_scorer import LeadScorer, score_company

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scoring", tags=["Lead Scoring"])


@router.post("/companies/{company_id}")
async def score_single_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
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
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Company Daten für Scoring vorbereiten
        company_data = {
            "name": company.name,
            "email": company.email,
            "phone": company.phone,
            "website": company.website,
            "address": f"{company.street}, {company.postal_code} {company.city}"
            if company.street
            else None,
            "city": company.city,
            "industry": company.industry,
            "team_size": None,  # TODO: Add to model
            "technologies": [],  # TODO: Add to model
            "directors": [],  # TODO: Add to model
        }

        # Lead Scoring durchführen
        scoring_result = score_company(company_data)

        # Score in DB speichern
        company.lead_score = scoring_result["score"]
        company.lead_quality = scoring_result["quality"]

        await db.commit()
        await db.refresh(company)

        logger.info(
            f"Company scored: {company.name} (ID: {company_id}) - "
            f"Score: {scoring_result['score']} ({scoring_result['quality']})"
        )

        return {
            "company_id": company_id,
            "company_name": company.name,
            **scoring_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scoring failed for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}") from e


@router.post("/companies/bulk")
async def score_multiple_companies(
    company_ids: list[int] | None = None,
    lead_status: str | None = Query(None, description="Filter by lead status"),
    lead_quality: str | None = Query(None, description="Filter by lead quality"),
    limit: int = Query(100, ge=1, le=1000, description="Max companies to score"),
    db: AsyncSession = Depends(get_db),
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
        if company_ids:
            # Spezifische Companies
            query = select(Company).where(Company.id.in_(company_ids))
        else:
            # Mit Filtern
            query = select(Company).limit(limit)

            if lead_status:
                query = query.where(Company.lead_status == lead_status)
            if lead_quality:
                query = query.where(Company.lead_quality == lead_quality)

        result = await db.execute(query)
        companies = result.scalars().all()

        logger.info(f"Bulk scoring {len(companies)} companies...")

        # Alle Companies bewerten
        for company in companies:
            company_data = {
                "name": company.name,
                "email": company.email,
                "phone": company.phone,
                "website": company.website,
                "address": f"{company.street}, {company.postal_code} {company.city}"
                if company.street
                else None,
                "city": company.city,
                "industry": company.industry,
                "team_size": None,
                "technologies": [],
                "directors": [],
            }

            scoring_result = scorer.score_lead(company_data)

            # Score in DB speichern
            company.lead_score = scoring_result["score"]
            company.lead_quality = scoring_result["quality"]

            results.append(
                {
                    "company_id": company.id,
                    "company_name": company.name,
                    "score": scoring_result["score"],
                    "quality": scoring_result["quality"],
                }
            )

        # Commit alle Änderungen
        await db.commit()

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
    db: AsyncSession = Depends(get_db),
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
        total_result = await db.execute(total_query)
        total = total_result.scalar()

        # Average Score
        avg_query = select(func.avg(Company.lead_score))
        avg_result = await db.execute(avg_query)
        avg_score = avg_result.scalar() or 0

        # Distribution by Quality
        quality_query = select(Company.lead_quality, func.count(Company.id)).group_by(
            Company.lead_quality
        )
        quality_result = await db.execute(quality_query)
        by_quality = {quality: count for quality, count in quality_result.all()}

        # Top 10 Companies
        top_query = (
            select(Company)
            .where(Company.lead_score.isnot(None))
            .order_by(Company.lead_score.desc())
            .limit(10)
        )
        top_result = await db.execute(top_query)
        top_companies = [
            {"id": c.id, "name": c.name, "score": c.lead_score, "quality": c.lead_quality}
            for c in top_result.scalars().all()
        ]

        # Bottom 10 Companies
        bottom_query = (
            select(Company)
            .where(Company.lead_score.isnot(None))
            .order_by(Company.lead_score.asc())
            .limit(10)
        )
        bottom_result = await db.execute(bottom_query)
        bottom_companies = [
            {"id": c.id, "name": c.name, "score": c.lead_score, "quality": c.lead_quality}
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
