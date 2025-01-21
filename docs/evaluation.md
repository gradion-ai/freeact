# Evaluation results

We [evaluated](https://github.com/gradion-ai/freeact/tree/main/evaluation) `freeact` using four state-of-the-art models:

- Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`)
- Claude 3.5 Haiku (`claude-3-5-haiku-20241022`)
- Gemini 2.0 Flash (`gemini-2.0-flash-exp`)
- Qwen 2.5 Coder 32B Instruct (`qwen2p5-coder-32b-instruct`)
- DeepSeek V3 (`deepseek-v3`)

The evaluation was performed using two benchmark datasets: [m-ric/agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2) and the MATH subset from [m-ric/smol_agents_benchmark](https://huggingface.co/datasets/m-ric/smol_agents_benchmark). Both datasets were created by the [smolagents](https://github.com/huggingface/smolagents) team at 🤗 Hugging Face and contain selected tasks from GAIA, GSM8K, SimpleQA and MATH:

<figure markdown>
  [![architecture](eval/eval-plot.png){ align="left" }](eval/eval-plot.png){target="_blank"}
</figure>

When comparing our results with smolagents using Claude 3.5 Sonnet on [m-ric/agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2) (only dataset with available smolagents [reference data](https://github.com/huggingface/smolagents/blob/c22fedaee17b8b966e86dc53251f210788ae5c19/examples/benchmark.ipynb)), we observed the following outcomes (evaluation conducted on 2025-01-07):

<figure markdown>
  [![architecture](eval/eval-plot-comparison.png){ width="60%" align="left" }](eval/eval-plot-comparison.png){target="_blank"}
</figure>

Interestingly, these results were achieved using zero-shot prompting in `freeact`, while the smolagents implementation utilizes few-shot prompting. To ensure a fair comparison, we employed identical evaluation protocols and tools. You can find all evaluation details [here](https://github.com/gradion-ai/freeact/tree/main/evaluation).
