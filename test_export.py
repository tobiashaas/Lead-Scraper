"""
Test Export Endpoints
"""

import requests

API_URL = "http://localhost:8000"

# Login um Token zu bekommen
print("🔐 Login...")
login_response = requests.post(
    f"{API_URL}/api/v1/auth/login", json={"username": "tobiashaas", "password": "HaasMal!a123"}
)

if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    print(f"✅ Token erhalten: {token[:50]}...")
    print()

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test Stats Export
    print("=" * 80)
    print("📊 TEST: Company Statistics")
    print("=" * 80)

    stats_response = requests.get(f"{API_URL}/api/v1/export/companies/stats", headers=headers)

    if stats_response.status_code == 200:
        stats = stats_response.json()
        print("✅ Stats Export erfolgreich!")
        print(f"   Total Companies: {stats['total_companies']}")
        print(f"   By Status: {stats['by_lead_status']}")
        print(f"   By Quality: {stats['by_lead_quality']}")
        if stats["top_cities"]:
            print(f"   Top City: {stats['top_cities'][0]}")
    else:
        print(f"❌ Stats Export failed: {stats_response.status_code}")
        print(stats_response.text)

    print()

    # 2. Test JSON Export
    print("=" * 80)
    print("📄 TEST: JSON Export")
    print("=" * 80)

    json_response = requests.get(f"{API_URL}/api/v1/export/companies/json?limit=5", headers=headers)

    if json_response.status_code == 200:
        data = json_response.json()
        print("✅ JSON Export erfolgreich!")
        print(f"   Total: {data['total']}")
        print(f"   Companies: {len(data['companies'])}")
        if data["companies"]:
            print(f"   First Company: {data['companies'][0]['name']}")
    else:
        print(f"❌ JSON Export failed: {json_response.status_code}")
        print(json_response.text)

    print()

    # 3. Test CSV Export
    print("=" * 80)
    print("📊 TEST: CSV Export")
    print("=" * 80)

    csv_response = requests.get(f"{API_URL}/api/v1/export/companies/csv?limit=5", headers=headers)

    if csv_response.status_code == 200:
        csv_data = csv_response.text
        lines = csv_data.strip().split("\n")
        print("✅ CSV Export erfolgreich!")
        print(f"   Lines: {len(lines)}")
        print(f"   Header: {lines[0][:80]}...")
        if len(lines) > 1:
            print(f"   First Row: {lines[1][:80]}...")
    else:
        print(f"❌ CSV Export failed: {csv_response.status_code}")
        print(csv_response.text)

else:
    print(f"❌ Login failed: {login_response.status_code}")
    print(login_response.text)

print()
print("=" * 80)
print("✅ Export Tests abgeschlossen!")
print("=" * 80)
