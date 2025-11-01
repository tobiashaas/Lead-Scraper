# AI Model Benchmarking Scripts

## Overview

The benchmarking suite provides repeatable evaluations for Ollama-powered scraping
pipelines. It captures accuracy, latency, and resource profiles across models and
prompt variants, enabling data-driven tuning of the production scrapers.

Generated artifacts include:

- Markdown benchmark reports for human review
- JSON summaries for automated model selection
- Prompt optimization results for deployment

## Scripts

### `benchmark_ollama_models.py`

Runs comprehensive model comparisons using curated benchmark cases.

```bash
python scripts/benchmarks/benchmark_ollama_models.py --models llama3.2,mistral --output both
```

#### Key Options

- `--models`: Comma-separated list of models to benchmark (default includes llama3.2, llama3.2:1b, mistral, qwen2.5, codellama)
- `--scraper`: `ai_web_scraper` or `crawl4ai_scraper`
- `--iterations`: Number of repetitions per test case (default 3)
- `--test-cases`: Limit number of cases (default all)
- `--test-file`: Path to test case JSON (default `data/benchmarks/test_cases.json`)
- `--output`: `json`, `markdown`, `both`, or `none`
- `--verbose`: Enable verbose logging

#### Generated Outputs

- `data/benchmarks/ollama_results.json`: Aggregated metrics per model
- `data/benchmarks/benchmark_details.json`: Detailed metrics per model
- `data/benchmarks/benchmark_report.md`: Markdown summary table

### `optimize_prompts.py`

Executes A/B testing across prompt variants for a selected use case.

```bash
python scripts/benchmarks/optimize_prompts.py --use-case company_basic --model llama3.2 --output both
```

#### Options

- `--use-case`: Use case key (e.g., `company_basic`, `employees`)
- `--model`: Ollama model to evaluate
- `--iterations`: Repetitions per prompt variant (default 1)
- `--output`: `json`, `markdown`, `both`, or `none`

#### Outputs

- `data/prompts/optimized_prompts.json`: Prompt library with aggregated metrics
- `data/benchmarks/prompt_optimization_report.md`: Markdown report

## Running the Suite

```bash
# Full workflow
make benchmark-models
make benchmark-prompts
make benchmark-report

# Validate benchmark-specific tests
make test-benchmarks
```

## Test Cases

Benchmark cases live in `data/benchmarks/test_cases.json`. They cover
simple, medium, complex, and edge scenarios with curated ground truth. Add
new cases by appending to the JSON list.

## Interpreting Results

- **Accuracy (F1/precision/recall)**: Quality of field extraction
- **JSON Valid %**: Structured output compliance
- **Hallucination %**: Frequency of fabricated data
- **Latency p50/p95/p99**: Performance characteristics
- **Tokens/s & Peak Memory**: Resource consumption indicators

## Best Practices

1. Benchmark before deploying new models or prompts.
2. Re-run benchmarks after Ollama updates.
3. Keep test cases representative of production workloads.
4. Track results over time to detect regressions.
5. Use prompt optimization to improve accuracy without switching models.
