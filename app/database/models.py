"""
SQLAlchemy Database Models
Definiert die Datenbankstruktur für Lead-Scraping
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class für alle Models"""

    pass


# Association Table für Many-to-Many: Company <-> Source
company_sources = Table(
    "company_sources",
    Base.metadata,
    Column("company_id", Integer, ForeignKey("companies.id"), primary_key=True),
    Column("source_id", Integer, ForeignKey("sources.id"), primary_key=True),
    Column("created_at", DateTime, default=lambda: datetime.now(UTC)),
)


class LeadStatus(enum.Enum):
    """Lead Status"""

    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    REJECTED = "rejected"


class LeadQuality(enum.Enum):
    """Lead Qualität"""

    A = "a"  # Sehr gut
    B = "b"  # Gut
    C = "c"  # Mittel
    D = "d"  # Niedrig
    UNKNOWN = "unknown"


class UserRole(enum.Enum):
    """User Rollen"""

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class Company(Base):
    """
    Unternehmen (Lead)
    Zentrale Tabelle für alle gescrapten Unternehmen
    """

    __tablename__ = "companies"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Basis-Informationen
    company_name = Column(String(255), nullable=False, index=True)
    legal_form = Column(String(50))  # GmbH, AG, UG, etc.
    industry = Column(String(100), index=True)
    description = Column(Text)

    # Kontaktdaten
    website = Column(String(500), index=True)
    email = Column(String(255), index=True)
    phone = Column(String(50))

    # Adresse
    address = Column(String(500))
    street = Column(String(255))
    postal_code = Column(String(20), index=True)
    city = Column(String(100), index=True)
    state = Column(String(100))  # Bundesland
    country = Column(String(100), default="Deutschland")

    # Geschäftsführung & Team
    directors = Column(JSON)  # Liste von Geschäftsführern
    team_size = Column(Integer)  # Geschätzte Mitarbeiterzahl
    team_members = Column(JSON)  # Liste von Team-Mitgliedern

    # Services & Technologien
    services = Column(JSON)  # Liste von Dienstleistungen
    technologies = Column(JSON)  # Liste von Technologien

    # Google Places Daten
    google_place_id = Column(String(255), unique=True, index=True)
    google_rating = Column(Float)
    google_reviews_count = Column(Integer)
    google_opening_hours = Column(JSON)

    # Handelsregister
    register_number = Column(String(100), index=True)
    register_court = Column(String(100))
    register_data = Column(JSON)

    # Lead Scoring & Status
    lead_status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW, index=True)
    lead_quality = Column(SQLEnum(LeadQuality), default=LeadQuality.UNKNOWN, index=True)
    lead_score = Column(Float, default=0.0)  # 0-100

    # Metadaten
    first_scraped_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_contacted_at = Column(DateTime)

    # Flags
    is_active = Column(Boolean, default=True, index=True)
    is_duplicate = Column(Boolean, default=False, index=True)
    duplicate_of_id = Column(Integer, ForeignKey("companies.id"))

    # Zusätzliche Daten (flexibel)
    extra_data = Column(JSON)

    # Relationships
    sources = relationship("Source", secondary=company_sources, back_populates="companies")
    scraping_jobs = relationship("ScrapingJob", back_populates="company")
    notes = relationship("CompanyNote", back_populates="company", cascade="all, delete-orphan")
    # Duplicate tracking relationships
    duplicate_of = relationship(
        "Company",
        remote_side=[id],
        foreign_keys=[duplicate_of_id],
    )
    duplicates = relationship(
        "Company",
        foreign_keys=[duplicate_of_id],
        back_populates="duplicate_of",
    )

    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.company_name}', city='{self.city}')>"


class Source(Base):
    """
    Datenquellen
    Trackt woher die Daten kommen (11880, Gelbe Seiten, etc.)
    """

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)

    # Source Informationen
    name = Column(
        String(100), nullable=False, unique=True, index=True
    )  # z.B. "11880", "gelbe_seiten"
    display_name = Column(String(255))  # z.B. "11880.com"
    url = Column(String(500))
    source_type = Column(String(50))  # "directory", "search_engine", "api", etc.

    # Metadaten
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Relationships
    companies = relationship("Company", secondary=company_sources, back_populates="sources")
    scraping_jobs = relationship("ScrapingJob", back_populates="source")

    def __repr__(self):
        return f"<Source(id={self.id}, name='{self.name}')>"


class ScrapingJob(Base):
    """
    Scraping Jobs
    Trackt alle Scraping-Durchläufe
    """

    __tablename__ = "scraping_jobs"

    id = Column(Integer, primary_key=True, index=True)

    # Job Informationen
    job_name = Column(String(255))
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"))

    # Parameter
    city = Column(String(100), index=True)
    industry = Column(String(100))
    search_query = Column(String(500))
    max_pages = Column(Integer)

    # Status
    status = Column(
        String(50), default="pending", index=True
    )  # pending, running, completed, failed
    progress = Column(Float, default=0.0)  # 0-100%

    # Ergebnisse
    results_count = Column(Integer, default=0)
    new_companies = Column(Integer, default=0)
    updated_companies = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    # Fehler
    error_message = Column(Text)

    # Metadaten
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    created_by = Column(String(100))  # User/System

    # Zusätzliche Daten
    config = Column(JSON)  # Job-Konfiguration
    stats = Column(JSON)  # Detaillierte Statistiken

    # Relationships
    source = relationship("Source", back_populates="scraping_jobs")
    company = relationship("Company", back_populates="scraping_jobs")

    def __repr__(self):
        return f"<ScrapingJob(id={self.id}, status='{self.status}', source='{self.source.name if self.source else None}')>"


class CompanyNote(Base):
    """
    Notizen zu Unternehmen
    Für manuelle Anmerkungen, Kontakthistorie, etc.
    """

    __tablename__ = "company_notes"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # Notiz
    title = Column(String(255))
    content = Column(Text, nullable=False)
    note_type = Column(String(50))  # "contact", "research", "general", etc.

    # Metadaten
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    created_by = Column(String(100))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(UTC))

    # Relationship
    company = relationship("Company", back_populates="notes")

    def __repr__(self):
        return f"<CompanyNote(id={self.id}, company_id={self.company_id})>"


class DuplicateCandidate(Base):
    """
    Duplikat-Kandidaten
    Für Fuzzy-Matching und manuelle Überprüfung
    """

    __tablename__ = "duplicate_candidates"

    id = Column(Integer, primary_key=True, index=True)

    # Unternehmen
    company_a_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    company_b_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # Similarity Scores
    name_similarity = Column(Float)  # 0-1
    address_similarity = Column(Float)
    phone_similarity = Column(Float)
    website_similarity = Column(Float)
    overall_similarity = Column(Float, index=True)

    # Status
    status = Column(String(50), default="pending", index=True)  # pending, confirmed, rejected
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    notes = Column(Text)

    # Metadaten
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Relationships
    company_a = relationship("Company", foreign_keys=[company_a_id])
    company_b = relationship("Company", foreign_keys=[company_b_id])

    def __repr__(self):
        return f"<DuplicateCandidate(id={self.id}, similarity={self.overall_similarity:.2f})>"


class User(Base):
    """
    User Model für Authentication
    """

    __tablename__ = "users"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # User Info
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255))

    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)

    # Security
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)

    # Metadaten
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role={self.role.value})>"
