# Deep Research AI Agent

> Agentic research pipeline that processed **44,000+** startups to measure internal generative AI adoption.

![UBC](https://img.shields.io/badge/UBC%20Sauder-AI%20Research-2ea44f)
![APIs](https://img.shields.io/badge/APIs-Perplexity%20%7C%20OpenAI%20%7C%20Tavily-8A2BE2)
![Companies](https://img.shields.io/badge/startups%20processed-44K%2B-orange)
![Findings](https://img.shields.io/badge/verified%20findings-2%2C062-blue)
![Cost](https://img.shields.io/badge/avg%20cost%20per%20startup-%241%20%E2%86%92%20%240.08-brightgreen)

The March 2026 findings dashboard lives with the frozen first production
run in [`legacy_agent_march_2026/presentation/production_results.html`](legacy_agent_march_2026/presentation/production_results.html).
Other HTML decks in `presentation/` are earlier proposal / stage-result slides.

## Research Context & The Problem

Conducted as part of my role as an AI student researcher at **UBC Sauder School of Business** under **Prof. Jan Bena**, supported by **$4K in research grants**. The research question: how is generative AI transforming the internal business processes of startups across the world?

A Perplexity deep-research call costs roughly **$1 per company**. At 44,000 startups, that's a **$44,000 bill** before writing a single line of analysis. The solution: Meticulous parameter tuning + a multi-stage agentic pipeline that uses output strength signals from Tavily API to decide where to spend the expensive compute — routing only the highest-signal companies to the deep-research agent.



## Architecture

```mermaid
flowchart LR
    subgraph S1["Stage 1 — Filter · ~$0.02/company"]
        W["Website Health Check"] --> T["Tavily Web Search"]
        T --> G["GPT-5 nano Priority Scorer (1-5)"]
    end

    subgraph S2["Stage 2 — Deep Research · ~$0.31/company"]
        P["Perplexity deep-research Agent"]
    end

    INPUT["44K Startups (Crunchbase)"] --> W
    G -->|"Priority 4-5 · ~9,400 companies"| P
    P --> OUT["EDA-Ready CSV · 2,062 Findings"]
```



## Engineering Highlights & Agentic Orchestration

**1. Hyperparameter Tuning**

Before the March production run, the Perplexity Agent API parameters were systematically tuned using a structured async A/B test framework (now frozen at `legacy_agent_march_2026/src/tests/stage_2/run_preset_test.py`). Parameters evaluated:

- `preset` — selects the underlying model and reasoning configuration (`deep-research` vs `advanced-deep-research`, each backed by a different frontier model)
- `max_steps` 
- `max_tokens` 
- `max_search_tool_calls` 


---

**2. Prompt Engineering**

Two prompt files drive the pipeline, each designed for a specific stage:

- [`prompts/stage_1_classifier.txt`](prompts/stage_1_classifier.txt) — GPT-5 nano system + user prompt. Instructs the classifier to compare Crunchbase profile against Tavily search snippets and output a `research_priority_score` (0–5). Includes few-shot examples for edge cases (generic company names, AI product companies, minimal footprint).

- [`prompts/stage_2_perplexity_prompt.txt`](prompts/stage_2_perplexity_prompt.txt) — Full deep-research agent prompt with the USE vs. SELL guardrail, source taxonomy, academic evidence standards, JSON output schema, and five few-shot examples covering positive findings, indirect evidence, and negative cases.


---

**3. Selective Model Escalation via Signal Strength**

Stage 1 uses Tavily search result quality as a proxy for a company's researchability. The GPT-5 nano classifier evaluates result count, source diversity, snippet relevance, and match confidence against the Crunchbase profile. Weak signals (generic names surfacing unrelated entities, thin snippets, dead sites) score 0–3 and stop there. High signals score 4–5 and escalate. This is the core mechanism behind the cost reduction: **spend $0.02 to decide whether to spend $0.31**.

---

**4. Academic-Grade Evidence Standards**

The Stage 2 prompt enforces strict research validity constraints baked directly into the agent's system prompt:

- **No source = no finding.** Every claim requires a citable URL.
- **No inference.** Report only what sources explicitly state.
- **Tool specificity.** "AI coding tool" is rejected; "GitHub Copilot" is required.
- **USE vs. SELL guardrail.** A company building AI products is not evidence of internal adoption — separate evidence of operational use is required.
- **Negative result documentation.** When no finding is found, the agent produces a structured `no_finding_analysis` explaining what was checked and why it didn't qualify.

---

**5. Rate Limiting & Async**

Stage 2 runs `AsyncPerplexity` with configurable concurrency (tested up to 250 workers in production), enforced by a custom `AsyncRateLimiter` (`src/common/rate_limiter.py`) that caps requests per minute to stay within API tier limits. A hard USD `--budget-cap` stops new calls when cumulative spend reaches the ceiling. Three-state Ctrl+C handling (PAUSE → RESUME or STOP) makes multi-hour runs operable without process loss.

---

**6. Structured JSON Schema for EDA-Ready Output**

Every agent response conforms to a strict JSON Schema enforced via Perplexity's `response_format` parameter. Findings land directly into a master JSONL with no post-processing — each row includes `AI_tool_used`, `business_function`, `use_case`, `evidence_description`, `source_url`, `source_type`, `cost_usd`, `input_tokens`, `output_tokens`, and `model_used`. The master CSV is regenerated after every run. No cleanup step, no manual review needed to load into Pandas.




## Tech Stack

| Layer | Tools |
|-------|-------|
| Deep research agent | Perplexity Agent API (`deep-research` preset) |
| Stage 1 classifier | OpenAI GPT-5 nano (via `httpx`) |
| Web search / signal probe | Tavily API (via `httpx`) |
| Async runtime | Python `asyncio`, `httpx`, custom `AsyncRateLimiter` |
| Schema | JSON Schema via Perplexity `response_format` |
| Data layer | Incremental JSONL, EDA-ready CSV |
| Tuning | Live: `evals/`. March A/B scripts: `legacy_agent_march_2026/src/tests/stage_2/` |

---

## Academic Findings Snapshot

**Findings by business function**

`Engineering 28.3%` · `Marketing 23.7%` · `Operations 23.0%` · `Customer Service` · `Sales` · `HR` · `Finance`

GenAI is not just an engineering tool. Marketing and Operations together account for nearly half of all findings.

**Evidence by source type**

`Company blogs 36.1%` · `Job postings 25.3%` · `Podcasts/video 12.9%` · `Website content 7.9%` · `Press coverage 7.6%`

[**View the March 2026 dashboard →**](legacy_agent_march_2026/presentation/production_results.html)



## Notable Agent Findings

**KONAMIYA** · `Sales` · `Retell AI, OpenAI` · [Source →](https://konamiya.com/en/how-we-automated-lead-qualification-with-retell-ai-make-com-and-clickup/)

Built an end-to-end automated lead qualification pipeline using Retell AI and OpenAI — replacing manual SDR workflows with an AI-native outbound system, documented publicly on their blog.

**HealthyLongevity.clinic** · `Customer Service` · `ChatGPT` · [Source →](https://www.healthylongevityclinic.cz/blog/novy-pristup-healthylongevity-clinic-hlc-a-jak-je-to-vlastne-se-zpomalenim-starnuti)

Integrated ChatGPT into clinical systems for biomarker analysis. Evidence sourced from a Czech-language blog post — the agent found, retrieved, and correctly interpreted a foreign-language source without any additional configuration.


## Repo Structure

Live Stage 2 is the architecture packages plus the eval harness. The March 2026
batch runner, its prompt, and its results dashboard are a frozen snapshot in
`legacy_agent_march_2026/` (runnable on its own, not imported by live code).
`src/` is Stage 1 only. `prompts/stage_2_perplexity_prompt.txt` stays in the
live tree because Unified Adaptive Search still loads it.

```
├── parallel_channel_search/       # PCS: 3 equal-depth channel agents
├── signal_gated_search/           # SGS: scouts, then gated digs
├── unified_adaptive_search/       # UAS: one adaptive Agent API call
├── citation_verification/         # Stage 3 judge (production package)
├── evals/                         # Harness + panels + instance archive
│   ├── references/                # Frozen March dump for panel rebuilds (local)
│   └── ...
├── contracts/                     # Shared Finding + cost ledger types
├── prompts/                       # Stage 1, UAS lineage, PCS/SGS/Stage 3
├── src/                           # Stage 1 filter pipeline only
│   ├── stage_1/
│   ├── common/
│   └── config.py
├── legacy_agent_march_2026/       # Frozen March agent (do not import)
├── credentials/                   # *.txt.template tracked; real keys gitignored
├── crunchbase_data/               # Licensed dumps local-only; sample/ in git
└── outputs/                       # gitignored pipeline artifacts
    ├── stage1/
    ├── stage2/test_runs/          # runners + summary.jsonl (eval evidence)
    └── prod/sample/               # fictional findings schema
```

### Eval CLI (architecture playground)

Architecture keys (kebab-case): `parallel-channel-search`, `signal-gated-search`,
`unified-adaptive-search` (aliases: `pcs`, `sgs`, `uas`).

```bash
# Estimate spend before a paid run (no API calls)
python -m evals cost-preview unified-adaptive-search

# Dry Stage A hyperparam screen (UAS) → Tuning instance dashboard
python -m evals run-tuning uas --stage screen

# Matrix prior + notes (includes $50 per-tuning-run ceiling); live aborts if over
python -m evals cost-preview uas --matrix screen
python -m evals run-tuning uas --stage screen --live

# Stub archive rows for later phases
python -m evals run-benchmarks uas
python -m evals run-verification

# Open the categorized landing index under evals/instances/
python -m evals open-dashboard
```

Eval artifacts stay under `evals/` so the harness is standalone. Live `run-tuning`
aborts before paid arms when the matrix prior exceeds **$50**
(`MAX_USD_PER_TUNING_RUN` in `evals/paths.py`). That is separate from the
architecture unit-cost target (~$0.10/company). Benchmark bake-off and Stage 3
verification remain stubs.

