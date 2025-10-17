"""
Data Validator
Validates and cleans scraped data
"""

import logging
import re
from typing import Any
from urllib.parse import urlparse

import phonenumbers
from email_validator import EmailNotValidError, validate_email

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Validates and cleans scraped company data
    """

    @staticmethod
    def validate_email(email: str | None) -> str | None:
        """
        Validates and normalizes email address

        Args:
            email: Email address to validate

        Returns:
            Normalized email or None if invalid
        """
        if not email:
            return None

        # Clean email
        email = email.strip().lower()

        # Remove common prefixes
        email = re.sub(r"^(mailto:|email:)", "", email, flags=re.IGNORECASE)

        try:
            # Validate with email-validator
            valid = validate_email(email, check_deliverability=False)
            return valid.normalized
        except EmailNotValidError as e:
            logger.debug(f"Invalid email '{email}': {e}")
            return None

    @staticmethod
    def validate_phone(phone: str | None, country: str = "DE") -> str | None:
        """
        Validates and normalizes phone number

        Args:
            phone: Phone number to validate
            country: Country code (default: DE for Germany)

        Returns:
            Normalized phone number or None if invalid
        """
        if not phone:
            return None

        # Clean phone
        phone = phone.strip()

        # Remove common prefixes
        phone = re.sub(r"^(tel:|phone:|telefon:)", "", phone, flags=re.IGNORECASE)

        try:
            # Parse with phonenumbers
            parsed = phonenumbers.parse(phone, country)

            # Validate
            if phonenumbers.is_valid_number(parsed):
                # Format as international
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
            else:
                logger.debug(f"Invalid phone number: {phone}")
                return None

        except phonenumbers.NumberParseException as e:
            logger.debug(f"Could not parse phone '{phone}': {e}")
            return None

    @staticmethod
    def validate_website(website: str | None) -> str | None:
        """
        Validates and normalizes website URL

        Args:
            website: Website URL to validate

        Returns:
            Normalized URL or None if invalid
        """
        if not website:
            return None

        # Clean URL
        website = website.strip()

        # Add scheme if missing
        if not website.startswith(("http://", "https://")):
            website = "https://" + website

        try:
            # Parse URL
            parsed = urlparse(website)

            # Validate
            if not parsed.netloc:
                return None

            # Reconstruct clean URL
            scheme = parsed.scheme or "https"
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip("/")

            clean_url = f"{scheme}://{netloc}{path}"

            return clean_url

        except Exception as e:
            logger.debug(f"Invalid URL '{website}': {e}")
            return None

    @staticmethod
    def validate_postal_code(postal_code: str | None, country: str = "DE") -> str | None:
        """
        Validates postal code

        Args:
            postal_code: Postal code to validate
            country: Country code

        Returns:
            Cleaned postal code or None if invalid
        """
        if not postal_code:
            return None

        # Clean
        postal_code = postal_code.strip()

        # Germany: 5 digits
        if country == "DE":
            # Extract digits
            digits = re.sub(r"\D", "", postal_code)

            if len(digits) == 5:
                return digits

        return postal_code if postal_code else None

    @staticmethod
    def validate_company_name(name: str | None) -> str | None:
        """
        Validates and cleans company name

        Args:
            name: Company name

        Returns:
            Cleaned name or None if invalid
        """
        if not name:
            return None

        # Clean
        name = name.strip()

        # Remove multiple spaces
        name = re.sub(r"\s+", " ", name)

        # Minimum length
        if len(name) < 2:
            return None

        return name

    @classmethod
    def validate_company_data(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validates all company data fields

        Args:
            data: Company data dictionary

        Returns:
            Validated and cleaned data
        """
        validated = {}

        # Company name (required)
        validated["company_name"] = cls.validate_company_name(data.get("company_name"))

        if not validated["company_name"]:
            raise ValueError("Company name is required and invalid")

        # Email
        if "email" in data:
            validated["email"] = cls.validate_email(data["email"])

        # Phone
        if "phone" in data:
            validated["phone"] = cls.validate_phone(data["phone"])

        # Website
        if "website" in data:
            validated["website"] = cls.validate_website(data["website"])

        # Postal code
        if "postal_code" in data:
            validated["postal_code"] = cls.validate_postal_code(data["postal_code"])

        # Copy other fields
        for key in ["city", "address", "description", "industry", "legal_form"]:
            if key in data and data[key]:
                validated[key] = str(data[key]).strip()

        return validated


# Convenience function
def validate_company(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validates company data

    Args:
        data: Company data dictionary

    Returns:
        Validated data
    """
    validator = DataValidator()
    return validator.validate_company_data(data)
