# Evaluation

We evaluated `freeact` with the following models:

- GPT-4.1 (`gpt-4.1`)
- Gemini 2.5 Pro Preview (`gemini-2.5-pro-preview-03-25`, `reasoning_effort=low`)
- Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`)
- Claude 3.5 Haiku (`claude-3-5-haiku-20241022`)
- Gemini 2.0 Flash (`gemini-2.0-flash-exp`)
- Qwen 2.5 Coder 32B Instruct (`qwen2p5-coder-32b-instruct`)
- DeepSeek V3 (`deepseek-v3`)
- DeepSeek R1 (`deepseek-r1`)

The evaluation uses two datasets:

1. [m-ric/agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2)
2. [m-ric/smol_agents_benchmark](https://huggingface.co/datasets/m-ric/smol_agents_benchmark)

Both datasets were created by the [smolagents](https://github.com/huggingface/smolagents) team at 🤗 Hugging Face and contain curated tasks from GAIA, GSM8K, SimpleQA, and MATH. We primarily use them for quickly comparing model performances in `freeact`, and for having a comparison with [their published results](https://huggingface.co/blog/smolagents#how-strong-are-open-models-for-agentic-workflows). To ensure a fair comparison, we use identical evaluation protocols and tools (implemented as [skills](skills)).

[<img src="../docs/eval/eval-plot.png" alt="Performance">](../docs/eval/eval-plot.png)

| model                                                   | GAIA (exact_match)  | GSM8K (exact_match) | MATH (exact_match) | SimpleQA (exact_match) | SimpleQA (llm_as_judge) |
|:--------------------------------------------------------|--------------------:|--------------------:|-------------------:|-----------------------:|------------------------:|
| gpt-4.1                                                 |                40.6 |                92.9 |           **98.0** |                  62.5  |                   65.0  |
| gemini-2.5-pro-preview-03-25<br/>(reasoning_effort=low) |                62.5 |                92.9 |               92.0 |               **65.0** |                **77.5** |
| claude-3-5-sonnet-20241022                              |                53.1 |            **95.7** |               90.0 |                  57.5  |                   72.5  |
| claude-3-5-haiku-20241022                               |                31.2 |                90.0 |               76.0 |                  52.5  |                   70.0  |
| gemini-2.0-flash-exp                                    |                34.4 |            **95.7** |               88.0 |                  50.0  |                   65.0  |
| qwen2p5-coder-32b-instruct                              |                25.0 |            **95.7** |               88.0 |                  52.5  |                   65.0  |
| deepseek-v3                                             |                37.5 |                91.4 |               88.0 |                  60.0  |                   67.5  |
| deepseek-r1                                             |            **65.6** |                     |                    |                        |                         |


A comparison with the smolagents [results](https://github.com/huggingface/smolagents/blob/c22fedaee17b8b966e86dc53251f210788ae5c19/examples/benchmark.ipynb), executed on 2025-01-07 with `claude-3-5-sonnet-20241022`, shows a higher success rate for `freeact` agents on [m-ric/agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2). Interestingly, these results were obtained with zero-shot prompting in `freeact`, while smolagents uses few-shot prompting.

[<img src="../docs/eval/eval-plot-comparison.png" alt="Performance comparison" width="60%">](../docs/eval/eval-plot-comparison.png)

| agent      | model                      | prompt    | GAIA      | GSM8K     | SimpleQA  |
|:-----------|:---------------------------|:----------|----------:|----------:|----------:|
| freeact    | claude-3-5-sonnet-20241022 | zero-shot |  **53.1** |  **95.7** |  **57.5** |
| smolagents | claude-3-5-sonnet-20241022 | few-shot  |      43.8 |      91.4 |      47.5 |

## Running

Clone the `freeact` repository:

```bash
git clone https://github.com/freeact/freeact.git
```

Set up a development environment as described in [DEVELOPMENT.md](../DEVELOPMENT.md) and create a `.env` file with [Anthropic](https://console.anthropic.com/settings/keys), [Gemini](https://aistudio.google.com/app/apikey), [Fireworks AI](https://fireworks.ai/account/api-keys) [SerpAPI](https://serpapi.com/dashboard) and [OpenAI](https://platform.openai.com/settings/organization/api-keys) API keys:

```env title=".env"
# Claude 3.5 Sonnet and Haiku
ANTHROPIC_API_KEY=...

# Gemini 2 Flash Experimental
GOOGLE_API_KEY=...

# Qwen 2.5 Coder 32B Instruct and DeepSeek V3
FIREWORKS_API_KEY=...

# Google Web Search
SERPAPI_API_KEY=...

# GPT-4 Judge (SimpleQA evaluation)
OPENAI_API_KEY=...
```

Then run the evaluation script for each model:

```bash
python evaluation/evaluate.py \
    --model-name gpt-4.1 \
    --run-id gpt-4.1 \
    --debug

python evaluation/evaluate.py \
    --model-name gemini-2.5-pro-preview-03-25 \
    --run-id gemini-2.5-pro-preview-03-25 \
    --debug

python evaluation/evaluate.py \
    --model-name claude-3-5-sonnet-20241022 \
    --run-id claude-3-5-sonnet-20241022 \
    --debug

python evaluation/evaluate.py \
    --model-name claude-3-5-haiku-20241022 \
    --run-id claude-3-5-haiku-20241022 \
    --debug

python evaluation/evaluate.py \
    --model-name gemini-2.0-flash-exp \
    --run-id gemini-2.0-flash-exp \
    --debug

python evaluation/evaluate.py \
    --model-name qwen2p5-coder-32b-instruct \
    --run-id qwen2p5-coder-32b-instruct \
    --debug

python evaluation/evaluate.py \
    --model-name deepseek-v3 \
    --run-id deepseek-v3 \
    --debug

python evaluation/evaluate.py \
    --model-name deepseek-r1 \
    --run-id deepseek-r1 \
    --debug
```

Results are saved in `output/evaluation/<run-id>`. Pre-generated outputs from our runs are available [here](https://github.com/user-attachments/files/20028136/evaluation-results-agents-7_medium_benchmark_2.zip).

## Analysis

Score the results:

```bash
python evaluation/score.py \
  --evaluation-dir output/evaluation/gpt-4.1 \
  --evaluation-dir output/evaluation/gemini-2.5-pro-preview-03-25 \
  --evaluation-dir output/evaluation/claude-3-5-sonnet-20241022 \
  --evaluation-dir output/evaluation/claude-3-5-haiku-20241022 \
  --evaluation-dir output/evaluation/gemini-2.0-flash-exp \
  --evaluation-dir output/evaluation/qwen2p5-coder-32b-instruct \
  --evaluation-dir output/evaluation/deepseek-v3 \
  --evaluation-dir output/evaluation/deepseek-r1
```

Generate plots and reports:

```bash
python evaluation/report.py performance

python evaluation/report.py performance-comparison \
  --model-name claude-3-5-sonnet-20241022 \
  --reference-results-file evaluation/reference/agents_medium_benchmark_2/smolagents-20250107.csv

python evaluation/report.py performance-comparison \
  --model-name qwen2p5-coder-32b-instruct \
  --reference-results-file evaluation/reference/agents_medium_benchmark_2/smolagents-20250107.csv
```

Plots and reports are saved to `output/evaluation-report`.
