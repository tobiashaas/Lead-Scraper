import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.database.models import Company, ScrapingJob
from tests.utils.test_helpers import wait_for_scraping_job_completion_async


async def _start_scraping_job(async_client, auth_headers, payload):
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
class TestMultiSourceWorkflows:
    async def test_sequential_multi_source_runs_deduplicate_companies(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
    ):
        create_source(name="11880")
        create_source(name="gelbe_seiten")

        html_11880 = html_fixture_loader("11880_stuttgart_it_service.html")
        html_gelbe = html_fixture_loader("gelbe_seiten_overlap_stuttgart_it_service.html")

        mock_playwright_with_html(html_11880)
        job_11880_id, job_11880 = await _start_scraping_job(
            async_client,
            auth_headers,
            {
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
        )
        assert job_11880["status"] == "completed"
        assert job_11880["new_companies"] == 3

        mock_playwright_with_html(html_gelbe)
        job_gelbe_id, job_gelbe = await _start_scraping_job(
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
        assert job_gelbe["status"] == "completed"
        assert job_gelbe["new_companies"] == 2
        assert job_gelbe["updated_companies"] == 1

        db_session.expire_all()
        companies = (
            db_session.query(Company)
            .filter(Company.city == "Stuttgart")
            .order_by(Company.company_name)
            .all()
        )
        assert len(companies) == 5

        company_names = [company.company_name.lower() for company in companies]
        assert len(company_names) == len(set(company_names)), "duplicate companies persisted"

        tech_support = (
            db_session.query(Company).filter(Company.company_name == "Technical Support").first()
        )
        assert tech_support is not None
        assert tech_support.email == "service@techsupport.de"
        assert tech_support.website == "https://www.techsupport.de"

        detail_response = await async_client.get(
            f"/api/v1/scraping/jobs/{job_gelbe_id}", headers=auth_headers
        )
        assert detail_response.status_code == status.HTTP_200_OK
        detail_payload = detail_response.json()
        assert detail_payload["new_companies"] == 2
        assert detail_payload["updated_companies"] == 1

        job_records = (
            db_session.query(ScrapingJob)
            .filter(ScrapingJob.id.in_([job_11880_id, job_gelbe_id]))
            .order_by(ScrapingJob.id)
            .all()
        )
        assert len(job_records) == 2
        assert {job.status for job in job_records} == {"completed"}

    async def test_different_cities_do_not_merge_records(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
    ):
        create_source(name="11880")

        html_stuttgart = html_fixture_loader("11880_stuttgart_it_service.html")
        html_munich = html_stuttgart.replace("Stuttgart", "München")

        mock_playwright_with_html(html_stuttgart)
        _, job_stuttgart = await _start_scraping_job(
            async_client,
            auth_headers,
            {
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
        )
        assert job_stuttgart["status"] == "completed"
        assert job_stuttgart["results_count"] == 3

        mock_playwright_with_html(html_munich)
        _, job_munich = await _start_scraping_job(
            async_client,
            auth_headers,
            {
                "source_name": "11880",
                "city": "München",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
        )
        assert job_munich["status"] == "completed"
        assert job_munich["new_companies"] == 3

        db_session.expire_all()
        stuttgart_companies = db_session.query(Company).filter(Company.city == "Stuttgart").all()
        munich_companies = db_session.query(Company).filter(Company.city == "München").all()

        assert len(stuttgart_companies) == 3
        assert len(munich_companies) == 3

        stuttgart_names = {company.company_name for company in stuttgart_companies}
        munich_names = {company.company_name for company in munich_companies}
        assert stuttgart_names == munich_names

        duplicates = (
            db_session.query(Company).filter(Company.company_name == "Technical Support").all()
        )
        assert {company.city for company in duplicates} == {"Stuttgart", "München"}

    async def test_job_statistics_across_multiple_runs(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
    ):
        create_source(name="11880")
        create_source(name="gelbe_seiten")

        html_11880 = html_fixture_loader("11880_stuttgart_it_service.html")
        html_gelbe = html_fixture_loader("gelbe_seiten_overlap_stuttgart_it_service.html")

        mock_playwright_with_html(html_11880)
        job1_id, job1 = await _start_scraping_job(
            async_client,
            auth_headers,
            {
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
        )

        mock_playwright_with_html(html_gelbe)
        job2_id, job2 = await _start_scraping_job(
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

        assert job1["results_count"] == 3
        assert job2["results_count"] == 3
        assert job2["new_companies"] == 2
        assert job2["updated_companies"] == 1

        list_response = await async_client.get(
            "/api/v1/scraping/jobs",
            headers=auth_headers,
            params={"limit": 10, "skip": 0},
        )
        assert list_response.status_code == status.HTTP_200_OK
        list_payload = list_response.json()
        assert list_payload["total"] == 2

        jobs_by_id = {item["id"]: item for item in list_payload["items"]}
        assert jobs_by_id[job1_id]["results_count"] == job1["results_count"]
        assert jobs_by_id[job2_id]["updated_companies"] == job2["updated_companies"]

        db_session.expire_all()
        job_records = (
            db_session.query(ScrapingJob).filter(ScrapingJob.id.in_([job1_id, job2_id])).all()
        )
        assert len(job_records) == 2
        total_results = sum(job.results_count for job in job_records)
        assert total_results == job1["results_count"] + job2["results_count"]
