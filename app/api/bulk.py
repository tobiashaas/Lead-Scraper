"""
Bulk Operations API Endpoints
Massenoperationen für Companies (Update, Delete, Status Change)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.models.company import Company
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bulk", tags=["Bulk Operations"])


class BulkUpdateRequest(BaseModel):
    """Bulk Update Request Schema"""

    company_ids: list[int]
    updates: dict[str, Any]


class BulkDeleteRequest(BaseModel):
    """Bulk Delete Request Schema"""

    company_ids: list[int]
    soft_delete: bool = True  # Soft delete by default


class BulkStatusChangeRequest(BaseModel):
    """Bulk Status Change Request Schema"""

    company_ids: list[int]
    lead_status: str | None = None
    lead_quality: str | None = None


@router.post("/companies/update")
async def bulk_update_companies(
    request: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Bulk Update für mehrere Companies

    **Permissions:** Authenticated users only

    **Allowed Updates:**
    - lead_status
    - lead_quality
    - industry
    - notes
    - tags

    **Example:**
    ```json
    {
        "company_ids": [1, 2, 3],
        "updates": {
            "lead_status": "contacted",
            "lead_quality": "warm"
        }
    }
    ```

    **Returns:**
    - updated_count: Anzahl aktualisierter Companies
    - failed_ids: IDs die nicht aktualisiert werden konnten
    """
    try:
        # Validiere Updates (nur erlaubte Felder)
        allowed_fields = {"lead_status", "lead_quality", "industry", "notes", "tags", "lead_score"}

        invalid_fields = set(request.updates.keys()) - allowed_fields
        if invalid_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid update fields: {invalid_fields}. Allowed: {allowed_fields}",
            )

        if not request.company_ids:
            raise HTTPException(status_code=400, detail="No company IDs provided")

        # Prüfe ob Companies existieren
        result = await db.execute(select(Company.id).where(Company.id.in_(request.company_ids)))
        existing_ids = {row[0] for row in result.all()}
        failed_ids = list(set(request.company_ids) - existing_ids)

        # Bulk Update
        if existing_ids:
            stmt = (
                update(Company).where(Company.id.in_(list(existing_ids))).values(**request.updates)
            )
            await db.execute(stmt)
            await db.commit()

        updated_count = len(existing_ids)

        logger.info(f"Bulk update: {updated_count} companies updated by {current_user.username}")

        return {
            "success": True,
            "updated_count": updated_count,
            "failed_ids": failed_ids,
            "updates_applied": request.updates,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk update failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk update failed: {str(e)}")


@router.post("/companies/delete")
async def bulk_delete_companies(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Bulk Delete für mehrere Companies

    **Permissions:** Authenticated users only

    **Options:**
    - soft_delete: True = Set is_active=False (default)
    - soft_delete: False = Permanent delete from database

    **Example:**
    ```json
    {
        "company_ids": [1, 2, 3],
        "soft_delete": true
    }
    ```

    **Returns:**
    - deleted_count: Anzahl gelöschter Companies
    - failed_ids: IDs die nicht gelöscht werden konnten
    """
    try:
        if not request.company_ids:
            raise HTTPException(status_code=400, detail="No company IDs provided")

        # Prüfe ob Companies existieren
        result = await db.execute(select(Company.id).where(Company.id.in_(request.company_ids)))
        existing_ids = {row[0] for row in result.all()}
        failed_ids = list(set(request.company_ids) - existing_ids)

        if existing_ids:
            if request.soft_delete:
                # Soft Delete: Set is_active = False
                stmt = (
                    update(Company)
                    .where(Company.id.in_(list(existing_ids)))
                    .values(is_active=False)
                )
                await db.execute(stmt)
            else:
                # Hard Delete: Remove from database
                stmt = delete(Company).where(Company.id.in_(list(existing_ids)))
                await db.execute(stmt)

            await db.commit()

        deleted_count = len(existing_ids)

        logger.warning(
            f"Bulk delete: {deleted_count} companies "
            f"({'soft' if request.soft_delete else 'hard'}) deleted by {current_user.username}"
        )

        return {
            "success": True,
            "deleted_count": deleted_count,
            "failed_ids": failed_ids,
            "soft_delete": request.soft_delete,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk delete failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")


@router.post("/companies/status")
async def bulk_change_status(
    request: BulkStatusChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Bulk Status Change für mehrere Companies

    **Permissions:** Authenticated users only

    **Example:**
    ```json
    {
        "company_ids": [1, 2, 3],
        "lead_status": "contacted",
        "lead_quality": "warm"
    }
    ```

    **Returns:**
    - updated_count: Anzahl aktualisierter Companies
    - changes: Angewandte Änderungen
    """
    try:
        if not request.company_ids:
            raise HTTPException(status_code=400, detail="No company IDs provided")

        if not request.lead_status and not request.lead_quality:
            raise HTTPException(
                status_code=400,
                detail="At least one of lead_status or lead_quality must be provided",
            )

        # Build updates dict
        updates = {}
        if request.lead_status:
            updates["lead_status"] = request.lead_status
        if request.lead_quality:
            updates["lead_quality"] = request.lead_quality

        # Prüfe ob Companies existieren
        result = await db.execute(select(Company.id).where(Company.id.in_(request.company_ids)))
        existing_ids = {row[0] for row in result.all()}

        if existing_ids:
            stmt = update(Company).where(Company.id.in_(list(existing_ids))).values(**updates)
            await db.execute(stmt)
            await db.commit()

        updated_count = len(existing_ids)

        logger.info(
            f"Bulk status change: {updated_count} companies updated by {current_user.username}"
        )

        return {
            "success": True,
            "updated_count": updated_count,
            "changes": updates,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk status change failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk status change failed: {str(e)}")


@router.post("/companies/restore")
async def bulk_restore_companies(
    company_ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Bulk Restore für soft-deleted Companies

    **Permissions:** Authenticated users only

    **Returns:**
    - restored_count: Anzahl wiederhergestellter Companies
    """
    try:
        if not company_ids:
            raise HTTPException(status_code=400, detail="No company IDs provided")

        # Restore: Set is_active = True
        stmt = (
            update(Company)
            .where(Company.id.in_(company_ids))
            .where(Company.is_active == False)
            .values(is_active=True)
        )
        result = await db.execute(stmt)
        await db.commit()

        restored_count = result.rowcount

        logger.info(f"Bulk restore: {restored_count} companies restored by {current_user.username}")

        return {
            "success": True,
            "restored_count": restored_count,
        }

    except Exception as e:
        logger.error(f"Bulk restore failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk restore failed: {str(e)}")
