"""Benchmark test case generator, validator, and synthesizer.

This helper script maintains the dataset used by the benchmarking harness.

Usage examples:
    python scripts/benchmarks/generate_test_cases.py --interactive
    python scripts/benchmarks/generate_test_cases.py --validate
    python scripts/benchmarks/generate_test_cases.py --generate-synthetic --count 5 --complexity medium

The script reads and writes ``data/benchmarks/test_cases.json``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

TEST_CASES_PATH = Path("data/benchmarks/test_cases.json")

DEFAULT_EXPECTED_TEMPLATE: Dict[str, Any] = {
    "company_name": None,
    "address": None,
    "phone": None,
    "email": None,
    "website": None,
    "services": [],
    "directors": [],
    "technologies": [],
    "social_media": {},
    "team_size": None,
}


def load_test_cases(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of test cases in {path}")
    return data


def save_test_cases(path: Path, cases: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def extract_ground_truth_from_html(html_content: str) -> Dict[str, Any]:
    html_content = unescape(html_content)
    text_lower = html_content.lower()

    company_name = None
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, flags=re.IGNORECASE | re.DOTALL)
    if h1_match:
        company_name = _strip_tags(h1_match.group(1)).strip()

    email_match = re.search(r"mailto:([\w.+-]+@[\w-]+\.[\w.-]+)", text_lower)
    if not email_match:
        email_match = re.search(r"([\w.+-]+@[\w-]+\.[\w.-]+)", html_content)
    email = email_match.group(1) if email_match else None

    phone_match = re.search(r"tel:([+\d\s-]+)", text_lower)
    if not phone_match:
        phone_match = re.search(r"(?:phone|telefon|tel)[:\s]*([+\d\s/()-]{6,})", html_content, re.IGNORECASE)
    phone = phone_match.group(1).strip() if phone_match else None

    website_match = re.search(r"https?://[\w./-]+", html_content)
    website = website_match.group(0) if website_match else None

    address_match = re.search(r"(?:adresse|address)[:\s]*(.+?)</", html_content, flags=re.IGNORECASE)
    address = _strip_tags(address_match.group(1)).strip() if address_match else None

    services: List[str] = []
    services_block = re.search(r"<h2[^>]*>\s*services\s*</h2>\s*<ul>(.*?)</ul>", html_content, flags=re.IGNORECASE | re.DOTALL)
    if services_block:
        services = [
            _strip_tags(item).strip()
            for item in re.findall(r"<li[^>]*>(.*?)</li>", services_block.group(1), flags=re.DOTALL)
            if _strip_tags(item).strip()
        ]

    directors: List[Dict[str, Optional[str]]] = []
    for match in re.findall(r"(?:director|ceo|cto|cfo|coo|lead|head)[:\s]+([^<]+)", html_content, flags=re.IGNORECASE):
        name = match.strip()
        if name:
            directors.append({"name": name, "title": None})

    return {
        "company_name": company_name,
        "address": address,
        "phone": phone,
        "email": email,
        "website": website,
        "services": services,
        "directors": directors,
    }


def _prompt(message: str, default: Optional[str] = None) -> str:
    prompt = f"{message}"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    response = input(prompt).strip()
    return response or (default or "")


def _prompt_multiline() -> str:
    print("Paste HTML content. Enter a single line with 'EOF' to finish.")
    lines: List[str] = []
    while True:
        line = input()
        if line.strip() == "EOF":
            break
        lines.append(line)
    return "\n".join(lines)


def _load_html_from_user() -> str:
    choice = _prompt("Provide HTML file path or type 'PASTE' to paste HTML", "PASTE")
    if choice.upper() == "PASTE":
        return _prompt_multiline()

    file_path = Path(choice).expanduser()
    if not file_path.exists():
        print(f"File {file_path} not found. Falling back to paste mode.")
        return _prompt_multiline()
    return file_path.read_text(encoding="utf-8")


def create_test_case_interactive(test_cases_path: Path = TEST_CASES_PATH) -> None:
    print("Creating a new benchmark test case. Press Ctrl+C to cancel.\n")
    cases = load_test_cases(test_cases_path)
    existing_ids = {case.get("id") for case in cases}

    while True:
        identifier = _prompt("Unique test case ID (e.g. TC021)")
        if identifier and identifier not in existing_ids:
            break
        print("ID is required and must be unique. Try again.")

    name = _prompt("Descriptive name")
    complexity = _prompt("Complexity (simple/medium/complex/edge)", "medium")
    content_type = _prompt("Content type (company_page/contact_page/services_page/team_page)", "company_page")

    html_content = _load_html_from_user()
    auto_data = extract_ground_truth_from_html(html_content)
    expected_data = deepcopy(DEFAULT_EXPECTED_TEMPLATE)
    expected_data.update({k: v for k, v in auto_data.items() if v})

    print("\nDetected values (press Enter to accept):")
    expected_data["company_name"] = _prompt("Company name", expected_data.get("company_name") or "") or None
    expected_data["address"] = _prompt("Address", expected_data.get("address") or "") or None
    expected_data["phone"] = _prompt("Phone", expected_data.get("phone") or "") or None
    expected_data["email"] = _prompt("Email", expected_data.get("email") or "") or None
    expected_data["website"] = _prompt("Website", expected_data.get("website") or "") or None

    services_input = _prompt("Services (comma separated)", ", ".join(expected_data.get("services", [])) or "")
    expected_data["services"] = [item.strip() for item in services_input.split(",") if item.strip()]

    technologies_input = _prompt("Technologies (comma separated)")
    expected_data["technologies"] = [item.strip() for item in technologies_input.split(",") if item.strip()]

    directors_input = _prompt("Directors (format: Name:Title;Name:Title)")
    directors: List[Dict[str, Optional[str]]] = []
    for raw in directors_input.split(";"):
        if not raw.strip():
            continue
        if ":" in raw:
            name, title = raw.split(":", 1)
            directors.append({"name": name.strip(), "title": title.strip()})
        else:
            directors.append({"name": raw.strip(), "title": None})
    expected_data["directors"] = directors

    social_input = _prompt("Social media (format: key=url,key=url)")
    social_media: Dict[str, str] = {}
    for pair in social_input.split(","):
        if not pair.strip():
            continue
        if "=" not in pair:
            print(f"Ignoring malformed social media entry: {pair}")
            continue
        key, value = pair.split("=", 1)
        social_media[key.strip()] = value.strip()
    expected_data["social_media"] = social_media

    team_size_input = _prompt("Team size (integer)")
    expected_data["team_size"] = int(team_size_input) if team_size_input.isdigit() else None

    new_case = {
        "id": identifier,
        "name": name or identifier,
        "complexity": complexity,
        "content_type": content_type,
        "html_content": html_content,
        "expected_data": expected_data,
        "metadata": {
            "created_via": "interactive",
        },
    }

    cases.append(new_case)
    save_test_cases(test_cases_path, cases)
    print(f"\n✅ Test case '{identifier}' added to {test_cases_path}.")


def validate_test_cases(test_cases_file: str) -> bool:
    path = Path(test_cases_file)
    if not path.exists():
        print(f"❌ Test cases file not found: {path}")
        return False

    try:
        cases = load_test_cases(path)
    except ValueError as exc:
        print(f"❌ {exc}")
        return False

    success = True
    seen_ids: set[str] = set()

    for index, case in enumerate(cases, start=1):
        location = f"Case #{index} ({case.get('id', 'unknown')})"

        for field in ("id", "name", "expected_data", "html_content"):
            if field not in case:
                print(f"❌ {location}: Missing required field '{field}'.")
                success = False

        identifier = case.get("id")
        if identifier in seen_ids:
            print(f"❌ Duplicate case id detected: {identifier}")
            success = False
        else:
            seen_ids.add(identifier)

        html_content = case.get("html_content")
        if not isinstance(html_content, str) or not html_content.strip():
            print(f"❌ {location}: 'html_content' must be a non-empty string or file reference.")
            success = False
        elif html_content.strip().startswith("file://"):
            file_path = Path(html_content[7:])
            if not file_path.exists():
                print(f"❌ {location}: Referenced HTML file does not exist: {file_path}")
                success = False

        if not isinstance(case.get("expected_data"), dict):
            print(f"❌ {location}: 'expected_data' must be a JSON object.")
            success = False

    if success:
        print(f"✅ Validation passed. {len(cases)} test cases ready for benchmarking.")
    return success


def generate_synthetic_test_case(complexity: str) -> Dict[str, Any]:
    complexity = complexity.lower()
    if complexity not in {"simple", "medium", "complex"}:
        raise ValueError("Complexity must be one of: simple, medium, complex")

    if complexity == "simple":
        name = "Synthetic Simple Company"
        html_content = (
            "<html><body><h1>Synthetic Simple Company</h1><p>Email: simple@example.com</p>"
            "<p>Phone: +49 89 123456</p></body></html>"
        )
        expected_data = {
            "company_name": "Synthetic Simple Company",
            "address": None,
            "phone": "+49 89 123456",
            "email": "simple@example.com",
            "website": None,
            "services": [],
            "directors": [],
            "technologies": [],
            "social_media": {},
            "team_size": None,
        }
        content_type = "company_page"
    elif complexity == "medium":
        name = "Synthetic Service Snapshot"
        html_content = (
            "<html><body><h1>Synthetic Service Snapshot</h1><h2>Services</h2><ul>"
            "<li>Cloud Migration</li><li>Security Audit</li></ul>"
            "<p>Contact us at <a href=\"mailto:services@example.com\">services@example.com</a>.</p>"
            "</body></html>"
        )
        expected_data = {
            "company_name": "Synthetic Service Snapshot",
            "address": None,
            "phone": None,
            "email": "services@example.com",
            "website": None,
            "services": ["Cloud Migration", "Security Audit"],
            "directors": [],
            "technologies": [],
            "social_media": {},
            "team_size": None,
        }
        content_type = "services_page"
    else:  # complex
        name = "Synthetic Enterprise Profile"
        html_content = (
            "<html><body><h1>Synthetic Enterprise Profile</h1><p>Address: Example Way 42, 80331 München</p>"
            "<p>Phone: +49 89 654321</p><p>Website: https://enterprise.example.com</p>"
            "<ul><li>CEO: Alex König</li><li>CTO: Jamie Roth</li></ul>"
            "<section><h2>Technologies</h2>We use Python, FastAPI, and Postgres.</section>"
            "</body></html>"
        )
        expected_data = {
            "company_name": "Synthetic Enterprise Profile",
            "address": "Example Way 42, 80331 München",
            "phone": "+49 89 654321",
            "email": None,
            "website": "https://enterprise.example.com",
            "services": [],
            "directors": [
                {"name": "Alex König", "title": "CEO"},
                {"name": "Jamie Roth", "title": "CTO"},
            ],
            "technologies": ["Python", "FastAPI", "Postgres"],
            "social_media": {},
            "team_size": None,
        }
        content_type = "company_page"

    return {
        "name": name,
        "complexity": complexity,
        "content_type": content_type,
        "html_content": html_content,
        "expected_data": expected_data,
        "metadata": {"created_via": "synthetic"},
    }


def _generate_unique_ids(existing_ids: Iterable[str], count: int, prefix: str = "SYN") -> List[str]:
    taken = {identifier for identifier in existing_ids if identifier}
    next_index = 1
    generated: List[str] = []
    while len(generated) < count:
        candidate = f"{prefix}{next_index:03d}"
        if candidate not in taken:
            generated.append(candidate)
        next_index += 1
    return generated


def handle_generate_synthetic(count: int, complexity: str, test_cases_path: Path) -> None:
    cases = load_test_cases(test_cases_path)
    new_cases: List[Dict[str, Any]] = []
    ids = _generate_unique_ids((case.get("id") for case in cases), count)

    for identifier in ids:
        synthetic = generate_synthetic_test_case(complexity)
        synthetic_case = {
            "id": identifier,
            **synthetic,
        }
        new_cases.append(synthetic_case)

    save_test_cases(test_cases_path, cases + new_cases)
    print(f"✅ Added {len(new_cases)} synthetic test case(s) to {test_cases_path}.")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Maintain benchmark test cases.")
    parser.add_argument(
        "--test-cases-file",
        default=str(TEST_CASES_PATH),
        help="Path to test_cases.json (defaults to repository dataset).",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--interactive", action="store_true", help="Add a test case interactively.")
    group.add_argument("--validate", action="store_true", help="Validate the dataset and exit.")
    group.add_argument(
        "--generate-synthetic",
        action="store_true",
        help="Generate synthetic test cases and append to the dataset.",
    )

    parser.add_argument("--count", type=int, default=1, help="Number of synthetic cases to generate.")
    parser.add_argument(
        "--complexity",
        choices=["simple", "medium", "complex"],
        default="simple",
        help="Complexity level for synthetic cases.",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    test_cases_path = Path(args.test_cases_file)

    if args.interactive:
        try:
            create_test_case_interactive(test_cases_path)
        except KeyboardInterrupt:
            print("\nCancelled by user.")
            return 1
        return 0

    if args.validate:
        return 0 if validate_test_cases(str(test_cases_path)) else 1

    if args.generate_synthetic:
        handle_generate_synthetic(args.count, args.complexity, test_cases_path)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
