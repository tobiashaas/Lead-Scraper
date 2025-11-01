"""Comprehensive benchmarking harness for Ollama-backed scrapers.

This module provides a CLI for running systematic benchmarks across multiple
Ollama models and prompt variants. It collects quality metrics (precision,
recall, F1) alongside performance metrics (latency percentiles, throughput,
memory usage) and exports consolidated reports for downstream consumption.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from app.utils.model_selector import ModelSelector

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore


# Avoid importing heavy dependencies at module import when running help()
ScraperFactory = Callable[[str], Any]


BENCHMARK_DIR = Path("data/benchmarks")
DEFAULT_TEST_CASES_FILE = BENCHMARK_DIR / "test_cases.json"
BENCHMARK_RESULTS_FILE = BENCHMARK_DIR / "ollama_results.json"
BENCHMARK_DETAILS_FILE = BENCHMARK_DIR / "benchmark_details.json"
BENCHMARK_REPORT_FILE = BENCHMARK_DIR / "benchmark_report.md"

_ALLOWED_OLLAMA_OPTIONS = {
    "temperature",
    "top_p",
    "top_k",
    "repeat_penalty",
    "presence_penalty",
    "frequency_penalty",
    "num_ctx",
    "num_predict",
}


@dataclass
class BenchmarkTestCase:
    """Represents an individual benchmark scenario with ground truth data."""

    id: str
    name: str
    html_content: str
    expected_data: Dict[str, Any]
    complexity: str = "medium"
    content_type: str = "company_page"
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkTestCase":
        required = {"id", "name", "html_content", "expected_data"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"Missing required fields in test case: {sorted(missing)}")
        html_content = data["html_content"]
        if html_content.strip().startswith("file://"):
            path = html_content[7:]
            html_content = Path(path).read_text(encoding="utf-8")
        return cls(
            id=data["id"],
            name=data["name"],
            html_content=html_content,
            expected_data=data["expected_data"],
            complexity=data.get("complexity", "medium"),
            content_type=data.get("content_type", "company_page"),
            source=data.get("source"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def load_all(cls, path: Path = DEFAULT_TEST_CASES_FILE) -> List["BenchmarkTestCase"]:
        if not path.exists():
            raise FileNotFoundError(f"Benchmark test cases file not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [cls.from_dict(item) for item in raw]


def _load_scraper(scraper_name: str, selector: Optional[ModelSelector]) -> Any:
    del selector  # selector is unused in benchmark factory but retained for future expansion
    from app.utils.ai_web_scraper import AIWebScraper

    def scraper_factory(model: str) -> Any:
        if scraper_name == "ai_web_scraper":
            return AIWebScraper(
                model=model,
                use_model_selector=False,
            )
        if scraper_name == "crawl4ai_scraper":
            raise ValueError("crawl4ai_scraper benchmarking requires async runner support")
        raise ValueError(f"Unsupported scraper: {scraper_name}")

    return scraper_factory


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_json_loads(payload: str) -> Tuple[bool, Optional[Any]]:
    try:
        return True, json.loads(payload)
    except json.JSONDecodeError:
        return False, None


def _summarize_errors(results: Dict[str, List[ExtractionResult]]) -> Tuple[int, Dict[str, int]]:
    total_errors = 0
    per_case: Dict[str, int] = {}
    for case_id, case_results in results.items():
        case_error_count = sum(1 for result in case_results if result.error)
        if case_error_count:
            per_case[case_id] = case_error_count
            total_errors += case_error_count
    return total_errors, per_case


def _recommend_config(metrics: AggregatedMetrics) -> Dict[str, Any]:
    """Derive a recommended Ollama configuration based on benchmark metrics."""

    config: Dict[str, Any] = {
        "temperature": 0.1,
        "top_p": 0.9,
        "num_predict": 1024,
        "repeat_penalty": 1.05,
    }

    if metrics.hallucination_rate > 0.15:
        config["temperature"] = 0.05
        config["top_p"] = 0.85
        config["repeat_penalty"] = 1.15

    if metrics.completeness < 0.55:
        config["num_predict"] = 1536
        config.setdefault("top_k", 60)

    if metrics.latency_p95 > 12:
        config["num_predict"] = min(config.get("num_predict", 1024), 1024)
        config["top_p"] = min(config.get("top_p", 0.9), 0.88)

    if metrics.latency_p95 < 6 and metrics.f1 > 0.65:
        config["temperature"] = min(config.get("temperature", 0.1) + 0.05, 0.25)

    return {k: v for k, v in config.items() if k in _ALLOWED_OLLAMA_OPTIONS}


@dataclass
class ExtractionResult:
    latency: float
    response: Any
    raw_response: str
    quality_metrics: Dict[str, float]
    json_valid: bool
    hallucination_rate: float
    tokens_per_second: float
    memory_used_mb: Optional[float]
    error: Optional[str] = None


@dataclass
class AggregatedMetrics:
    precision: float
    recall: float
    f1: float
    completeness: float
    json_valid_rate: float
    hallucination_rate: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    mean_tokens_per_second: float
    peak_memory_mb: Optional[float]


class ModelBenchmark:
    def __init__(
        self,
        model_name: str,
        scraper_factory: ScraperFactory,
        test_cases: Sequence[BenchmarkTestCase],
        iterations: int = 3,
    ) -> None:
        self.model_name = model_name
        self.scraper_factory = scraper_factory
        self.test_cases = test_cases
        self.iterations = max(1, iterations)
        self._results: Dict[str, List[ExtractionResult]] = {}

    def run_full_benchmark(self) -> AggregatedMetrics:
        latencies: List[float] = []
        precisions: List[float] = []
        recalls: List[float] = []
        f1_scores: List[float] = []
        completeness_scores: List[float] = []
        json_valid_flags: List[bool] = []
        hallucination_rates: List[float] = []
        tokens_per_second: List[float] = []
        memory_measurements: List[float] = []

        for test_case in self.test_cases:
            self._results[test_case.id] = self._run_test_iterations(test_case)
            for result in self._results[test_case.id]:
                latencies.append(result.latency)
                precisions.append(result.quality_metrics.get("precision", 0.0))
                recalls.append(result.quality_metrics.get("recall", 0.0))
                f1_scores.append(result.quality_metrics.get("f1", 0.0))
                completeness_scores.append(result.quality_metrics.get("completeness", 0.0))
                json_valid_flags.append(result.json_valid)
                hallucination_rates.append(result.hallucination_rate)
                tokens_per_second.append(result.tokens_per_second)
                if result.memory_used_mb is not None:
                    memory_measurements.append(result.memory_used_mb)

        return AggregatedMetrics(
            precision=self._mean(precisions),
            recall=self._mean(recalls),
            f1=self._mean(f1_scores),
            completeness=self._mean(completeness_scores),
            json_valid_rate=self._ratio(json_valid_flags),
            hallucination_rate=self._mean(hallucination_rates),
            latency_p50=self._percentile(latencies, 50),
            latency_p95=self._percentile(latencies, 95),
            latency_p99=self._percentile(latencies, 99),
            mean_tokens_per_second=self._mean(tokens_per_second),
            peak_memory_mb=max(memory_measurements) if memory_measurements else None,
        )

    def _run_test_iterations(self, test_case: BenchmarkTestCase) -> List[ExtractionResult]:
        results: List[ExtractionResult] = []
        scraper = self.scraper_factory(self.model_name)

        ai_web_scraper_cls = None
        crawl4ai_scraper_cls = None
        try:
            from app.utils.ai_web_scraper import AIWebScraper as _AIWebScraper

            ai_web_scraper_cls = _AIWebScraper
        except Exception:  # pragma: no cover - optional dependency
            ai_web_scraper_cls = None
        try:
            from app.utils.crawl4ai_scraper import Crawl4AIOllamaScraper as _Crawl4AIOllamaScraper

            crawl4ai_scraper_cls = _Crawl4AIOllamaScraper
        except Exception:  # pragma: no cover - optional dependency
            crawl4ai_scraper_cls = None

        for _ in range(self.iterations):
            start_time = time.perf_counter()
            snapshot_before = self._process_snapshot()
            error_message: Optional[str] = None
            raw_response: str = ""
            response_payload: Any = {}

            try:
                if ai_web_scraper_cls and isinstance(scraper, ai_web_scraper_cls):
                    prompt_entry = scraper._resolve_prompt(
                        "company_basic", self.model_name, scraper.company_prompt
                    )
                    prompt_template = prompt_entry.get("template", scraper.company_prompt)
                    query_response = scraper._query_ollama(
                        prompt_template,
                        test_case.html_content,
                        model_name=self.model_name,
                        system_message=prompt_entry.get("system_message"),
                        prompt_parameters=prompt_entry.get("parameters"),
                    )
                    if isinstance(query_response, dict):
                        response_payload = query_response
                        raw_response = json.dumps(query_response, ensure_ascii=False)
                    elif isinstance(query_response, str):
                        parsed = scraper._parse_json_response(query_response)
                        response_payload = parsed if isinstance(parsed, dict) else {}
                        raw_response = query_response
                    else:
                        response_payload = {}
                        raw_response = json.dumps({"raw": str(query_response)}, ensure_ascii=False)
                elif crawl4ai_scraper_cls and isinstance(scraper, crawl4ai_scraper_cls):
                    source_url = test_case.source or (
                        test_case.metadata.get("url") if test_case.metadata else None
                    )
                    query_response = scraper.extract_from_content(
                        test_case.html_content,
                        model_name=self.model_name,
                        source_url=source_url,
                    )
                    response_payload = query_response if isinstance(query_response, dict) else {}
                    raw_response = (
                        json.dumps(query_response, ensure_ascii=False)
                        if isinstance(query_response, (dict, list))
                        else str(query_response)
                    )
                else:
                    extract_fn = getattr(scraper, "extract_company_data", None)
                    if not callable(extract_fn):
                        raise AttributeError(
                            "scraper must expose extract_company_data or content extraction method"
                        )
                    query_response = extract_fn(test_case.html_content)
                    response_payload = query_response if isinstance(query_response, dict) else {}
                    raw_response = (
                        json.dumps(query_response, ensure_ascii=False)
                        if isinstance(query_response, (dict, list))
                        else str(query_response)
                    )
            except Exception as exc:  # pragma: no cover - defensive
                error_message = str(exc)
                response_payload = {}
                raw_response = json.dumps({"error": error_message}, ensure_ascii=False)

            latency = time.perf_counter() - start_time
            snapshot_after = self._process_snapshot()

            parsed_payload = response_payload if isinstance(response_payload, dict) else {}
            if not parsed_payload and raw_response:
                json_valid, parsed = _safe_json_loads(raw_response)
                if json_valid and isinstance(parsed, dict):
                    parsed_payload = parsed
            else:
                json_valid, _ = _safe_json_loads(raw_response)

            quality = self.calculate_quality_metrics(parsed_payload, test_case.expected_data)
            hallucination_rate = self._estimate_hallucination_rate(parsed_payload, test_case.expected_data)
            tokens_per_second = self._estimate_tokens_per_second(response_payload, latency)
            memory_used_mb = self._memory_used(snapshot_before, snapshot_after)

            results.append(
                ExtractionResult(
                    latency=latency,
                    response=response_payload,
                    raw_response=raw_response,
                    quality_metrics=quality,
                    json_valid=json_valid,
                    hallucination_rate=hallucination_rate,
                    tokens_per_second=tokens_per_second,
                    memory_used_mb=memory_used_mb,
                    error=error_message,
                )
            )

        return results

    @staticmethod
    def calculate_quality_metrics(extracted: Any, expected: Dict[str, Any]) -> Dict[str, float]:
        if not isinstance(extracted, dict):
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "completeness": 0.0}

        true_positive = 0
        false_positive = 0
        false_negative = 0
        total_expected = 0

        for key, expected_value in expected.items():
            total_expected += 1
            extracted_value = extracted.get(key)
            if expected_value in (None, "", [], {}):
                if extracted_value not in (None, "", [], {}):
                    false_positive += 1
            else:
                if extracted_value in (None, "", [], {}):
                    false_negative += 1
                elif ModelBenchmark._normalize_value(extracted_value) == ModelBenchmark._normalize_value(expected_value):
                    true_positive += 1
                else:
                    false_positive += 1
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
        recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        completeness = true_positive / total_expected if total_expected else 0.0

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "completeness": completeness,
        }

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        if isinstance(value, list):
            return sorted(ModelBenchmark._normalize_value(v) for v in value)
        return value

    @staticmethod
    def _estimate_hallucination_rate(extracted: Any, expected: Dict[str, Any]) -> float:
        if not isinstance(extracted, dict):
            return 1.0
        hallucinations = 0
        total = 0
        for key, value in extracted.items():
            total += 1
            expected_value = expected.get(key)
            if expected_value in (None, "", [], {}):
                if value not in (None, "", [], {}):
                    hallucinations += 1
            elif ModelBenchmark._normalize_value(value) != ModelBenchmark._normalize_value(expected_value):
                hallucinations += 1
        return hallucinations / total if total else 0.0

    @staticmethod
    def _estimate_tokens_per_second(response: Any, latency: float) -> float:
        if latency <= 0:
            return 0.0
        text = json.dumps(response, ensure_ascii=False) if isinstance(response, (dict, list)) else str(response)
        rough_token_count = max(1, len(text) // 4)
        return rough_token_count / latency

    @staticmethod
    def _process_snapshot() -> Optional[psutil.Process]:
        if psutil is None:
            return None
        try:
            return psutil.Process()
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _memory_used(before: Optional[psutil.Process], after: Optional[psutil.Process]) -> Optional[float]:
        if before is None or after is None:
            return None
        try:
            before_mem = before.memory_info().rss
            after_mem = after.memory_info().rss
            return max(0.0, (after_mem - before_mem) / (1024 * 1024))
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _mean(values: Iterable[float]) -> float:
        data = list(values)
        return float(sum(data) / len(data)) if data else 0.0

    @staticmethod
    def _percentile(values: Iterable[float], percentile: float) -> float:
        data = sorted(values)
        if not data:
            return 0.0
        k = (len(data) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return data[int(k)]
        return data[f] * (c - k) + data[c] * (k - f)

    @staticmethod
    def _ratio(flags: Iterable[bool]) -> float:
        data = list(flags)
        if not data:
            return 0.0
        return sum(1 for flag in data if flag) / len(data)


def run_benchmarks(
    models: Sequence[str],
    scraper_name: str,
    test_cases: Sequence[BenchmarkTestCase],
    iterations: int,
    output_mode: str,
) -> Dict[str, AggregatedMetrics]:
    selector = ModelSelector()
    scraper_factory = _load_scraper(scraper_name, selector)
    results: Dict[str, AggregatedMetrics] = {}
    details: Dict[str, Any] = {}

    for model in models:
        benchmark = ModelBenchmark(model, scraper_factory, test_cases, iterations=iterations)
        aggregated = benchmark.run_full_benchmark()
        results[model] = aggregated
        total_errors, per_case_errors = _summarize_errors(benchmark._results)
        details[model] = {
            "precision": aggregated.precision,
            "recall": aggregated.recall,
            "f1": aggregated.f1,
            "completeness": aggregated.completeness,
            "json_valid_rate": aggregated.json_valid_rate,
            "hallucination_rate": aggregated.hallucination_rate,
            "latency_p50": aggregated.latency_p50,
            "latency_p95": aggregated.latency_p95,
            "latency_p99": aggregated.latency_p99,
            "mean_tokens_per_second": aggregated.mean_tokens_per_second,
            "peak_memory_mb": aggregated.peak_memory_mb,
            "error_count": total_errors,
            "errors_by_case": per_case_errors,
            "recommended_config": _recommend_config(aggregated),
        }

    if output_mode in {"json", "both"}:
        _ensure_dir(BENCHMARK_RESULTS_FILE)
        BENCHMARK_RESULTS_FILE.write_text(json.dumps(details, indent=2), encoding="utf-8")
        BENCHMARK_DETAILS_FILE.write_text(json.dumps(details, indent=2), encoding="utf-8")

    if output_mode in {"markdown", "both"}:
        _ensure_dir(BENCHMARK_REPORT_FILE)
        BENCHMARK_REPORT_FILE.write_text(_render_markdown_report(details), encoding="utf-8")

    return results


def _render_markdown_report(details: Dict[str, Any]) -> str:
    headers = [
        "Model",
        "Precision",
        "Recall",
        "F1",
        "Completeness",
        "JSON Valid %",
        "Hallucination %",
        "p50 (s)",
        "p95 (s)",
        "p99 (s)",
        "Tokens/s",
        "Peak Memory (MB)",
        "Errors",
    ]
    table_lines = ["| " + " | ".join(headers) + " |", "|" + " --- |" * len(headers)]
    for model, metrics in details.items():
        row = [
            model,
            f"{metrics['precision']:.2%}",
            f"{metrics['recall']:.2%}",
            f"{metrics['f1']:.2%}",
            f"{metrics['completeness']:.2%}",
            f"{metrics['json_valid_rate']:.2%}",
            f"{metrics['hallucination_rate']:.2%}",
            f"{metrics['latency_p50']:.2f}",
            f"{metrics['latency_p95']:.2f}",
            f"{metrics['latency_p99']:.2f}",
            f"{metrics['mean_tokens_per_second']:.2f}",
            f"{metrics['peak_memory_mb']:.2f}" if metrics.get("peak_memory_mb") is not None else "N/A",
            str(metrics.get("error_count", 0)),
        ]
        table_lines.append("| " + " | ".join(row) + " |")

    return "\n".join(
        [
            "# Ollama Model Benchmark Report",
            "",
            "Generated by `scripts/benchmarks/benchmark_ollama_models.py`.",
            "",
            "## Summary",
            "",
            *table_lines,
            "",
            "## Notes",
            "- Tokens per second are approximations based on payload lengths.",
            "- Memory usage is only recorded when `psutil` is available.",
            "- Error counts reflect iteration-level exceptions per model.",
        ]
    )


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Ollama models for scraping accuracy and performance.")
    parser.add_argument(
        "--models",
        default="llama3.2,llama3.2:1b,mistral,qwen2.5,codellama",
        help="Comma-separated list of Ollama models to benchmark.",
    )
    parser.add_argument(
        "--scraper",
        default="ai_web_scraper",
        choices=["ai_web_scraper"],
        help="Scraper implementation used for benchmarking (Crawl4AI support pending async runner).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of runs per test case for statistical significance.",
    )
    parser.add_argument(
        "--test-cases",
        type=int,
        default=None,
        help="Limit number of test cases (default: run all).",
    )
    parser.add_argument(
        "--test-file",
        default=str(DEFAULT_TEST_CASES_FILE),
        help="Path to benchmark test cases JSON file.",
    )
    parser.add_argument(
        "--output",
        choices=["json", "markdown", "both", "none"],
        default="both",
        help="Output mode for benchmark results.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging for debug purposes.",
    )
    return parser.parse_args(args)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    test_cases = BenchmarkTestCase.load_all(Path(args.test_file))
    if args.test_cases:
        test_cases = test_cases[: args.test_cases]
    if args.verbose:
        print(f"Running benchmark for models: {models}")
        print(f"Total test cases: {len(test_cases)}")
        print(f"Iterations per test case: {args.iterations}")

    run_benchmarks(models, args.scraper, test_cases, args.iterations, args.output)

    if args.output == "none":
        print("Benchmarks completed without writing output files.")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
