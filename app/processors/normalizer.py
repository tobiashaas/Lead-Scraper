"""
Data Normalizer
Normalizes and standardizes scraped data
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Normalizes company data to consistent format
    """

    # Legal form mappings
    LEGAL_FORMS = {
        "gmbh": "GmbH",
        "ug": "UG",
        "ag": "AG",
        "kg": "KG",
        "ohg": "OHG",
        "gbr": "GbR",
        "ev": "e.V.",
        "eg": "eG",
        "einzelunternehmen": "Einzelunternehmen",
        "freiberufler": "Freiberufler",
    }

    # State mappings (Bundesländer)
    STATES = {
        "bw": "Baden-Württemberg",
        "baden-württemberg": "Baden-Württemberg",
        "baden württemberg": "Baden-Württemberg",
        "by": "Bayern",
        "bayern": "Bayern",
        "be": "Berlin",
        "berlin": "Berlin",
        "bb": "Brandenburg",
        "brandenburg": "Brandenburg",
        "hb": "Bremen",
        "bremen": "Bremen",
        "hh": "Hamburg",
        "hamburg": "Hamburg",
        "he": "Hessen",
        "hessen": "Hessen",
        "mv": "Mecklenburg-Vorpommern",
        "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
        "ni": "Niedersachsen",
        "niedersachsen": "Niedersachsen",
        "nw": "Nordrhein-Westfalen",
        "nordrhein-westfalen": "Nordrhein-Westfalen",
        "rp": "Rheinland-Pfalz",
        "rheinland-pfalz": "Rheinland-Pfalz",
        "sl": "Saarland",
        "saarland": "Saarland",
        "sn": "Sachsen",
        "sachsen": "Sachsen",
        "st": "Sachsen-Anhalt",
        "sachsen-anhalt": "Sachsen-Anhalt",
        "sh": "Schleswig-Holstein",
        "schleswig-holstein": "Schleswig-Holstein",
        "th": "Thüringen",
        "thüringen": "Thüringen",
    }

    @staticmethod
    def normalize_company_name(name: str) -> str:
        """
        Normalize company name

        Args:
            name: Company name

        Returns:
            Normalized name
        """
        if not name:
            return name

        # Remove extra whitespace
        name = re.sub(r"\s+", " ", name.strip())

        # Capitalize properly
        # Keep existing capitalization for acronyms
        words = name.split()
        normalized = []

        for word in words:
            # Keep if all uppercase (likely acronym)
            if word.isupper() and len(word) > 1:
                normalized.append(word)
            # Keep if mixed case (likely intentional)
            elif any(c.isupper() for c in word[1:]):
                normalized.append(word)
            # Otherwise title case
            else:
                normalized.append(word.capitalize())

        return " ".join(normalized)

    @classmethod
    def normalize_legal_form(cls, legal_form: str | None) -> str | None:
        """
        Normalize legal form

        Args:
            legal_form: Legal form string

        Returns:
            Normalized legal form
        """
        if not legal_form:
            return None

        # Clean
        legal_form = legal_form.strip().lower()

        # Remove common prefixes/suffixes
        legal_form = re.sub(r"(^rechtsform:?\s*|\s*\(.*\)$)", "", legal_form)

        # Map to standard form
        for key, value in cls.LEGAL_FORMS.items():
            if key in legal_form:
                return value

        # Return capitalized if no match
        return legal_form.upper()

    @classmethod
    def normalize_state(cls, state: str | None) -> str | None:
        """
        Normalize state/Bundesland

        Args:
            state: State name or abbreviation

        Returns:
            Normalized state name
        """
        if not state:
            return None

        # Clean
        state = state.strip().lower()

        # Map to full name
        return cls.STATES.get(state, state.title())

    @staticmethod
    def normalize_city(city: str | None) -> str | None:
        """
        Normalize city name

        Args:
            city: City name

        Returns:
            Normalized city
        """
        if not city:
            return None

        # Remove extra whitespace
        city = re.sub(r"\s+", " ", city.strip())

        # Title case
        return city.title()

    @staticmethod
    def normalize_list_field(items: list[str] | None) -> list[str] | None:
        """
        Normalize list field (directors, services, etc.)

        Args:
            items: List of strings

        Returns:
            Normalized list
        """
        if not items:
            return None

        # Remove empty strings and duplicates
        normalized = []
        seen = set()

        for item in items:
            if not item:
                continue

            # Clean
            item = item.strip()

            # Remove duplicates (case-insensitive)
            item_lower = item.lower()
            if item_lower not in seen:
                normalized.append(item)
                seen.add(item_lower)

        return normalized if normalized else None

    @staticmethod
    def extract_legal_form_from_name(name: str) -> tuple[str, str | None]:
        """
        Extract legal form from company name

        Args:
            name: Company name

        Returns:
            Tuple of (cleaned_name, legal_form)
        """
        if not name:
            return name, None

        # Common patterns
        patterns = [
            r"\s+(GmbH|UG|AG|KG|OHG|GbR|e\.V\.|eG)(\s+&\s+Co\.?\s+KG)?$",
            r"\s+\((GmbH|UG|AG|KG|OHG|GbR|e\.V\.|eG)\)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                legal_form = match.group(0).strip()
                cleaned_name = name[: match.start()].strip()
                return cleaned_name, legal_form

        return name, None

    @classmethod
    def normalize_company_data(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize all company data fields

        Args:
            data: Company data dictionary

        Returns:
            Normalized data
        """
        normalized = data.copy()

        # Company name
        if "company_name" in normalized:
            name = normalized["company_name"]

            # Extract legal form if embedded
            if not normalized.get("legal_form"):
                name, legal_form = cls.extract_legal_form_from_name(name)
                if legal_form:
                    normalized["legal_form"] = legal_form

            normalized["company_name"] = cls.normalize_company_name(name)

        # Legal form
        if "legal_form" in normalized:
            normalized["legal_form"] = cls.normalize_legal_form(normalized["legal_form"])

        # City
        if "city" in normalized:
            normalized["city"] = cls.normalize_city(normalized["city"])

        # State
        if "state" in normalized:
            normalized["state"] = cls.normalize_state(normalized["state"])

        # List fields
        for field in ["directors", "services", "technologies"]:
            if field in normalized:
                normalized[field] = cls.normalize_list_field(normalized[field])

        # Description (trim)
        if "description" in normalized and normalized["description"]:
            desc = normalized["description"].strip()
            # Limit length
            if len(desc) > 1000:
                desc = desc[:997] + "..."
            normalized["description"] = desc

        return normalized


# Convenience function
def normalize_company(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize company data

    Args:
        data: Company data dictionary

    Returns:
        Normalized data
    """
    normalizer = DataNormalizer()
    return normalizer.normalize_company_data(data)
