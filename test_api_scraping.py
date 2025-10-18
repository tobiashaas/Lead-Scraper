"""
Test: Scraping Job über API starten
"""

import requests
import time
import json

API_URL = "http://localhost:8000"

# Dein Token (aus dem Login)
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0b2JpYXNoYWFzIiwidXNlcl9pZCI6MSwiZXhwIjoxNzYwNzk0NjMyLCJ0eXBlIjoiYWNjZXNzIn0.WoMF_HvjUeyJYMGNI0bKTmoHnAiZpisgixzxd1yVLnU"

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print("=" * 80)
print("🚀 SCRAPING JOB TEST - API Integration")
print("=" * 80)
print()

# 1. Starte Scraping Job
print("📝 Starte Scraping Job...")
print("-" * 80)

job_data = {
    "source": "smart_scraper",  # Unser AI-Scraper!
    "search_term": "IT Dienstleistungen",
    "location": "Stuttgart",
    "max_results": 3,
    "config": {
        "urls": [
            "https://www.microsoft.com/de-de/about",
            "https://github.com/about",
            "https://www.google.com/about",
        ]
    },
}

try:
    response = requests.post(
        f"{API_URL}/api/v1/scraping/jobs", headers=headers, json=job_data, timeout=30
    )

    if response.status_code == 200 or response.status_code == 201:
        job = response.json()
        job_id = job.get("id")

        print("✅ Job gestartet!")
        print(f"   Job ID: {job_id}")
        print(f"   Status: {job.get('status')}")
        print(f"   Source: {job.get('source')}")
        print()

        # 2. Warte und checke Status
        print("⏳ Warte auf Job-Completion...")
        print("-" * 80)

        max_wait = 60  # 60 Sekunden
        waited = 0

        while waited < max_wait:
            time.sleep(5)
            waited += 5

            # Check Status
            status_response = requests.get(
                f"{API_URL}/api/v1/scraping/jobs/{job_id}", headers=headers
            )

            if status_response.status_code == 200:
                job_status = status_response.json()
                status = job_status.get("status")

                print(f"   [{waited}s] Status: {status}")

                if status == "completed":
                    print()
                    print("✅ JOB ABGESCHLOSSEN!")
                    print("-" * 80)
                    print(f"   Ergebnisse: {job_status.get('results_count', 0)}")
                    print(f"   Dauer: {job_status.get('duration_seconds', 0)}s")

                    # Zeige Ergebnisse
                    if job_status.get("results"):
                        print()
                        print("📊 Extrahierte Companies:")
                        print("-" * 80)
                        for i, result in enumerate(job_status["results"][:3], 1):
                            print(f"\n{i}. {result.get('company_name', 'Unknown')}")
                            print(f"   URL: {result.get('source_url', 'N/A')}")
                            print(f"   Legal Form: {result.get('legal_form', 'N/A')}")
                            if result.get("services"):
                                print(f"   Services: {', '.join(result['services'][:2])}")

                    break

                elif status == "failed":
                    print()
                    print("❌ JOB FEHLGESCHLAGEN!")
                    print(f"   Error: {job_status.get('error_message', 'Unknown')}")
                    break

        if waited >= max_wait:
            print()
            print("⏰ Timeout - Job läuft noch...")

    else:
        print(f"❌ Fehler beim Starten: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback

    traceback.print_exc()

print()
print("=" * 80)
print("✅ Test abgeschlossen!")
print("=" * 80)
