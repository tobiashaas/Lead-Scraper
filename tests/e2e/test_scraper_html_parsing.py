import pytest

from app.scrapers.eleven_eighty import ElevenEightyScaper
from app.scrapers.gelbe_seiten import GelbeSeitenScraper


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_eleven_eighty_parse_search_results_extracts_contact_details(html_fixture_loader):
    scraper = ElevenEightyScaper(use_tor=False)
    html = html_fixture_loader("11880_stuttgart_it_service.html")

    results = await scraper.parse_search_results(html, "https://www.11880.com/suche")

    assert len(results) == 3

    technical_support = next(result for result in results if result.company_name == "Technical Support")
    assert technical_support.phone == "+497118829810"
    assert technical_support.postal_code == "70567"
    assert technical_support.city == "Stuttgart"
    assert technical_support.address.startswith("Musterstraße 123")

    netpolte = next(result for result in results if result.company_name == "NETPOLTE EDV Dienstleistungen")
    assert netpolte.phone == "+4971146051188"
    assert netpolte.email is None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_gelbe_seiten_parse_results_normalizes_redirect_and_mailto_links(html_fixture_loader):
    scraper = GelbeSeitenScraper(use_tor=False)
    html = html_fixture_loader("gelbe_seiten_overlap_stuttgart_it_service.html")

    results = await scraper.parse_search_results(html, "https://www.gelbeseiten.de/Suche")

    assert len(results) == 3

    stuttgart_software = next(result for result in results if result.company_name == "Stuttgart Software AG")
    assert stuttgart_software.email == "info@stuttgart-software.de"
    assert stuttgart_software.website == "https://www.stuttgart-software.de"
    assert stuttgart_software.postal_code == "70178"

    technical_support = next(result for result in results if result.company_name == "Technical Support")
    assert technical_support.phone == "+497118829810"
    assert technical_support.email == "service@techsupport.de"
