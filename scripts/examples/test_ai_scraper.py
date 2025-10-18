"""
Test AI Web Scraper with Scrapegraph-AI

This script demonstrates how to use the AI Web Scraper to extract
structured data from company websites.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.ai_web_scraper import AIWebScraper


def test_company_extraction():
    """Test extracting complete company data"""
    print("=" * 80)
    print("TEST 1: Extract Complete Company Data")
    print("=" * 80)

    scraper = AIWebScraper()

    # Test with a real company website
    url = "https://www.example-company.com"  # Replace with actual URL

    print(f"\nExtracting data from: {url}")
    data = scraper.extract_company_data(url)

    print("\n📊 Extracted Data:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    return data


def test_employee_extraction():
    """Test extracting only employees"""
    print("\n" + "=" * 80)
    print("TEST 2: Extract Employees Only")
    print("=" * 80)

    scraper = AIWebScraper()

    # Test with team/about page
    url = "https://www.example-company.com/team"  # Replace with actual URL

    print(f"\nExtracting employees from: {url}")
    employees = scraper.extract_employees(url)

    print(f"\n👥 Found {len(employees)} employees:")
    for emp in employees:
        print(f"  - {emp.get('name', 'N/A')} ({emp.get('position', 'N/A')})")
        if emp.get('email'):
            print(f"    Email: {emp['email']}")

    return employees


def test_contact_extraction():
    """Test extracting contact information"""
    print("\n" + "=" * 80)
    print("TEST 3: Extract Contact Information")
    print("=" * 80)

    scraper = AIWebScraper()

    url = "https://www.example-company.com/contact"  # Replace with actual URL

    print(f"\nExtracting contact info from: {url}")
    contact = scraper.extract_contact_info(url)

    print("\n📞 Contact Information:")
    print(json.dumps(contact, indent=2, ensure_ascii=False))

    return contact


def test_services_extraction():
    """Test extracting services/products"""
    print("\n" + "=" * 80)
    print("TEST 4: Extract Services/Products")
    print("=" * 80)

    scraper = AIWebScraper()

    url = "https://www.example-company.com/services"  # Replace with actual URL

    print(f"\nExtracting services from: {url}")
    services = scraper.extract_services(url)

    print(f"\n🛠️ Found {len(services)} services:")
    for service in services:
        print(f"  - {service}")

    return services


def test_custom_extraction():
    """Test custom extraction with custom prompt"""
    print("\n" + "=" * 80)
    print("TEST 5: Custom Extraction")
    print("=" * 80)

    scraper = AIWebScraper()

    url = "https://www.example-company.com"  # Replace with actual URL

    custom_prompt = """
    Extract the following from this company website:
    {
        "founded_year": "Year company was founded",
        "number_of_employees": "Approximate number of employees",
        "headquarters": "Location of headquarters",
        "industry": "Primary industry/sector"
    }
    Return ONLY valid JSON.
    """

    print(f"\nExtracting custom data from: {url}")
    data = scraper.extract_custom(url, custom_prompt)

    print("\n🎯 Custom Extracted Data:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    return data


def main():
    """Run all tests"""
    print("\n🤖 AI Web Scraper Test Suite")
    print("Using Scrapegraph-AI + Ollama\n")

    print("⚠️  Make sure Ollama is running: ollama serve")
    print("⚠️  Make sure you have llama3.2 model: ollama pull llama3.2\n")

    input("Press Enter to start tests...")

    try:
        # Run tests
        test_company_extraction()
        test_employee_extraction()
        test_contact_extraction()
        test_services_extraction()
        test_custom_extraction()

        print("\n" + "=" * 80)
        print("✅ All tests completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
