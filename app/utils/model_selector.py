"""Model selection and prompt optimization helpers for Ollama scrapers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_ALLOWED_OLLAMA_OPTIONS = {
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


def _load_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to load JSON from %s: %s", path, exc)
        return {}


@dataclass
class ModelCharacteristics:
    name: str
    speed: str
    accuracy: str
    resource_cost: str
    metrics: Dict[str, Any]


class ModelSelector:
    """Centralised access to benchmark-informed model and prompt choices."""

    def __init__(
        self,
        benchmark_results_path: Optional[str] = None,
        prompt_library_path: Optional[str] = None,
    ) -> None:
        benchmark_default = getattr(
            settings,
            "ollama_benchmark_results_path",
            "data/benchmarks/ollama_results.json",
        )
        prompt_default = getattr(
            settings,
            "ollama_prompt_library_path",
            "data/prompts/optimized_prompts.json",
        )

        self.benchmark_path = Path(benchmark_results_path or benchmark_default)
        self.prompt_library_path = Path(prompt_library_path or prompt_default)

        self.benchmark_results = _load_json_file(self.benchmark_path)
        self.prompt_library = _load_json_file(self.prompt_library_path)

        self.default_model = getattr(settings, "ollama_model", "llama3.2")
        self.fast_model = getattr(settings, "ollama_model_fast", "llama3.2:1b")
        self.accurate_model = getattr(settings, "ollama_model_accurate", "llama3.2")
        self.balanced_model = getattr(settings, "ollama_model_balanced", "mistral")
        self.resource_efficient_model = getattr(
            settings, "ollama_model_resource_efficient", "qwen2.5"
        )

        self.model_configs: Dict[str, Dict[str, Any]] = {
            "llama3.2": {
                "temperature": 0.15,
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": 2048,
            },
            "llama3.2:1b": {
                "temperature": 0.05,
                "top_p": 0.85,
                "top_k": 40,
                "num_predict": 1024,
            },
            "mistral": {
                "temperature": 0.1,
                "top_p": 0.9,
                "top_k": 50,
                "num_predict": 1536,
            },
            "qwen2.5": {
                "temperature": 0.1,
                "top_p": 0.85,
                "top_k": 45,
                "num_predict": 1536,
            },
            "codellama": {
                "temperature": 0.05,
                "top_p": 0.8,
                "top_k": 30,
                "num_predict": 1024,
            },
        }
        self.model_characteristics = self._build_characteristics()

    def _build_characteristics(self) -> Dict[str, ModelCharacteristics]:
        defaults: Dict[str, ModelCharacteristics] = {}
        defaults["llama3.2"] = ModelCharacteristics(
            name="llama3.2",
            speed="medium",
            accuracy="high",
            resource_cost="high",
            metrics=self.benchmark_results.get("llama3.2", {}),
        )
        defaults["llama3.2:1b"] = ModelCharacteristics(
            name="llama3.2:1b",
            speed="high",
            accuracy="medium",
            resource_cost="low",
            metrics=self.benchmark_results.get("llama3.2:1b", {}),
        )
        defaults["mistral"] = ModelCharacteristics(
            name="mistral",
            speed="medium",
            accuracy="medium_high",
            resource_cost="medium",
            metrics=self.benchmark_results.get("mistral", {}),
        )
        defaults["qwen2.5"] = ModelCharacteristics(
            name="qwen2.5",
            speed="medium_high",
            accuracy="medium_high",
            resource_cost="medium",
            metrics=self.benchmark_results.get("qwen2.5", {}),
        )
        defaults["codellama"] = ModelCharacteristics(
            name="codellama",
            speed="low",
            accuracy="low",
            resource_cost="high",
            metrics=self.benchmark_results.get("codellama", {}),
        )
        return defaults

    def select_model_for_use_case(self, use_case: str, priority: str = "balanced") -> str:
        use_case = use_case or "company_basic"
        priority = (priority or "balanced").lower()
        use_case_defaults = {
            "company_basic": "speed",
            "company_detailed": "accuracy",
            "employees": "balanced",
            "services": "speed",
            "contact_info": "balanced",
            "custom": priority,
        }
        priority_map = {
            "speed": self.fast_model,
            "accuracy": self.accurate_model,
            "balanced": self.balanced_model,
            "resource_efficient": self.resource_efficient_model,
        }

        resolved_priority = use_case_defaults.get(use_case, "balanced")
        if priority != "balanced":
            resolved_priority = priority

        model = priority_map.get(resolved_priority)
        if model:
            return model

        return self.default_model

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        config = dict(self.model_configs.get(model_name, {}))
        benchmark_config = self.benchmark_results.get(model_name, {}).get("recommended_config")
        if isinstance(benchmark_config, dict):
            config.update({k: v for k, v in benchmark_config.items() if v is not None})
        return {k: v for k, v in config.items() if k in _ALLOWED_OLLAMA_OPTIONS}

    def get_optimized_prompt(self, use_case: str, model_name: str) -> Optional[Dict[str, Any]]:
        prompts_for_case = self.prompt_library.get(use_case)
        if not isinstance(prompts_for_case, dict):
            return None
        model_prompt = prompts_for_case.get(model_name)
        if isinstance(model_prompt, dict):
            return model_prompt
        default_prompt = prompts_for_case.get("default")
        if isinstance(default_prompt, dict):
            return default_prompt
        if isinstance(default_prompt, str):
            return {"template": default_prompt}
        return None

    def get_benchmark_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        for name, characteristics in self.model_characteristics.items():
            summary[name] = {
                "speed": characteristics.speed,
                "accuracy": characteristics.accuracy,
                "resource_cost": characteristics.resource_cost,
                "metrics": characteristics.metrics,
            }
        return summary


def auto_select_model(
    content_length: int,
    complexity: str,
    priority: str = "balanced",
    selector: Optional[ModelSelector] = None,
) -> str:
    if selector is None:
        selector = ModelSelector()

    complexity = (complexity or "medium").lower()
    priority = (priority or "balanced").lower()

    if content_length < 1000 and complexity == "simple":
        if priority == "accuracy":
            return selector.accurate_model
        return selector.fast_model

    if content_length > 5000 or complexity == "complex":
        if priority == "speed":
            return selector.balanced_model
        return selector.accurate_model

    if priority == "speed":
        return selector.fast_model
    if priority == "accuracy":
        return selector.accurate_model
    if priority == "resource_efficient":
        return selector.resource_efficient_model

    return selector.balanced_model


__all__ = ["ModelSelector", "auto_select_model"]
