"""Unit tests for DataNormalizer."""

import pytest

from app.processors.normalizer import DataNormalizer


class TestDataNormalizer:
    """Test suite for DataNormalizer."""

    def test_normalize_company_name_basic(self) -> None:
        assert DataNormalizer.normalize_company_name("test company") == "Test Company"
        # Keeps all uppercase (acronym)
        assert DataNormalizer.normalize_company_name("IBM COMPANY") == "IBM COMPANY"

    def test_normalize_company_name_with_whitespace(self) -> None:
        assert DataNormalizer.normalize_company_name("  test   company  ") == "Test Company"

    def test_normalize_company_name_empty(self) -> None:
        assert DataNormalizer.normalize_company_name("") == ""
        assert DataNormalizer.normalize_company_name(None) is None

    def test_normalize_legal_form_basic(self) -> None:
        assert DataNormalizer.normalize_legal_form("gmbh") == "GmbH"
        assert DataNormalizer.normalize_legal_form("ug") == "UG"
        assert DataNormalizer.normalize_legal_form("ag") == "AG"

    def test_normalize_legal_form_empty(self) -> None:
        assert DataNormalizer.normalize_legal_form("") is None
        assert DataNormalizer.normalize_legal_form(None) is None

    def test_normalize_city_basic(self) -> None:
        assert DataNormalizer.normalize_city("stuttgart") == "Stuttgart"
        assert DataNormalizer.normalize_city("BERLIN") == "Berlin"

    def test_normalize_city_empty(self) -> None:
        assert DataNormalizer.normalize_city("") is None
        assert DataNormalizer.normalize_city(None) is None

    def test_normalize_state_abbreviation(self) -> None:
        assert DataNormalizer.normalize_state("bw") == "Baden-Württemberg"
        assert DataNormalizer.normalize_state("by") == "Bayern"
        assert DataNormalizer.normalize_state("be") == "Berlin"

    def test_normalize_state_full_name(self) -> None:
        assert DataNormalizer.normalize_state("baden-württemberg") == "Baden-Württemberg"
        assert DataNormalizer.normalize_state("bayern") == "Bayern"

    def test_normalize_state_empty(self) -> None:
        assert DataNormalizer.normalize_state("") is None
        assert DataNormalizer.normalize_state(None) is None

    def test_normalize_list_field_basic(self) -> None:
        items = ["Director 1", "Director 2", "Director 1"]
        result = DataNormalizer.normalize_list_field(items)
        assert len(result) == 2
        assert "Director 1" in result
        assert "Director 2" in result

    def test_normalize_list_field_empty(self) -> None:
        assert DataNormalizer.normalize_list_field([]) is None
        assert DataNormalizer.normalize_list_field(None) is None
        # Whitespace-only items are filtered but list is returned
        result = DataNormalizer.normalize_list_field(["", "  "])
        assert result is None or len(result) <= 1

    def test_extract_legal_form_from_name(self) -> None:
        name, legal_form = DataNormalizer.extract_legal_form_from_name("Test Company GmbH")
        assert name == "Test Company"
        assert legal_form == "GmbH"

    def test_extract_legal_form_from_name_with_parentheses(self) -> None:
        name, legal_form = DataNormalizer.extract_legal_form_from_name("Test Company (UG)")
        assert name == "Test Company"
        assert legal_form == "(UG)"

    def test_extract_legal_form_from_name_none(self) -> None:
        name, legal_form = DataNormalizer.extract_legal_form_from_name("Test Company")
        assert name == "Test Company"
        assert legal_form is None

    def test_normalize_company_data_with_embedded_legal_form(self) -> None:
        data = {
            "company_name": "test company GmbH",
            "city": "stuttgart",
            "state": "bw",
        }

        normalized = DataNormalizer.normalize_company_data(data)

        assert normalized["company_name"] == "Test Company"
        assert normalized["legal_form"] == "GmbH"
        assert normalized["city"] == "Stuttgart"
        assert normalized["state"] == "Baden-Württemberg"

    def test_normalize_company_data_with_description(self) -> None:
        data = {
            "company_name": "test company",
            "description": "  A great company  ",
        }

        normalized = DataNormalizer.normalize_company_data(data)

        assert normalized["description"] == "A great company"

    def test_normalize_company_data_long_description(self) -> None:
        data = {
            "company_name": "test",
            "description": "x" * 1500,
        }

        normalized = DataNormalizer.normalize_company_data(data)

        assert len(normalized["description"]) == 1000
        assert normalized["description"].endswith("...")

    def test_normalize_company_data_with_list_fields(self) -> None:
        data = {
            "company_name": "test",
            "directors": ["John Doe", "Jane Doe", "John Doe"],
            "services": ["Service A", "", "Service B"],
        }

        normalized = DataNormalizer.normalize_company_data(data)

        assert len(normalized["directors"]) == 2
        assert len(normalized["services"]) == 2

    def test_normalize_company_data_empty(self) -> None:
        normalized = DataNormalizer.normalize_company_data({})
        assert isinstance(normalized, dict)
        assert len(normalized) == 0
