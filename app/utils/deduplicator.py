"""
Company Deduplicator
Identifies and merges duplicate company entries
"""

import logging
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database.models import Company

logger = logging.getLogger(__name__)


class CompanyDeduplicator:
    """Service for detecting and merging duplicate companies"""

    def __init__(self, name_similarity_threshold: float = 0.85):
        """
        Initialize deduplicator

        Args:
            name_similarity_threshold: Minimum similarity score for name matching (0-1)
        """
        self.name_similarity_threshold = name_similarity_threshold

    def _normalize_string(self, text: str | None) -> str:
        """
        Normalize string for comparison

        Args:
            text: Input text

        Returns:
            Normalized lowercase string without extra whitespace
        """
        if not text:
            return ""
        return " ".join(text.lower().strip().split())

    def _calculate_similarity(self, str1: str | None, str2: str | None) -> float:
        """
        Calculate similarity between two strings using SequenceMatcher

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score between 0 and 1
        """
        if not str1 or not str2:
            return 0.0

        norm1 = self._normalize_string(str1)
        norm2 = self._normalize_string(str2)

        if not norm1 or not norm2:
            return 0.0

        return SequenceMatcher(None, norm1, norm2).ratio()

    def _normalize_phone(self, phone: str | None) -> str:
        """
        Normalize phone number for comparison

        Args:
            phone: Phone number

        Returns:
            Normalized phone number (digits only)
        """
        if not phone:
            return ""
        return "".join(filter(str.isdigit, phone))

    def _normalize_website(self, website: str | None) -> str:
        """
        Normalize website URL for comparison

        Args:
            website: Website URL

        Returns:
            Normalized domain (without protocol, www, trailing slash)
        """
        if not website:
            return ""

        # Remove protocol
        url = website.lower().replace("https://", "").replace("http://", "")

        # Remove www
        url = url.replace("www.", "")

        # Remove trailing slash
        url = url.rstrip("/")

        return url

    def find_duplicates(
        self, db: Session, company: Company, limit: int = 10
    ) -> list[tuple[Company, float]]:
        """
        Find potential duplicates for a company

        Args:
            db: Database session
            company: Company to check for duplicates
            limit: Maximum number of duplicates to return

        Returns:
            List of (duplicate_company, confidence_score) tuples, sorted by confidence
        """
        candidates = []

        # Strategy 1: Exact phone match
        if company.phone:
            phone_norm = self._normalize_phone(company.phone)
            if phone_norm:
                phone_matches = (
                    db.query(Company)
                    .filter(
                        and_(
                            Company.id != company.id,
                            Company.phone.isnot(None),
                        )
                    )
                    .all()
                )

                for match in phone_matches:
                    if self._normalize_phone(match.phone) == phone_norm:
                        candidates.append((match, 1.0))  # 100% confidence

        # Strategy 2: Exact website match
        if company.website:
            website_norm = self._normalize_website(company.website)
            if website_norm:
                website_matches = (
                    db.query(Company)
                    .filter(
                        and_(
                            Company.id != company.id,
                            Company.website.isnot(None),
                        )
                    )
                    .all()
                )

                for match in website_matches:
                    if self._normalize_website(match.website) == website_norm:
                        # Check if not already added
                        if not any(c.id == match.id for c, _ in candidates):
                            candidates.append((match, 0.95))  # 95% confidence

        # Strategy 3: Name + City similarity
        if company.company_name and company.city:
            city_norm = self._normalize_string(company.city)

            # Get companies in same city
            city_matches = (
                db.query(Company)
                .filter(
                    and_(
                        Company.id != company.id,
                        Company.city.isnot(None),
                    )
                )
                .all()
            )

            for match in city_matches:
                # Skip if already added
                if any(c.id == match.id for c, _ in candidates):
                    continue

                # Check city similarity
                if self._normalize_string(match.city) != city_norm:
                    continue

                # Calculate name similarity
                name_sim = self._calculate_similarity(company.company_name, match.company_name)

                if name_sim >= self.name_similarity_threshold:
                    # Boost confidence if address also matches
                    confidence = name_sim
                    if company.street and match.street:
                        street_sim = self._calculate_similarity(company.street, match.street)
                        if street_sim > 0.8:
                            confidence = min(1.0, confidence + 0.1)

                    candidates.append((match, confidence))

        # Sort by confidence (highest first) and limit
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:limit]

    def merge_companies(self, db: Session, primary: Company, duplicate: Company) -> Company:
        """
        Merge duplicate company into primary company

        Strategy: Keep primary company, fill in missing fields from duplicate

        Args:
            db: Database session
            primary: Primary company to keep
            duplicate: Duplicate company to merge and delete

        Returns:
            Updated primary company
        """
        logger.info(f"Merging companies: primary_id={primary.id}, duplicate_id={duplicate.id}")

        # Merge fields - fill in missing data from duplicate
        fields_to_merge = [
            "email",
            "phone",
            "website",
            "street",
            "postal_code",
            "city",
            "state",
            "country",
            "industry",
            "description",
            "team_size",
            "revenue",
            "founded_year",
            "technologies",
            "directors",
            "social_media",
        ]

        merged_count = 0
        for field in fields_to_merge:
            primary_value = getattr(primary, field)
            duplicate_value = getattr(duplicate, field)

            # If primary is missing but duplicate has value, use duplicate
            if not primary_value and duplicate_value:
                setattr(primary, field, duplicate_value)
                merged_count += 1
                logger.debug(f"Merged field '{field}' from duplicate to primary: {duplicate_value}")

        # Keep better lead score
        if duplicate.lead_score and (
            not primary.lead_score or duplicate.lead_score > primary.lead_score
        ):
            primary.lead_score = duplicate.lead_score
            primary.lead_quality = duplicate.lead_quality
            merged_count += 1

        # Delete duplicate
        db.delete(duplicate)
        db.commit()
        db.refresh(primary)

        logger.info(
            f"Successfully merged companies: merged_fields={merged_count}, "
            f"primary_id={primary.id}, deleted_duplicate_id={duplicate.id}"
        )

        return primary

    def deduplicate_all(
        self, db: Session, auto_merge_threshold: float = 0.95, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Find and merge all duplicates in database

        Args:
            db: Database session
            auto_merge_threshold: Confidence threshold for automatic merging
            dry_run: If True, only report duplicates without merging

        Returns:
            Statistics about deduplication process
        """
        logger.info(
            f"Starting deduplication: auto_merge_threshold={auto_merge_threshold}, "
            f"dry_run={dry_run}"
        )

        all_companies = db.query(Company).all()
        total_companies = len(all_companies)

        duplicates_found = 0
        auto_merged = 0
        manual_review = []
        processed_ids = set()

        for company in all_companies:
            # Skip if already processed as duplicate
            if company.id in processed_ids:
                continue

            # Find duplicates
            duplicates = self.find_duplicates(db, company)

            if duplicates:
                duplicates_found += len(duplicates)

                for duplicate, confidence in duplicates:
                    # Skip if already processed
                    if duplicate.id in processed_ids:
                        continue

                    if confidence >= auto_merge_threshold:
                        if not dry_run:
                            self.merge_companies(db, company, duplicate)
                            processed_ids.add(duplicate.id)
                        auto_merged += 1
                    else:
                        manual_review.append(
                            {
                                "primary_id": company.id,
                                "primary_name": company.company_name,
                                "duplicate_id": duplicate.id,
                                "duplicate_name": duplicate.company_name,
                                "confidence": confidence,
                            }
                        )

        result = {
            "total_companies": total_companies,
            "duplicates_found": duplicates_found,
            "auto_merged": auto_merged,
            "manual_review_count": len(manual_review),
            "manual_review": manual_review[:20],  # Limit to first 20
            "dry_run": dry_run,
        }

        logger.info(
            f"Deduplication completed: total={total_companies}, "
            f"duplicates={duplicates_found}, auto_merged={auto_merged}, "
            f"manual_review={len(manual_review)}"
        )

        return result


# Global deduplicator instance
deduplicator = CompanyDeduplicator()
