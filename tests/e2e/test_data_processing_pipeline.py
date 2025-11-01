import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.database.models import Company
from tests.utils.test_helpers import wait_for_scraping_job_completion_async


async def _run_job(async_client, auth_headers, payload):
    response = await async_client.post(
        "/api/v1/scraping/jobs",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    job_id = response.json()["id"]
    job_data = await wait_for_scraping_job_completion_async(
        client=async_client,
        job_id=job_id,
        auth_headers=auth_headers,
        timeout=30,
        poll_interval=0.5,
    )
    return job_id, job_data


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scraped_companies_are_validated_and_normalized(
    async_client,
    auth_headers,
    db_session: Session,
    html_fixture_loader,
    mock_playwright_with_html,
    mock_rate_limiter,
    mock_tor_proxy,
    create_source,
):
    create_source(name="gelbe_seiten")

    html = html_fixture_loader("gelbe_seiten_overlap_stuttgart_it_service.html")
    mock_playwright_with_html(html)

    job_id, job_data = await _run_job(
        async_client,
        auth_headers,
        {
            "source_name": "gelbe_seiten",
            "city": "Stuttgart",
            "industry": "IT-Service",
            "max_pages": 1,
            "use_tor": False,
            "use_ai": False,
        },
    )

    assert job_data["status"] == "completed"
    assert job_data["new_companies"] == 3
    assert job_data["updated_companies"] == 0
    assert job_data["errors_count"] == 0

    detail_response = await async_client.get(
        f"/api/v1/scraping/jobs/{job_id}", headers=auth_headers
    )
    assert detail_response.status_code == status.HTTP_200_OK
    detail_payload = detail_response.json()
    assert detail_payload["results_count"] == 3
    assert detail_payload["errors_count"] == 0

    db_session.expire_all()

    technical_support = (
        db_session.query(Company)
        .filter(Company.company_name == "Technical Support", Company.city == "Stuttgart")
        .first()
    )
    assert technical_support is not None
    assert technical_support.phone == "+49 711 8829810"
    assert technical_support.legal_form is None

    cloud_experts = (
        db_session.query(Company)
        .filter(Company.company_name == "Cloud Experts", Company.city == "Stuttgart")
        .first()
    )
    assert cloud_experts is not None
    assert cloud_experts.legal_form == "GmbH"
    assert cloud_experts.postal_code == "70179"
    assert cloud_experts.company_name == "Cloud Experts"

    assert technical_support.email == "service@techsupport.de"
    assert technical_support.website == "https://www.techsupport.de"
    assert technical_support.postal_code == "70567"
    assert technical_support.city == "Stuttgart"
