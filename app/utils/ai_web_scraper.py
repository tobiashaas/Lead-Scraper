"""AI-Powered Web Scraper using Trafilatura + Ollama."""

from __future__ import annotations

import json
import math
import time
from textwrap import dedent
from typing import Any, Optional

import ollama
import trafilatura

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
from app.utils.model_selector import ModelSelector, auto_select_model

ALLOWED_OLLAMA_OPTIONS = {
    "temperature",
    "top_p",
    "top_k",
    "repeat_penalty",
    "presence_penalty",
    "frequency_penalty",
    "num_ctx",
    "num_predict",
    "stop",
}


DEFAULT_COMPANY_PROMPT = dedent(
    """
    Extract the following information from this company website:

    {
        "company_name": "Full company name",
        "employees": [
            {
                "name": "Full name",
                "position": "Job title",
                "email": "Email address if available",
                "phone": "Phone number if available"
            }
        ],
        "contact": {
            "email": "General company email",
            "phone": "General company phone",
            "address": "Full address"
        },
        "services": ["List of services or products offered"],
        "about": "Brief company description"
    }

    Return ONLY valid JSON. If information is not found, use null.
    """
).strip()


DEFAULT_EMPLOYEES_PROMPT = dedent(
    """
    Extract all employee/team member information from this page.

    Return as JSON array:
    [
        {
            "name": "Full name",
            "position": "Job title or role",
            "email": "Email if available",
            "phone": "Phone if available",
            "bio": "Short bio if available"
        }
    ]

    Return ONLY the JSON array, no explanations.
    """
).strip()


DEFAULT_CONTACT_PROMPT = dedent(
    """
    Extract all contact information from this website:

    {
        "email": "General contact email",
        "phone": "Phone number",
        "address": "Full physical address",
        "website": "Website URL",
        "linkedin": "LinkedIn URL",
        "facebook": "Facebook URL",
        "twitter": "Twitter URL",
        "instagram": "Instagram URL"
    }

    Return ONLY valid JSON. Use null for missing information.
    """
).strip()


DEFAULT_SERVICES_PROMPT = dedent(
    """
    Extract all services, products, or solutions offered by this company.

    Return as JSON array of strings:
    ["Service 1", "Service 2", "Service 3"]

    Return ONLY the JSON array.
    """
).strip()


