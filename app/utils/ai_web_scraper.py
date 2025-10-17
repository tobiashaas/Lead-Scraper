"""
AI-Powered Web Scraper using Trafilatura + Ollama

This module provides intelligent web scraping capabilities using AI to extract
structured data from company websites, including employee information, contact
details, services, and more.

Uses Trafilatura for content extraction and Ollama for AI-powered structuring.
Compatible with Python 3.13!
"""

import json
from typing import Dict, Any, List, Optional
import trafilatura
import ollama
from app.utils.logger import logger


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
        model: str = "llama3.2",
        temperature: float = 0,
        max_content_length: int = 10000
    ):
        """
        Initialize AI Web Scraper.

        Args:
            model: Ollama model to use (default: llama3.2)
            temperature: LLM temperature (0 = deterministic)
            max_content_length: Max characters to send to LLM
        """
        self.model = model
        self.temperature = temperature
        self.max_content_length = max_content_length
        logger.info(f"AIWebScraper initialized with model: {model}")

    def _fetch_content(self, url: str) -> Optional[str]:
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

    def _query_ollama(self, prompt: str, content: str) -> Dict[str, Any]:
        """Query Ollama with prompt and content"""
        try:
            # Limit content length
            limited_content = content[:self.max_content_length]

            response = ollama.chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': f'{prompt}\n\nWebsite Content:\n{limited_content}'
                }],
                options={'temperature': self.temperature}
            )

            result_text = response['message']['content']

            # Try to extract JSON from response
            try:
                # Find JSON in response
                start = result_text.find('{')
                end = result_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = result_text[start:end]
                    return json.loads(json_str)

                # Try to find JSON array
                start = result_text.find('[')
                end = result_text.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = result_text[start:end]
                    return json.loads(json_str)

                # Try to parse entire response
                return json.loads(result_text)
            except Exception:
                # If parsing fails, return raw text
                return {"raw_response": result_text}

        except Exception as e:
            logger.error(f"Error querying Ollama: {e}")
            return {"error": str(e)}

    def extract_company_data(self, url: str) -> Dict[str, Any]:
        """
        Extract comprehensive company data from website.

        Args:
            url: Company website URL

        Returns:
            Dictionary with extracted company data
        """
        prompt = """
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

        try:
            logger.info(f"Extracting company data from: {url}")

            content = self._fetch_content(url)
            if not content:
                return {"error": "Could not fetch content", "url": url}

            result = self._query_ollama(prompt, content)
            logger.info(f"Successfully extracted data from {url}")
            return result

        except Exception as e:
            logger.error(f"Error extracting company data from {url}: {e}")
            return {"error": str(e), "url": url}

    def extract_employees(self, url: str) -> List[Dict[str, str]]:
        """
        Extract only employee information from website.

        Args:
            url: Company website URL (usually /team or /about page)

        Returns:
            List of employee dictionaries
        """
        prompt = """
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

        try:
            logger.info(f"Extracting employees from: {url}")

            content = self._fetch_content(url)
            if not content:
                return []
            
            result = self._query_ollama(prompt, content)
            
            # Ensure it's a list
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
            logger.error(f"Error extracting employees from {url}: {e}")
            return []

    def extract_contact_info(self, url: str) -> Dict[str, str]:
        """
        Extract contact information from website.

        Args:
            url: Company website URL

        Returns:
            Dictionary with contact information
        """
        prompt = """
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

        try:
            logger.info(f"Extracting contact info from: {url}")

            content = self._fetch_content(url)
            if not content:
                return {"error": "Could not fetch content"}
            
            result = self._query_ollama(prompt, content)
            logger.info(f"Successfully extracted contact info from {url}")
            return result

        except Exception as e:
            logger.error(f"Error extracting contact info from {url}: {e}")
            return {"error": str(e)}

    def extract_services(self, url: str) -> List[str]:
        """
        Extract services/products offered by company.

        Args:
            url: Company website URL

        Returns:
            List of services/products
        """
        prompt = """
        Extract all services, products, or solutions offered by this company.

        Return as JSON array of strings:
        ["Service 1", "Service 2", "Service 3"]

        Return ONLY the JSON array.
        """

        try:
            logger.info(f"Extracting services from: {url}")

            content = self._fetch_content(url)
            if not content:
                return []
            
            result = self._query_ollama(prompt, content)
            
            # Ensure it's a list
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
            logger.error(f"Error extracting services from {url}: {e}")
            return []

    def extract_custom(self, url: str, prompt: str) -> Any:
        """
        Extract custom data using a custom prompt.

        Args:
            url: Website URL
            prompt: Custom extraction prompt

        Returns:
            Extracted data (format depends on prompt)
        """
        try:
            logger.info(f"Extracting custom data from: {url}")

            content = self._fetch_content(url)
            if not content:
                return {"error": "Could not fetch content"}
            
            result = self._query_ollama(prompt, content)
            logger.info(f"Successfully extracted custom data from {url}")
            return result

        except Exception as e:
            logger.error(f"Error extracting custom data from {url}: {e}")
            return {"error": str(e)}


# Convenience function for quick usage
def scrape_company(url: str, model: str = "llama3.2") -> Dict[str, Any]:
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
