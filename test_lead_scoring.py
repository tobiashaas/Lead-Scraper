"""
Test Lead Scoring System
"""

from app.utils.lead_scorer import LeadScorer

print("=" * 80)
print("📈 LEAD SCORING TEST")
print("=" * 80)
print()

scorer = LeadScorer()

# Test Cases
test_companies = [
    {
        "name": "High Quality Lead",
        "email": "info@techcompany.de",
        "phone": "+49 711 123456",
        "website": "https://www.techcompany.de",
        "address": "Hauptstraße 1, 70173 Stuttgart",
        "city": "Stuttgart",
        "industry": "Software Development",
        "team_size": 150,
        "technologies": ["React", "Node.js", "AWS", "PostgreSQL"],
        "directors": ["Max Mustermann", "Anna Schmidt"],
    },
    {
        "name": "Medium Quality Lead",
        "email": "contact@company.com",
        "website": "https://company.com",
        "city": "Berlin",
        "industry": "Consulting",
        "team_size": 25,
    },
    {
        "name": "Low Quality Lead",
        "phone": "123456",
        "city": "München",
    },
]

for i, company in enumerate(test_companies, 1):
    print(f"Test {i}: {company.get('name', 'Unknown')}")
    print("-" * 80)
    
    result = scorer.score_lead(company)
    
    print(f"✅ Score: {result['score']}/100")
    print(f"   Quality: {result['quality'].upper()}")
    print()
    print("   Breakdown:")
    for category, details in result['breakdown'].items():
        print(f"     - {category}: {details}")
    
    if result['recommendations']:
        print()
        print("   Recommendations:")
        for rec in result['recommendations']:
            print(f"     • {rec}")
    
    print()
    print()

print("=" * 80)
print("📊 SCORING STATISTICS")
print("=" * 80)
stats = scorer.get_stats()
for key, value in stats.items():
    print(f"  {key}: {value}")

print()
print("=" * 80)
print("✅ Lead Scoring Test abgeschlossen!")
print("=" * 80)
