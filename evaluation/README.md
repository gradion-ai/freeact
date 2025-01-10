# Evaluation

This directory contains scripts that evaluate `freeact` agents on the [agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2) dataset of the [smolagents](https://github.com/huggingface/smolagents) project. We used the very same evaluation protocol and tools (converted to `freeact` [skills](skills)) to ensure a fair comparison to the [smolagents results](https://github.com/huggingface/smolagents?tab=readme-ov-file#how-strong-are-open-models-for-agentic-workflows).

## Results

`freeact` shows the following improvements over `smolagents` (as of 2025-01-06) with the `claude-3-5-sonnet-20241022` model. We see these improvements despite using a zero-shot prompting approach for `freeact` agents, while `smolagents` uses a few-shot prompting approach:

(TODO: use table, and also mention prompting approach)
- GSM8K: smolagents score, freeact score, ...% relative improvement, ...% absolute improvement
- SimpleQA: smolagents score, freeact score, ...% relative improvement, ...% absolute improvement
- GAIA: smolagents score, freeact score, ...% relative improvement, ...% absolute improvement

The following plot also includes other models supported by `freeact` to provide a more comprehensive comparison:

...

For the SimpleQA subset of [agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2) we additionally introduce an LLM-as-judge evaluation protocol conforming to [OpenAI's SimpleQA guidelines](https://openai.com/index/introducing-simpleqa/) to address issues with exact string matching.

**Note**: Agent outputs from our evaluation runs are available [here](https://github.com/user-attachments/files/18364906/evaluation-results-agents_medium_benchmark_2.zip).

## Running

Clone the `freeact` repository:

```bash
git clone https://github.com/freeact/freeact.git
```

Set up the development environment (as described in [CONTRIBUTING.md](../CONTRIBUTING.md)) replacing the default installation command with the following:

```bash
poetry install --with eval
```

Create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys), [Gemini](https://aistudio.google.com/app/apikey), [SerpAPI](https://serpapi.com/dashboard) and [OpenAI](https://platform.openai.com/settings/organization/api-keys) API keys:

```env title=".env"
# Required for Claude 3.5 Sonnet and Haiku
ANTHROPIC_API_KEY=...

# Required for Gemini 2 Flash Experimental
GOOGLE_API_KEY=...

# Required for Google Web Search
SERPAPI_API_KEY=...

# Required for GPT-4o Judge in SimpleQA evaluation
OPENAI_API_KEY=...
```

Then run the evaluation script with a model name and a run-id as arguments:

```bash
python evaluation/evaluate.py \
    --model-name claude-3-5-sonnet-20241022 \
    --run-id claude-3-5-sonnet
```

The following models are currently supported for evaluation:
* `claude-3-5-sonnet-20241022`
* `claude-3-5-haiku-20241022`
* `gemini-2.0-flash-exp`

The evaluation results are saved to a subdirectory named after the `run-id` in the `output/evaluation` directory.

Score the results with:

```bash
python evaluation/score.py \
  --evaluation-dir output/evaluation/claude-3-5-sonnet-20241022 \
  --evaluation-dir output/evaluation/claude-3-5-haiku-20241022 \
  --evaluation-dir output/evaluation/gemini-2.0-flash-exp
```

Finally, generate result tables and plots with:

```bash
python evaluation/report.py performance
```

This script generates a plot with the results in the `output/evaluation-report/plot.png` file.