class AIWebScraper:
    """
    AI-powered web scraper using Trafilatura + Ollama.

    Extracts structured data from websites using natural language prompts.
    Ideal for extracting employee information, contact details, services, etc.

    Example:
        >>> scraper = AIWebScraper()
        >>> data = scraper.extract_company_data("https://company.com")
        >>> print(data['employees'])
        [{'name': 'John Doe', 'position': 'CEO', 'email': 'john@company.com'}]
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0,
        max_content_length: int = 10000,
        use_model_selector: bool | None = None,
        priority: str | None = None,
    ):
        """
        Initialize AI Web Scraper.

        Args:
            model: Ollama model to use (default: llama3.2)
            temperature: LLM temperature (0 = deterministic)
            max_content_length: Max characters to send to LLM
        """
        self.use_model_selector = (
            use_model_selector
            if use_model_selector is not None
            else getattr(settings, "ollama_model_selection_enabled", False)
        )
        self.priority = priority or getattr(settings, "ollama_model_priority", "balanced")

        self.model_selector: Optional[ModelSelector] = None
        if self.use_model_selector:
            try:
                self.model_selector = ModelSelector()
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("ModelSelector initialization failed: %s", exc)
                self.use_model_selector = False

        self.model = model or self._initial_model()
        self.temperature = temperature
        self.max_content_length = max_content_length
        self.use_prompt_library = bool(
            self.model_selector and getattr(settings, "ollama_prompt_optimization_enabled", False)
        )
        self._stats: dict[str, Any] = {
            "requests": 0,
            "model_usage": {},
            "latencies": [],
            "errors": 0,
        }
        self.company_prompt = DEFAULT_COMPANY_PROMPT
        self.employees_prompt = DEFAULT_EMPLOYEES_PROMPT
        self.contact_prompt = DEFAULT_CONTACT_PROMPT
        self.services_prompt = DEFAULT_SERVICES_PROMPT
        logger.info("AIWebScraper initialized with model: %s", self.model)

    def _initial_model(self) -> str:
        if self.model_selector:
            return self.model_selector.select_model_for_use_case("company_basic", self.priority)
        return getattr(settings, "ollama_model", "llama3.2")

    def _record_model_usage(self, model: str, latency: float) -> None:
        usage = self._stats["model_usage"].setdefault(model, {"count": 0, "latency": []})
        usage["count"] += 1
        usage["latency"].append(latency)

    def _select_model(self, content: str, use_case: str, complexity: str = "medium") -> str:
        if not self.model_selector:
            return self.model
        selected = auto_select_model(len(content), complexity, self.priority, self.model_selector)
        logger.debug("Auto-selected model '%s' for use case '%s'", selected, use_case)
        return selected

    def _fetch_content(self, url: str) -> str | None:
        """Fetch and extract content from URL using Trafilatura"""
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning(f"Could not fetch URL: {url}")
                return None

            text = trafilatura.extract(downloaded)
            if not text:
                logger.warning(f"Could not extract content from: {url}")
                return None

            return text
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}")
            return None

    def _resolve_prompt(
        self, use_case: str, model_name: str, default_prompt: str
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {"template": default_prompt}
        if self.use_prompt_library and self.model_selector:
            prompt_entry = self.model_selector.get_optimized_prompt(use_case, model_name)
            if isinstance(prompt_entry, dict):
                resolved_template = prompt_entry.get("template") or default_prompt
                resolved["template"] = resolved_template
                system_message = prompt_entry.get("system_message")
                if isinstance(system_message, str) and system_message.strip():
                    resolved["system_message"] = system_message.strip()
                parameters = prompt_entry.get("parameters")
                if isinstance(parameters, dict) and parameters:
                    resolved["parameters"] = parameters
                examples = prompt_entry.get("examples")
                if isinstance(examples, list) and examples:
                    resolved["examples"] = examples
                return resolved
            if isinstance(prompt_entry, str):
                resolved["template"] = prompt_entry
                return resolved
        return resolved

    def _build_messages(
        self, prompt: str, content: str, system_message: Optional[str] = None
    ) -> list[dict[str, str]]:
        limited_content = content[: self.max_content_length]
        if "{{content}}" in prompt:
            user_content = prompt.replace("{{content}}", limited_content)
        else:
            user_content = f"{prompt}\n\nWebsite Content:\n{limited_content}"

        messages: list[dict[str, str]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_content})
        return messages

    def _ollama_options(
        self, model_name: str, prompt_parameters: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if self.model_selector:
            model_config = self.model_selector.get_model_config(model_name)
            options.update(model_config)
        if prompt_parameters:
            options.update(
                {k: v for k, v in prompt_parameters.items() if k in ALLOWED_OLLAMA_OPTIONS}
            )
        if self.temperature is not None:
            options["temperature"] = self.temperature
        return {k: v for k, v in options.items() if k in ALLOWED_OLLAMA_OPTIONS and v is not None}

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            candidate = text[start:end]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            candidate = text[start:end]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_response": text}

    def _query_ollama(
        self,
        prompt: str,
        content: str,
        model_name: Optional[str] = None,
        *,
        system_message: Optional[str] = None,
        prompt_parameters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Query Ollama with prompt and content"""
        model_to_use = model_name or self.model
        messages = self._build_messages(prompt, content, system_message=system_message)
        options = self._ollama_options(model_to_use, prompt_parameters)

        start_time = time.perf_counter()
        try:
            response = ollama.chat(model=model_to_use, messages=messages, options=options)
        except Exception as exc:
            self._stats["errors"] += 1
            logger.error("Error querying Ollama (%s): %s", model_to_use, exc)
            return {"error": str(exc)}

        latency = time.perf_counter() - start_time
        self._stats["requests"] += 1
        self._stats["latencies"].append(latency)
        self._record_model_usage(model_to_use, latency)

        message = response.get("message", {})
        result_text = message.get("content", "")
        parsed = self._parse_json_response(result_text)
        if "raw_response" in parsed:
            parsed.setdefault("model_used", model_to_use)
            return parsed
        parsed.setdefault("model_used", model_to_use)
        return parsed

    def extract_company_data(self, url: str) -> dict[str, Any]:
        """
        Extract comprehensive company data from website.

        Args:
            url: Company website URL

        Returns:
            Dictionary with extracted company data
        """
        prompt = self.company_prompt

        try:
            logger.info(f"Extracting company data from: {url}")

            content = self._fetch_content(url)
            if not content:
                self._stats["errors"] += 1
                return {"error": "Could not fetch content", "url": url}

            model_name = self._select_model(content, "company_basic", "medium")
            prompt_entry = self._resolve_prompt("company_basic", model_name, prompt)
            prompt_template = prompt_entry["template"]
            result = self._query_ollama(
                prompt_template,
                content,
                model_name=model_name,
                system_message=prompt_entry.get("system_message"),
                prompt_parameters=prompt_entry.get("parameters"),
            )
            if isinstance(result, dict):
                result.setdefault("source_url", url)
            logger.info(f"Successfully extracted data from {url}")
            return result

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error extracting company data from {url}: {e}")
            return {"error": str(e), "url": url}

    def extract_employees(self, url: str) -> list[dict[str, str]]:
        """
        Extract only employee information from website.

        Args:
            url: Company website URL (usually /team or /about page)

        Returns:
            List of employee dictionaries
        """
        prompt = self.employees_prompt

        try:
            logger.info(f"Extracting employees from: {url}")

            content = self._fetch_content(url)
            if not content:
                self._stats["errors"] += 1
                return []

            model_name = self._select_model(content, "employees", "complex")
            prompt_entry = self._resolve_prompt("employees", model_name, prompt)
            prompt_template = prompt_entry["template"]
            result = self._query_ollama(
                prompt_template,
                content,
                model_name=model_name,
                system_message=prompt_entry.get("system_message"),
                prompt_parameters=prompt_entry.get("parameters"),
            )

            if isinstance(result, dict):
                if "employees" in result:
                    result = result["employees"]
                elif "error" in result:
                    return []
                else:
                    result = [result]
            elif not isinstance(result, list):
                result = []

            logger.info(f"Found {len(result)} employees from {url}")
            return result

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error extracting employees from {url}: {e}")
            return []

    def extract_contact_info(self, url: str) -> dict[str, str]:
        """
        Extract contact information from website.

        Args:
            url: Company website URL

        Returns:
            Dictionary with contact information
        """
        prompt = self.contact_prompt

        try:
            logger.info(f"Extracting contact info from: {url}")

            content = self._fetch_content(url)
            if not content:
                self._stats["errors"] += 1
                return {"error": "Could not fetch content"}

            model_name = self._select_model(content, "contact_info", "simple")
            prompt_entry = self._resolve_prompt("contact_info", model_name, prompt)
            prompt_template = prompt_entry["template"]
            result = self._query_ollama(
                prompt_template,
                content,
                model_name=model_name,
                system_message=prompt_entry.get("system_message"),
                prompt_parameters=prompt_entry.get("parameters"),
            )
            logger.info(f"Successfully extracted contact info from {url}")
            return result

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error extracting contact info from {url}: {e}")
            return {"error": str(e)}

    def extract_services(self, url: str) -> list[str]:
        """
        Extract services/products offered by company.

        Args:
            url: Company website URL

        Returns:
            List of services/products
        """
        prompt = self.services_prompt

        try:
            logger.info(f"Extracting services from: {url}")

            content = self._fetch_content(url)
            if not content:
                self._stats["errors"] += 1
                return []

            model_name = self._select_model(content, "services", "medium")
            prompt_entry = self._resolve_prompt("services", model_name, prompt)
            prompt_template = prompt_entry["template"]
            result = self._query_ollama(
                prompt_template,
                content,
                model_name=model_name,
                system_message=prompt_entry.get("system_message"),
                prompt_parameters=prompt_entry.get("parameters"),
            )

            if isinstance(result, dict):
                if "services" in result:
                    result = result["services"]
                elif "error" in result:
                    return []
                else:
                    result = list(result.values())
            elif not isinstance(result, list):
                result = []

            logger.info(f"Found {len(result)} services from {url}")
            return result

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error extracting services from {url}: {e}")
            return []

    def extract_custom(self, url: str, prompt: str, use_case: str = "custom") -> Any:
        """
        Extract custom data using a custom prompt.

        Args:
            url: Website URL
            prompt: Custom extraction prompt
            use_case: Use-case label for model selection

        Returns:
            Extracted data (format depends on prompt)
        """
        try:
            logger.info(f"Extracting custom data from: {url}")

            content = self._fetch_content(url)
            if not content:
                return {"error": "Could not fetch content"}

            model_name = self._select_model(content, use_case, "medium")
            result = self._query_ollama(prompt, content, model_name=model_name)
            logger.info(f"Successfully extracted custom data from {url}")
            return result

        except Exception as e:
            logger.error(f"Error extracting custom data from {url}: {e}")
            return {"error": str(e)}

    def get_benchmark_stats(self) -> dict[str, Any]:
        """Return aggregated statistics recorded during runtime."""

        latencies = self._stats.get("latencies", [])
        if latencies:
            latency_p50 = self._percentile(latencies, 50)
            latency_p95 = self._percentile(latencies, 95)
            latency_p99 = self._percentile(latencies, 99)
            mean_latency = sum(latencies) / len(latencies)
        else:
            latency_p50 = latency_p95 = latency_p99 = mean_latency = 0.0

        return {
            "requests": self._stats.get("requests", 0),
            "errors": self._stats.get("errors", 0),
            "model_usage": self._stats.get("model_usage", {}),
            "latency_mean": mean_latency,
            "latency_p50": latency_p50,
            "latency_p95": latency_p95,
            "latency_p99": latency_p99,
        }

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        data = sorted(values)
        k = (len(data) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data[int(k)]
        return data[f] * (c - k) + data[c] * (k - f)


# Convenience function for quick usage
def scrape_company(url: str, model: str = "llama3.2") -> dict[str, Any]:
    """
    Quick function to scrape company data.

    Args:
        url: Company website URL
        model: Ollama model to use

    Returns:
        Dictionary with company data
    """
    scraper = AIWebScraper(model=model)
    return scraper.extract_company_data(url)
