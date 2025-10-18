"""
Lead Scoring Algorithm
Bewertet Leads automatisch basierend auf verschiedenen Faktoren
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class LeadScorer:
    """
    Intelligenter Lead Scoring Algorithmus

    Scoring Faktoren:
    - Kontaktdaten Vollständigkeit (0-30 Punkte)
    - Website Qualität (0-20 Punkte)
    - Branche/Industry (0-15 Punkte)
    - Firmengröße (0-15 Punkte)
    - Technologie Stack (0-10 Punkte)
    - Datenqualität (0-10 Punkte)

    Max Score: 100 Punkte

    Kategorien:
    - 80-100: Hot Lead (Sehr hohe Priorität)
    - 60-79:  Warm Lead (Hohe Priorität)
    - 40-59:  Cold Lead (Mittlere Priorität)
    - 0-39:   Low Quality (Niedrige Priorität)
    """

    # Hochwertige Branchen (höhere Scores)
    HIGH_VALUE_INDUSTRIES = {
        "software",
        "it",
        "tech",
        "saas",
        "cloud",
        "ai",
        "ml",
        "consulting",
        "beratung",
        "engineering",
        "automation",
        "fintech",
        "medtech",
        "healthtech",
        "e-commerce",
    }

    # Technologien die auf moderne Firmen hindeuten
    MODERN_TECHNOLOGIES = {
        "react",
        "vue",
        "angular",
        "node",
        "python",
        "aws",
        "azure",
        "kubernetes",
        "docker",
        "microservices",
        "api",
        "rest",
        "graphql",
        "mongodb",
        "postgresql",
        "redis",
        "kafka",
    }

    def __init__(self):
        """Initialisiert Lead Scorer"""
        self.stats = {
            "total_scored": 0,
            "hot_leads": 0,
            "warm_leads": 0,
            "cold_leads": 0,
            "low_quality": 0,
        }

    def score_lead(self, company_data: dict[str, Any]) -> dict[str, Any]:
        """
        Bewertet einen Lead und gibt Score + Kategorie zurück

        Args:
            company_data: Company Daten Dictionary

        Returns:
            {
                "score": 75,
                "quality": "warm",
                "breakdown": {...},
                "recommendations": [...]
            }
        """
        score = 0
        breakdown = {}
        recommendations = []

        # 1. Kontaktdaten Vollständigkeit (0-30 Punkte)
        contact_score, contact_breakdown = self._score_contact_data(company_data)
        score += contact_score
        breakdown["contact_data"] = contact_breakdown

        if contact_score < 20:
            recommendations.append("Kontaktdaten vervollständigen (Email, Telefon)")

        # 2. Website Qualität (0-20 Punkte)
        website_score, website_breakdown = self._score_website(company_data)
        score += website_score
        breakdown["website"] = website_breakdown

        if website_score < 10:
            recommendations.append("Website-Informationen überprüfen")

        # 3. Branche/Industry (0-15 Punkte)
        industry_score, industry_breakdown = self._score_industry(company_data)
        score += industry_score
        breakdown["industry"] = industry_breakdown

        # 4. Firmengröße (0-15 Punkte)
        size_score, size_breakdown = self._score_company_size(company_data)
        score += size_score
        breakdown["company_size"] = size_breakdown

        # 5. Technologie Stack (0-10 Punkte)
        tech_score, tech_breakdown = self._score_technologies(company_data)
        score += tech_score
        breakdown["technologies"] = tech_breakdown

        # 6. Datenqualität (0-10 Punkte)
        quality_score, quality_breakdown = self._score_data_quality(company_data)
        score += quality_score
        breakdown["data_quality"] = quality_breakdown

        if quality_score < 5:
            recommendations.append("Datenqualität verbessern (Duplikate, Validierung)")

        # Qualitätskategorie bestimmen
        quality = self._get_quality_category(score)

        # Statistiken updaten
        self.stats["total_scored"] += 1
        quality_key = quality.replace("_", "_")  # low_quality bleibt low_quality
        if f"{quality}_leads" in self.stats:
            self.stats[f"{quality}_leads"] += 1
        else:
            self.stats["low_quality"] += 1

        logger.info(
            f"Lead scored: {company_data.get('name', 'Unknown')} - Score: {score} ({quality})"
        )

        return {
            "score": score,
            "quality": quality,
            "breakdown": breakdown,
            "recommendations": recommendations,
        }

    def _score_contact_data(self, data: dict[str, Any]) -> tuple[int, dict]:
        """Bewertet Kontaktdaten Vollständigkeit (0-30 Punkte)"""
        score = 0
        breakdown = {}

        # Email (10 Punkte)
        if data.get("email") or data.get("contact_email"):
            email = data.get("email") or data.get("contact_email")
            if self._is_valid_email(email):
                score += 10
                breakdown["email"] = "valid"
            else:
                score += 5
                breakdown["email"] = "invalid"
        else:
            breakdown["email"] = "missing"

        # Telefon (10 Punkte)
        if data.get("phone") or data.get("contact_phone"):
            phone = data.get("phone") or data.get("contact_phone")
            if self._is_valid_phone(phone):
                score += 10
                breakdown["phone"] = "valid"
            else:
                score += 5
                breakdown["phone"] = "invalid"
        else:
            breakdown["phone"] = "missing"

        # Adresse (5 Punkte)
        if data.get("address") or (data.get("street") and data.get("city")):
            score += 5
            breakdown["address"] = "present"
        else:
            breakdown["address"] = "missing"

        # Ansprechpartner/Directors (5 Punkte)
        if data.get("directors") and len(data.get("directors", [])) > 0:
            score += 5
            breakdown["directors"] = f"{len(data['directors'])} found"
        else:
            breakdown["directors"] = "missing"

        return score, breakdown

    def _score_website(self, data: dict[str, Any]) -> tuple[int, dict]:
        """Bewertet Website Qualität (0-20 Punkte)"""
        score = 0
        breakdown = {}

        website = data.get("website") or data.get("source_url")

        if not website:
            breakdown["status"] = "missing"
            return 0, breakdown

        # Website vorhanden (10 Punkte)
        score += 10
        breakdown["status"] = "present"

        # HTTPS (5 Punkte)
        if website.startswith("https://"):
            score += 5
            breakdown["https"] = True
        else:
            breakdown["https"] = False

        # Eigene Domain (nicht Social Media) (5 Punkte)
        social_domains = ["facebook", "linkedin", "twitter", "instagram", "xing"]
        if not any(domain in website.lower() for domain in social_domains):
            score += 5
            breakdown["own_domain"] = True
        else:
            breakdown["own_domain"] = False

        return score, breakdown

    def _score_industry(self, data: dict[str, Any]) -> tuple[int, dict]:
        """Bewertet Branche/Industry (0-15 Punkte)"""
        score = 0
        breakdown = {}

        industry = data.get("industry", "").lower()

        if not industry:
            breakdown["status"] = "missing"
            return 0, breakdown

        # Industry vorhanden (5 Punkte)
        score += 5
        breakdown["status"] = "present"

        # Hochwertige Branche (10 Punkte)
        if any(keyword in industry for keyword in self.HIGH_VALUE_INDUSTRIES):
            score += 10
            breakdown["high_value"] = True
        else:
            breakdown["high_value"] = False

        return score, breakdown

    def _score_company_size(self, data: dict[str, Any]) -> tuple[int, dict]:
        """Bewertet Firmengröße (0-15 Punkte)"""
        score = 0
        breakdown = {}

        team_size = data.get("team_size")

        if not team_size:
            breakdown["status"] = "unknown"
            return 5, breakdown  # Default 5 Punkte

        try:
            size = int(team_size)

            if size >= 100:
                score = 15  # Großunternehmen
                breakdown["category"] = "large"
            elif size >= 50:
                score = 12  # Mittelstand
                breakdown["category"] = "medium"
            elif size >= 10:
                score = 10  # Kleinunternehmen
                breakdown["category"] = "small"
            else:
                score = 7  # Sehr klein
                breakdown["category"] = "micro"

            breakdown["size"] = size

        except (ValueError, TypeError):
            score = 5
            breakdown["status"] = "invalid"

        return score, breakdown

    def _score_technologies(self, data: dict[str, Any]) -> tuple[int, dict]:
        """Bewertet Technologie Stack (0-10 Punkte)"""
        score = 0
        breakdown = {}

        technologies = data.get("technologies", [])

        if not technologies:
            breakdown["status"] = "missing"
            return 0, breakdown

        # Technologien vorhanden (5 Punkte)
        score += 5
        breakdown["count"] = len(technologies)

        # Moderne Technologien (5 Punkte)
        modern_tech_count = sum(
            1
            for tech in technologies
            if any(keyword in tech.lower() for keyword in self.MODERN_TECHNOLOGIES)
        )

        if modern_tech_count > 0:
            score += min(5, modern_tech_count * 2)  # Max 5 Punkte
            breakdown["modern_count"] = modern_tech_count

        return score, breakdown

    def _score_data_quality(self, data: dict[str, Any]) -> tuple[int, dict]:
        """Bewertet Datenqualität (0-10 Punkte)"""
        score = 10  # Start mit vollen Punkten
        breakdown = {}
        issues = []

        # Firmenname vorhanden und valide (kritisch)
        name = data.get("name") or data.get("company_name")
        if not name or len(name) < 3:
            score -= 5
            issues.append("invalid_name")

        # Keine offensichtlichen Fehler in Daten
        if data.get("error"):
            score -= 3
            issues.append("has_errors")

        # Mindestens 3 Felder ausgefüllt
        filled_fields = sum(1 for v in data.values() if v and v != "null")
        if filled_fields < 3:
            score -= 2
            issues.append("incomplete_data")

        breakdown["issues"] = issues
        breakdown["filled_fields"] = filled_fields

        return max(0, score), breakdown

    def _get_quality_category(self, score: int) -> str:
        """Bestimmt Qualitätskategorie basierend auf Score"""
        if score >= 80:
            return "hot"
        elif score >= 60:
            return "warm"
        elif score >= 40:
            return "cold"
        else:
            return "low_quality"

    def _is_valid_email(self, email: str) -> bool:
        """Validiert Email Format"""
        if not email:
            return False
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _is_valid_phone(self, phone: str) -> bool:
        """Validiert Telefonnummer (einfache Prüfung)"""
        if not phone:
            return False
        # Mindestens 6 Ziffern
        digits = re.sub(r"\D", "", phone)
        return len(digits) >= 6

    def get_stats(self) -> dict[str, int]:
        """Gibt Scoring Statistiken zurück"""
        return self.stats.copy()


# Convenience Function
def score_company(company_data: dict[str, Any]) -> dict[str, Any]:
    """
    Convenience Function für schnelles Lead Scoring

    Args:
        company_data: Company Daten Dictionary

    Returns:
        Scoring Result mit score, quality, breakdown, recommendations
    """
    scorer = LeadScorer()
    return scorer.score_lead(company_data)
