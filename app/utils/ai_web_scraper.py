"""
AI-Powered Web Scraper using Scrapegraph-AI + Ollama

This module provides intelligent web scraping capabilities using AI to extract
structured data from company websites, including employee information, contact
details, services, and more.
"""

import json
from typing import Dict, Any, List, Optional
from scrapegraphai.graphs import SmartScraperGraph
from app.utils.logger import logger


class AIWebScraper:
    """
    AI-powered web scraper using Scrapegraph-AI with Ollama.
    
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
        model: str = "ollama/llama3.2",
        temperature: float = 0,
        base_url: str = "http://localhost:11434"
    ):
        """
        Initialize AI Web Scraper.
        
        Args:
            model: Ollama model to use (default: llama3.2)
            temperature: LLM temperature (0 = deterministic)
            base_url: Ollama API base URL
        """
        self.model = model
        self.config = {
            "llm": {
                "model": model,
                "temperature": temperature,
                "base_url": base_url,
            },
            "verbose": False,
            "headless": True,
        }
        logger.info(f"AIWebScraper initialized with model: {model}")
    
    def extract_company_data(self, url: str) -> Dict[str, Any]:
        """
        Extract comprehensive company data from website.
        
        Args:
            url: Company website URL
            
        Returns:
            Dictionary with extracted company data:
            {
                "company_name": str,
                "employees": List[Dict],
                "contact": Dict,
                "services": List[str],
                "about": str
            }
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
            
            smart_scraper = SmartScraperGraph(
                prompt=prompt,
                source=url,
                config=self.config
            )
            
            result = smart_scraper.run()
            
            # Parse result if it's a string
            if isinstance(result, str):
                result = json.loads(result)
            
            logger.info(f"Successfully extracted data from {url}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting company data from {url}: {e}")
            return {
                "error": str(e),
                "url": url
            }
    
    def extract_employees(self, url: str) -> List[Dict[str, str]]:
        """
        Extract only employee information from website.
        
        Args:
            url: Company website URL (usually /team or /about page)
            
        Returns:
            List of employee dictionaries with name, position, email, phone
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
            
            smart_scraper = SmartScraperGraph(
                prompt=prompt,
                source=url,
                config=self.config
            )
            
            result = smart_scraper.run()
            
            # Parse result if it's a string
            if isinstance(result, str):
                result = json.loads(result)
            
            # Ensure it's a list
            if isinstance(result, dict) and "employees" in result:
                result = result["employees"]
            elif not isinstance(result, list):
                result = [result]
            
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
            Dictionary with email, phone, address, social media
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
            
            smart_scraper = SmartScraperGraph(
                prompt=prompt,
                source=url,
                config=self.config
            )
            
            result = smart_scraper.run()
            
            # Parse result if it's a string
            if isinstance(result, str):
                result = json.loads(result)
            
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
            
            smart_scraper = SmartScraperGraph(
                prompt=prompt,
                source=url,
                config=self.config
            )
            
            result = smart_scraper.run()
            
            # Parse result if it's a string
            if isinstance(result, str):
                result = json.loads(result)
            
            # Ensure it's a list
            if isinstance(result, dict) and "services" in result:
                result = result["services"]
            elif not isinstance(result, list):
                result = [result]
            
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
            
            smart_scraper = SmartScraperGraph(
                prompt=prompt,
                source=url,
                config=self.config
            )
            
            result = smart_scraper.run()
            
            # Try to parse as JSON
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass  # Keep as string if not valid JSON
            
            logger.info(f"Successfully extracted custom data from {url}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting custom data from {url}: {e}")
            return {"error": str(e)}


# Convenience function for quick usage
def scrape_company(url: str, model: str = "ollama/llama3.2") -> Dict[str, Any]:
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
