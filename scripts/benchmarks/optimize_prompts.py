"""Prompt optimization harness for Ollama-based scrapers.

This script evaluates multiple prompt variants via A/B testing against a shared
set of benchmark cases, recording accuracy and latency metrics per variant and
model. The aggregated results are exported for downstream consumption and used
for auto-selection in production scraping flows.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from scripts.benchmarks.benchmark_ollama_models import (
    BENCHMARK_DIR,
    BenchmarkTestCase,
    ModelBenchmark,
    _ensure_dir,
    _safe_json_loads,
)

PROMPT_LIBRARY_PATH = Path("data/prompts/optimized_prompts.json")
PROMPT_SCORES_PATH = Path("data/benchmarks/prompt_scores.json")
PROMPT_REPORT_PATH = Path("data/benchmarks/prompt_optimization_report.md")


@dataclass
class PromptVariant:
    name: str
    prompt_template: str
    system_message: Optional[str] = None
    temperature: Optional[float] = None
    format_instruction: Optional[str] = None
    examples: Optional[List[Dict[str, Any]]] = None

    def render(self, content: str) -> str:
        return self.prompt_template.replace("{{content}}", content)


def _load_baseline_prompts() -> Dict[str, str]:
    from app.utils.ai_web_scraper import AIWebScraper

    scraper = AIWebScraper(model="llama3.2", use_model_selector=False)
    return {
        "company_basic": getattr(scraper, "company_prompt", ""),
        "employees": getattr(scraper, "employees_prompt", ""),
        "contact_info": getattr(scraper, "contact_prompt", ""),
        "services": getattr(scraper, "services_prompt", ""),
    }


def _load_prompt_variants(use_case: str) -> List[PromptVariant]:
    baseline_prompts = _load_baseline_prompts()
    baseline = baseline_prompts.get(use_case, "Extract data: {{content}}")
    return [
        PromptVariant(name="baseline", prompt_template=baseline),
        PromptVariant(
            name="structured",
            prompt_template=(
                "You are an information extraction system. Extract ONLY verifiable "
                "facts from the content below and respond with valid JSON using the "
                "fields defined.\n"
                "Use this structure: {\n"
                "  \"company_name\": string | null,\n"
                "  \"address\": string | null,\n"
                "  \"phone\": string | null,\n"
                "  \"email\": string | null,\n"
                "  \"website\": string | null,\n"
                "  \"services\": [string],\n"
                "  \"directors\": [{\"name\": string, \"title\": string | null}]\n"
                "}\n"
                "Do not include inferred information. Content: {{content}}"
            ),
            format_instruction="Return valid JSON with the specified keys only.",
        ),
        PromptVariant(
            name="few_shot",
            prompt_template=(
                "You are an expert data extraction assistant. Follow the examples "
                "closely and extract only the facts from the content.\n"
                "Example 1 Input: <html><h1>Alpha GmbH</h1><p>Services: IT Consulting</p></html>\n"
                "Example 1 Output: {\"company_name\": \"Alpha GmbH\", \"services\": [\"IT Consulting\"], \"directors\": []}\n"
                "Example 2 Input: <html><h1>Beta AG</h1><p>CEO: Dr. Jane Doe</p></html>\n"
                "Example 2 Output: {\"company_name\": \"Beta AG\", \"directors\": [{\"name\": \"Dr. Jane Doe\", \"title\": \"CEO\"}]}\n"
                "Now extract from: {{content}}"
            ),
            format_instruction="Respond with valid JSON only.",
        ),
        PromptVariant(
            name="chain_of_thought",
            prompt_template=(
                "Carefully analyse the content and think through each field step by "
                "step before returning the final JSON.\n"
                "1. Identify the company name if available.\n"
                "2. Locate contact details (address, phone, email, website).\n"
                "3. Extract services listed.\n"
                "4. Extract directors or key people.\n"
                "5. Ensure every field is based on explicit text.\n"
                "6. Return the final JSON with these keys only.\n"
                "Content: {{content}}"
            ),
        ),
        PromptVariant(
            name="minimal",
            prompt_template="Return JSON of company facts: {{content}}",
        ),
    ]


def evaluate_prompt_variant(
    variant: PromptVariant,
    model: str,
    test_cases: Sequence[BenchmarkTestCase],
) -> Dict[str, float]:
    latencies: List[float] = []
    f1_scores: List[float] = []
    hallucinations: List[float] = []

    from app.utils.ai_web_scraper import AIWebScraper

    scraper = AIWebScraper(model=model, use_model_selector=False)

    for case in test_cases:
        prompt = variant.render(case.html_content)
        start = time.perf_counter()
        prompt_parameters: Dict[str, Any] | None = None
        if variant.temperature is not None:
            prompt_parameters = {"temperature": variant.temperature}

        response = scraper._query_ollama(
            prompt,
            case.html_content,
            model_name=model,
            system_message=variant.system_message,
            prompt_parameters=prompt_parameters,
        )
        latency = time.perf_counter() - start
        latencies.append(latency)

        if isinstance(response, dict):
            data = response
        elif isinstance(response, str):
            data = scraper._parse_json_response(response)
        else:
            data = {}

        if not isinstance(data, dict):
            data = {}

        metrics = ModelBenchmark.calculate_quality_metrics(data, case.expected_data)
        f1_scores.append(metrics.get("f1", 0.0))
        hallucinations.append(ModelBenchmark._estimate_hallucination_rate(data, case.expected_data))

    return {
        "prompt": variant.name,
        "model": model,
        "f1_mean": statistics.mean(f1_scores) if f1_scores else 0.0,
        "latency_mean": statistics.mean(latencies) if latencies else 0.0,
        "hallucination_mean": statistics.mean(hallucinations) if hallucinations else 1.0,
    }


def run_prompt_optimization(
    use_case: str,
    model: str,
    iterations: int,
    output: str,
) -> List[Dict[str, float]]:
    test_cases = BenchmarkTestCase.load_all()
    variants = _load_prompt_variants(use_case)

    scores: List[Dict[str, float]] = []
    for variant in variants:
        variant_scores = []
        for _ in range(iterations):
            variant_scores.append(evaluate_prompt_variant(variant, model, test_cases))
        aggregated = {
            "prompt": variant.name,
            "model": model,
            "f1_mean": statistics.mean(s["f1_mean"] for s in variant_scores),
            "latency_mean": statistics.mean(s["latency_mean"] for s in variant_scores),
            "hallucination_mean": statistics.mean(s["hallucination_mean"] for s in variant_scores),
        }
        scores.append(aggregated)

    best = max(scores, key=lambda s: s["f1_mean"] - s["hallucination_mean"])
    best_variant = next(v for v in variants if v.name == best["prompt"])
    _persist_prompt_results(use_case, model, scores, output, best, best_variant)
    return scores


def _persist_prompt_results(use_case: str, model: str, scores: List[Dict[str, float]], output: str, best: Dict[str, float], best_variant: PromptVariant) -> None:
    if output in {"json", "both"}:
        _ensure_dir(PROMPT_SCORES_PATH)
        score_payload: Dict[str, Any] = {}
        if PROMPT_SCORES_PATH.exists():
            score_payload = json.loads(PROMPT_SCORES_PATH.read_text(encoding="utf-8"))
        score_payload.setdefault(use_case, {})[model] = scores
        PROMPT_SCORES_PATH.write_text(json.dumps(score_payload, indent=2), encoding="utf-8")

        _ensure_dir(PROMPT_LIBRARY_PATH)
        prompt_library: Dict[str, Any] = {}
        if PROMPT_LIBRARY_PATH.exists():
            prompt_library = json.loads(PROMPT_LIBRARY_PATH.read_text(encoding="utf-8"))
        use_case_library = prompt_library.setdefault(use_case, {})
        existing_entry = use_case_library.get(model)
        entry: Dict[str, Any]
        if isinstance(existing_entry, dict):
            entry = dict(existing_entry)
        else:
            entry = {}

        entry["template"] = best_variant.prompt_template

        if best_variant.system_message:
            entry["system_message"] = best_variant.system_message

        parameters: Dict[str, Any] = dict(entry.get("parameters") or {})
        if best_variant.temperature is not None:
            parameters["temperature"] = best_variant.temperature
        if parameters:
            entry["parameters"] = parameters
        if best_variant.examples:
            entry["examples"] = best_variant.examples
        elif "examples" in entry and not entry["examples"]:
            entry.pop("examples")
        use_case_library[model] = entry
        PROMPT_LIBRARY_PATH.write_text(json.dumps(prompt_library, indent=2), encoding="utf-8")

    if output in {"markdown", "both"}:
        _ensure_dir(PROMPT_REPORT_PATH)
        lines = [
            "# Prompt Optimization Report",
            "",
            f"Use case: `{use_case}`",
            f"Model: `{model}`",
            "",
            "| Prompt | F1 Mean | Latency Mean (s) | Hallucination Mean |",
            "| --- | --- | --- | --- |",
        ]
        for score in scores:
            lines.append(
                "| {prompt} | {f1:.2%} | {latency:.2f} | {hall:.2%} |".format(
                    prompt=score["prompt"],
                    f1=score["f1_mean"],
                    latency=score["latency_mean"],
                    hall=score["hallucination_mean"],
                )
            )
        PROMPT_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize scraping prompts via A/B testing.")
    parser.add_argument("--use-case", default="company_basic", help="Use case to optimize prompts for.")
    parser.add_argument("--model", default="llama3.2", help="Model to use for optimization runs.")
    parser.add_argument("--iterations", type=int, default=1, help="Number of repetitions per prompt variant.")
    parser.add_argument(
        "--output",
        choices=["json", "markdown", "both", "none"],
        default="both",
        help="Output format for optimization results.",
    )
    return parser.parse_args(args)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    scores = run_prompt_optimization(args.use_case, args.model, args.iterations, args.output)
    best = max(scores, key=lambda s: s["f1_mean"] - s["hallucination_mean"])
    print(
        "Best prompt: {prompt} (F1={f1:.2%}, Latency={latency:.2f}s, Hallucination={hall:.2%})".format(
            prompt=best["prompt"],
            f1=best["f1_mean"],
            latency=best["latency_mean"],
            hall=best["hallucination_mean"],
        )
    )
    if args.output == "none":
        print("Results not persisted (output=none).")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
