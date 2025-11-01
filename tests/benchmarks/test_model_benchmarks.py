import json
import os
from pathlib import Path
from types import MethodType

import pytest

from app.utils.model_selector import ModelSelector
from scripts.benchmarks import benchmark_ollama_models as benchmarks
from scripts.benchmarks import optimize_prompts

os.environ.setdefault("DATABASE_URL", "sqlite:///./benchmark_tests.db")


@pytest.fixture
def sample_case() -> benchmarks.BenchmarkTestCase:
    return benchmarks.BenchmarkTestCase(
        id="case-1",
        name="Sample",
        html_content="<html><body>Acme Corp</body></html>",
        expected_data={"company_name": "Acme Corp"},
        complexity="simple",
    )


def _make_result(
    *,
    precision: float = 1.0,
    recall: float = 1.0,
    f1: float = 1.0,
    completeness: float = 1.0,
    latency: float = 0.05,
    json_valid: bool = True,
    hallucination_rate: float = 0.0,
    tokens_per_second: float = 10.0,
    memory_used_mb: float | None = 5.0,
    error: str | None = None,
) -> benchmarks.ExtractionResult:
    return benchmarks.ExtractionResult(
        latency=latency,
        response={"company_name": "Acme Corp"},
        raw_response=json.dumps({"company_name": "Acme Corp"}),
        quality_metrics={
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "completeness": completeness,
        },
        json_valid=json_valid,
        hallucination_rate=hallucination_rate,
        tokens_per_second=tokens_per_second,
        memory_used_mb=memory_used_mb,
        error=error,
    )


@pytest.mark.benchmark
def test_benchmark_llama32_extraction_quality(sample_case: benchmarks.BenchmarkTestCase) -> None:
    benchmark = benchmarks.ModelBenchmark(
        "llama3.2", lambda _: object(), [sample_case], iterations=1
    )
    benchmark._run_test_iterations = MethodType(lambda self, _case: [_make_result()], benchmark)
    metrics = benchmark.run_full_benchmark()
    assert metrics.f1 == pytest.approx(1.0)
    assert metrics.completeness == pytest.approx(1.0)


@pytest.mark.benchmark
def test_benchmark_mistral_vs_llama32(sample_case: benchmarks.BenchmarkTestCase) -> None:
    fast_benchmark = benchmarks.ModelBenchmark(
        "llama3.2", lambda _: object(), [sample_case], iterations=1
    )
    fast_benchmark._run_test_iterations = MethodType(
        lambda self, _case: [_make_result(f1=0.65, precision=0.7, recall=0.6, completeness=0.6)],
        fast_benchmark,
    )
    accurate_benchmark = benchmarks.ModelBenchmark(
        "mistral", lambda _: object(), [sample_case], iterations=1
    )
    accurate_benchmark._run_test_iterations = MethodType(
        lambda self, _case: [_make_result(f1=0.82, precision=0.85, recall=0.8, completeness=0.8)],
        accurate_benchmark,
    )

    fast_metrics = fast_benchmark.run_full_benchmark()
    accurate_metrics = accurate_benchmark.run_full_benchmark()

    assert accurate_metrics.f1 > fast_metrics.f1
    assert accurate_metrics.precision >= fast_metrics.precision


@pytest.mark.benchmark
def test_benchmark_response_times(sample_case: benchmarks.BenchmarkTestCase) -> None:
    benchmark = benchmarks.ModelBenchmark(
        "llama3.2:1b", lambda _: object(), [sample_case], iterations=1
    )
    benchmark._run_test_iterations = MethodType(
        lambda self, _case: [_make_result(latency=0.12), _make_result(latency=0.25)],
        benchmark,
    )
    metrics = benchmark.run_full_benchmark()
    assert metrics.latency_p50 > 0
    assert metrics.latency_p95 >= metrics.latency_p50


