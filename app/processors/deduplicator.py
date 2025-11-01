"""
Deduplicator
Finds and merges duplicate companies using fuzzy matching
"""

import logging

from fuzzywuzzy import fuzz
from sqlalchemy.orm import Session

from app.database.models import Company, DuplicateCandidate

logger = logging.getLogger(__name__)


class Deduplicator:
    """
    Finds and handles duplicate companies
    """

    def __init__(
        self,
        name_threshold: int = 85,
        address_threshold: int = 80,
        phone_threshold: int = 90,
        website_threshold: int = 95,
        overall_threshold: int = 80,
    ):
        """
        Initialize deduplicator

        Args:
            name_threshold: Minimum similarity for company names (0-100)
            address_threshold: Minimum similarity for addresses
            phone_threshold: Minimum similarity for phone numbers
            website_threshold: Minimum similarity for websites
            overall_threshold: Minimum overall similarity to flag as duplicate
        """
        self.name_threshold = name_threshold
        self.address_threshold = address_threshold
        self.phone_threshold = phone_threshold
        self.website_threshold = website_threshold
        self.overall_threshold = overall_threshold

    def calculate_similarity(
        self, company_a: Company, company_b: Company
    ) -> tuple[float, float, float, float, float]:
        """
        Calculate similarity scores between two companies

        Args:
            company_a: First company
            company_b: Second company

        Returns:
            Tuple of (name_sim, address_sim, phone_sim, website_sim, overall_sim)
        """
        # Name similarity (required)
        name_sim = fuzz.token_sort_ratio(
            company_a.company_name.lower(), company_b.company_name.lower()
        )

        # Address similarity
        address_sim = 0.0
        if company_a.address and company_b.address:
            address_sim = fuzz.token_sort_ratio(
                company_a.address.lower(), company_b.address.lower()
            )

        # Phone similarity
        phone_sim = 0.0
        if company_a.phone and company_b.phone:
            # Remove all non-digits for comparison
            phone_a = "".join(filter(str.isdigit, company_a.phone))
            phone_b = "".join(filter(str.isdigit, company_b.phone))
            if phone_a and phone_b:
                phone_sim = fuzz.ratio(phone_a, phone_b)

        # Website similarity
        website_sim = 0.0
        if company_a.website and company_b.website:
            website_sim = fuzz.ratio(company_a.website.lower(), company_b.website.lower())

        # Overall similarity (weighted average)
        weights = {"name": 0.4, "address": 0.2, "phone": 0.2, "website": 0.2}

        overall_sim = (
            weights["name"] * name_sim
            + weights["address"] * address_sim
            + weights["phone"] * phone_sim
            + weights["website"] * website_sim
        )

        return name_sim, address_sim, phone_sim, website_sim, overall_sim

    def is_duplicate(self, company_a: Company, company_b: Company) -> bool:
        """
        Check if two companies are duplicates

        Args:
            company_a: First company
            company_b: Second company

        Returns:
            True if companies are likely duplicates
        """
        name_sim, address_sim, phone_sim, website_sim, overall_sim = self.calculate_similarity(
            company_a, company_b
        )

        # High confidence duplicate if:
        # 1. Name is very similar AND
        # 2. At least one other field matches well OR overall score is high

        if name_sim >= self.name_threshold:
            if (
                address_sim >= self.address_threshold
                or phone_sim >= self.phone_threshold
                or website_sim >= self.website_threshold
                or overall_sim >= self.overall_threshold
            ):
                return True

        return False

    def find_duplicates(
        self, db: Session, company: Company, limit: int = 10
    ) -> list[tuple[Company, float]]:
        """
        Find potential duplicates for a company

        Args:
            db: Database session
            company: Company to check
            limit: Maximum number of candidates to return

        Returns:
            List of (candidate_company, similarity_score) tuples
        """
        # Query similar companies (same city, similar name)
        candidates = (
            db.query(Company)
            .filter(Company.id != company.id, Company.is_active, Company.city == company.city)
            .all()
        )

        # Calculate similarities
        results = []
        for candidate in candidates:
            _, _, _, _, overall_sim = self.calculate_similarity(company, candidate)

            if overall_sim >= self.overall_threshold:
                results.append((candidate, overall_sim))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]

    def create_duplicate_candidate(
        self, db: Session, company_a: Company, company_b: Company
    ) -> DuplicateCandidate:
        """
        Create a duplicate candidate entry for manual review

        Args:
            db: Database session
            company_a: First company
            company_b: Second company

        Returns:
            Created DuplicateCandidate
        """
        # Check if already exists
        existing = (
            db.query(DuplicateCandidate)
            .filter(
                (
                    (DuplicateCandidate.company_a_id == company_a.id)
                    & (DuplicateCandidate.company_b_id == company_b.id)
                )
                | (
                    (DuplicateCandidate.company_a_id == company_b.id)
                    & (DuplicateCandidate.company_b_id == company_a.id)
                )
            )
            .first()
        )

        if existing is not None:
            return existing

        # Calculate similarities
        name_sim, address_sim, phone_sim, website_sim, overall_sim = self.calculate_similarity(
            company_a, company_b
        )

        # Create candidate
        candidate = DuplicateCandidate(
            company_a_id=company_a.id,
            company_b_id=company_b.id,
            name_similarity=name_sim / 100.0,
            address_similarity=address_sim / 100.0,
            phone_similarity=phone_sim / 100.0,
            website_similarity=website_sim / 100.0,
            overall_similarity=overall_sim / 100.0,
            status="pending",
        )

        db.add(candidate)
        db.flush()

        logger.info(
            f"Created duplicate candidate: {company_a.company_name} <-> "
            f"{company_b.company_name} (similarity: {overall_sim:.1f}%)"
        )

        return candidate

    def merge_companies(self, db: Session, primary: Company, duplicate: Company) -> Company:
        """
        Merge duplicate company into primary

        Args:
            db: Database session
            primary: Primary company (keep)
            duplicate: Duplicate company (merge and deactivate)

        Returns:
            Updated primary company
        """
        logger.info(f"Merging {duplicate.company_name} into {primary.company_name}")

        # Merge fields (prefer non-null values from duplicate)
        merge_fields = [
            "email",
            "phone",
            "website",
            "address",
            "description",
            "legal_form",
            "industry",
            "directors",
            "services",
            "technologies",
        ]

        for field in merge_fields:
            primary_value = getattr(primary, field)
            duplicate_value = getattr(duplicate, field)

            # Use duplicate value if primary is empty
            if not primary_value and duplicate_value:
                setattr(primary, field, duplicate_value)

        # Merge extra_data
        if duplicate.extra_data:
            if not primary.extra_data:
                primary.extra_data = {}

            # Merge sources
            if "sources" in duplicate.extra_data:
                if "sources" not in primary.extra_data:
                    primary.extra_data["sources"] = []

                primary.extra_data["sources"].extend(duplicate.extra_data["sources"])

        # Mark duplicate as inactive
        duplicate.is_active = False
        duplicate.is_duplicate = True
        duplicate.duplicate_of_id = primary.id

        db.flush()

        logger.info("✅ Merge completed")

        return primary

    def scan_for_duplicates(self, db: Session, batch_size: int = 100) -> int:
        """
        Scan all companies for duplicates using batched processing

        Args:
            db: Database session
            batch_size: Number of companies to process per batch

        Returns:
            Number of duplicate candidates created
        """
        logger.info("Starting duplicate scan...")

        # Get total count
        total = db.query(Company).filter(Company.is_active).count()
        candidates_created = 0
        offset = 0

        logger.info(f"Scanning {total} companies in batches of {batch_size}...")

        # Process in batches using offset/limit
        while offset < total:
            # Fetch batch
            batch = (
                db.query(Company)
                .filter(Company.is_active)
                .order_by(Company.id)
                .limit(batch_size)
                .offset(offset)
                .all()
            )

            if not batch:
                break

            # Process each company in batch
            for company in batch:
                # Find duplicates
                duplicates = self.find_duplicates(db, company, limit=5)

                # Create candidates
                for duplicate, _similarity in duplicates:
                    self.create_duplicate_candidate(db, company, duplicate)
                    candidates_created += 1

            # Flush after each batch
            db.flush()

            offset += batch_size
            logger.info(f"Progress: {offset}/{total} companies scanned, {candidates_created} candidates created")

        logger.info(f"✅ Scan completed: {candidates_created} duplicate candidates found")

        return candidates_created


# Convenience functions
def find_duplicates(db: Session, company: Company) -> list[tuple[Company, float]]:
    """Find duplicates for a company"""
    dedup = Deduplicator()
    return dedup.find_duplicates(db, company)


def merge_companies(db: Session, primary: Company, duplicate: Company) -> Company:
    """Merge duplicate into primary"""
    dedup = Deduplicator()
    return dedup.merge_companies(db, primary, duplicate)
