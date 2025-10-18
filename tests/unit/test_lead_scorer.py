"""
Tests für Lead Scorer Utility
Unit Tests ohne Database Dependency
"""

from app.utils.lead_scorer import LeadScorer, score_company


def test_lead_scorer_initialization():
    """Test LeadScorer Initialisierung"""
    scorer = LeadScorer()

    assert scorer.stats["total_scored"] == 0
    assert scorer.stats["hot_leads"] == 0
    assert scorer.stats["warm_leads"] == 0
    assert scorer.stats["cold_leads"] == 0
    assert scorer.stats["low_quality"] == 0


def test_score_high_quality_lead():
    """Test Scoring für High Quality Lead"""
    company_data = {
        "name": "Tech Company GmbH",
        "email": "info@techcompany.de",
        "phone": "+49 711 123456",
        "website": "https://www.techcompany.de",
        "address": "Hauptstraße 1, 70173 Stuttgart",
        "city": "Stuttgart",
        "industry": "Software Development",
        "team_size": 150,
        "technologies": ["React", "Node.js", "AWS", "PostgreSQL"],
        "directors": ["Max Mustermann", "Anna Schmidt"],
    }

    result = score_company(company_data)

    assert result["score"] >= 80
    assert result["quality"] == "hot"
    assert "breakdown" in result
    assert "recommendations" in result
    assert isinstance(result["breakdown"], dict)
    assert isinstance(result["recommendations"], list)


def test_score_medium_quality_lead():
    """Test Scoring für Medium Quality Lead"""
    company_data = {
        "name": "Medium Company",
        "email": "contact@company.com",
        "website": "https://company.com",
        "city": "Berlin",
        "industry": "Consulting",
        "team_size": 25,
    }

    result = score_company(company_data)

    assert 40 <= result["score"] < 80
    assert result["quality"] in ["warm", "cold"]


def test_score_low_quality_lead():
    """Test Scoring für Low Quality Lead"""
    company_data = {"name": "Low Quality", "phone": "123456", "city": "München"}

    result = score_company(company_data)

    assert result["score"] < 40
    assert result["quality"] == "low_quality"
    assert len(result["recommendations"]) > 0


def test_score_contact_data_complete():
    """Test Contact Data Scoring - Vollständig"""
    scorer = LeadScorer()

    company_data = {
        "name": "Test Company",
        "email": "test@example.com",
        "phone": "+49 711 123456",
        "address": "Test Street 1",
        "directors": ["John Doe"],
    }

    result = scorer.score_lead(company_data)
    contact_score = result["breakdown"]["contact_data"]

    assert contact_score["email"] == "valid"
    assert contact_score["phone"] == "valid"
    assert contact_score["address"] == "present"


def test_score_contact_data_incomplete():
    """Test Contact Data Scoring - Unvollständig"""
    scorer = LeadScorer()

    company_data = {"name": "Test Company"}

    result = scorer.score_lead(company_data)
    contact_score = result["breakdown"]["contact_data"]

    assert contact_score["email"] == "missing"
    assert contact_score["phone"] == "missing"


def test_score_website_https():
    """Test Website Scoring - HTTPS"""
    scorer = LeadScorer()

    company_data = {"name": "Test", "website": "https://example.com"}

    result = scorer.score_lead(company_data)
    website_score = result["breakdown"]["website"]

    assert website_score["status"] == "present"
    assert website_score["https"] is True


def test_score_website_no_https():
    """Test Website Scoring - No HTTPS"""
    scorer = LeadScorer()

    company_data = {"name": "Test", "website": "http://example.com"}

    result = scorer.score_lead(company_data)
    website_score = result["breakdown"]["website"]

    assert website_score["status"] == "present"
    assert website_score["https"] is False


def test_score_high_value_industry():
    """Test Industry Scoring - High Value"""
    scorer = LeadScorer()

    company_data = {"name": "Test", "industry": "Software Development"}

    result = scorer.score_lead(company_data)
    industry_score = result["breakdown"]["industry"]

    assert industry_score["status"] == "present"
    assert industry_score["high_value"] is True


def test_score_regular_industry():
    """Test Industry Scoring - Regular"""
    scorer = LeadScorer()

    company_data = {"name": "Test", "industry": "Retail"}

    result = scorer.score_lead(company_data)
    industry_score = result["breakdown"]["industry"]

    assert industry_score["status"] == "present"
    assert industry_score["high_value"] is False


def test_score_company_size_large():
    """Test Company Size Scoring - Large"""
    scorer = LeadScorer()

    company_data = {"name": "Test", "team_size": 200}

    result = scorer.score_lead(company_data)
    size_score = result["breakdown"]["company_size"]

    assert size_score["category"] == "large"
    assert size_score["size"] == 200


def test_score_company_size_small():
    """Test Company Size Scoring - Small"""
    scorer = LeadScorer()

    company_data = {"name": "Test", "team_size": 15}

    result = scorer.score_lead(company_data)
    size_score = result["breakdown"]["company_size"]

    assert size_score["category"] == "small"


def test_score_modern_technologies():
    """Test Technology Scoring - Modern Tech"""
    scorer = LeadScorer()

    company_data = {
        "name": "Test",
        "technologies": ["React", "Docker", "Kubernetes", "AWS"],
    }

    result = scorer.score_lead(company_data)
    tech_score = result["breakdown"]["technologies"]

    assert tech_score["count"] == 4
    assert tech_score["modern_count"] > 0


def test_email_validation():
    """Test Email Validation"""
    scorer = LeadScorer()

    assert scorer._is_valid_email("test@example.com") is True
    assert scorer._is_valid_email("invalid-email") is False
    assert scorer._is_valid_email("") is False
    assert scorer._is_valid_email(None) is False


def test_phone_validation():
    """Test Phone Validation"""
    scorer = LeadScorer()

    assert scorer._is_valid_phone("+49 711 123456") is True
    assert scorer._is_valid_phone("0711-123456") is True
    assert scorer._is_valid_phone("123") is False
    assert scorer._is_valid_phone("") is False
    assert scorer._is_valid_phone(None) is False


def test_quality_categories():
    """Test Quality Category Assignment"""
    scorer = LeadScorer()

    assert scorer._get_quality_category(90) == "hot"
    assert scorer._get_quality_category(70) == "warm"
    assert scorer._get_quality_category(50) == "cold"
    assert scorer._get_quality_category(30) == "low_quality"


def test_scorer_statistics():
    """Test Scorer Statistics Tracking"""
    scorer = LeadScorer()

    # Score different quality leads
    scorer.score_lead(
        {
            "name": "Hot Lead",
            "email": "test@example.com",
            "phone": "+49 711 123456",
            "website": "https://example.com",
            "industry": "Software",
            "team_size": 100,
            "technologies": ["React", "AWS"],
            "directors": ["John Doe"],
        }
    )

    scorer.score_lead({"name": "Low Lead", "city": "Berlin"})

    stats = scorer.get_stats()

    assert stats["total_scored"] == 2
    assert stats["hot_leads"] >= 1
    assert stats["low_quality"] >= 1


def test_recommendations_generation():
    """Test Recommendations Generation"""
    company_data = {"name": "Test", "city": "Berlin"}

    result = score_company(company_data)

    assert len(result["recommendations"]) > 0
    assert any("Kontaktdaten" in rec for rec in result["recommendations"])


def test_score_with_missing_name():
    """Test Scoring mit fehlendem Namen"""
    company_data = {"email": "test@example.com", "city": "Berlin"}

    result = score_company(company_data)

    # Should handle missing name gracefully
    assert "score" in result
    assert result["score"] < 100  # Reduced score due to missing name