@pytest.mark.benchmark
def test_json_validity_rate(sample_case: benchmarks.BenchmarkTestCase) -> None:
    benchmark = benchmarks.ModelBenchmark(
        "mistral", lambda _: object(), [sample_case], iterations=1
    )
    benchmark._run_test_iterations = MethodType(
        lambda self, _case: [_make_result(json_valid=True), _make_result(json_valid=False)],
        benchmark,
    )
    metrics = benchmark.run_full_benchmark()
    assert metrics.json_valid_rate == pytest.approx(0.5)


@pytest.mark.benchmark
def test_hallucination_detection(sample_case: benchmarks.BenchmarkTestCase) -> None:
    benchmark = benchmarks.ModelBenchmark(
        "qwen2.5", lambda _: object(), [sample_case], iterations=1
    )
    benchmark._run_test_iterations = MethodType(
        lambda self, _case: [
            _make_result(hallucination_rate=0.2),
            _make_result(hallucination_rate=0.1),
        ],
        benchmark,
    )
    metrics = benchmark.run_full_benchmark()
    assert metrics.hallucination_rate == pytest.approx(0.15)


@pytest.mark.benchmark
def test_model_selector_use_case_mapping(tmp_path: Path) -> None:
    prompt_library = tmp_path / "prompts.json"
    prompt_library.write_text(
        json.dumps(
            {
                "company_basic": {
                    "llama3.2": {
                        "template": "Prompt {{content}}",
                        "system_message": "System",
                        "parameters": {"temperature": 0.2},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    benchmark_results = tmp_path / "results.json"
    benchmark_results.write_text(
        json.dumps(
            {
                "llama3.2": {
                    "recommended_config": {
                        "top_p": 0.85,
                        "num_predict": 1536,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    selector = ModelSelector(
        benchmark_results_path=str(benchmark_results),
        prompt_library_path=str(prompt_library),
    )

    prompt_entry = selector.get_optimized_prompt("company_basic", "llama3.2")
    config = selector.get_model_config("llama3.2")

    assert isinstance(prompt_entry, dict)
    assert prompt_entry["template"].startswith("Prompt")
    assert config["top_p"] == pytest.approx(0.85)
    assert config["num_predict"] == 1536


@pytest.mark.benchmark
def test_optimized_prompts_improve_accuracy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scores_path = tmp_path / "prompt_scores.json"
    library_path = tmp_path / "optimized_prompts.json"

    monkeypatch.setattr(optimize_prompts, "PROMPT_SCORES_PATH", scores_path)
    monkeypatch.setattr(optimize_prompts, "PROMPT_LIBRARY_PATH", library_path)

    sample_cases = [
        benchmarks.BenchmarkTestCase(
            id="case-1",
            name="Case",
            html_content="<html>Content</html>",
            expected_data={"field": "value"},
        )
    ]
    monkeypatch.setattr(
        benchmarks.BenchmarkTestCase, "load_all", staticmethod(lambda: sample_cases)
    )

    def fake_evaluate(variant, model, cases):
        del model, cases
        base = 0.5 if variant.name == "baseline" else 0.7
        return {
            "prompt": variant.name,
            "model": "llama3.2",
            "f1_mean": base,
            "latency_mean": 0.2,
            "hallucination_mean": 0.05,
        }

    monkeypatch.setattr(optimize_prompts, "evaluate_prompt_variant", fake_evaluate)

    variants = optimize_prompts._load_prompt_variants("company_basic")
    monkeypatch.setattr(optimize_prompts, "_load_prompt_variants", lambda use_case: variants)

    results = optimize_prompts.run_prompt_optimization("company_basic", "llama3.2", 1, "json")

    assert any(result["prompt"] != "baseline" for result in results)
    assert scores_path.exists()
    saved_scores = json.loads(scores_path.read_text(encoding="utf-8"))
    assert "company_basic" in saved_scores

    library_payload = json.loads(library_path.read_text(encoding="utf-8"))
    assert library_payload["company_basic"]["llama3.2"]["template"].strip() != ""
