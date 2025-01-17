# Evaluation results

We [evaluated](https://github.com/gradion-ai/freeact/tree/main/evaluation) `freeact` using four state-of-the-art models:

- Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`)
- Claude 3.5 Haiku (`claude-3-5-haiku-20241022`)
- Gemini 2.0 Flash (`gemini-2.0-flash-exp`)
- Qwen 2.5 Coder 32B Instruct (`qwen2p5-coder-32b-instruct`)

The evaluation was performed on the [m-ric/agents_medium_benchmark_2](https://huggingface.co/datasets/m-ric/agents_medium_benchmark_2) dataset, developed by the [smolagents](https://github.com/huggingface/smolagents) team at 🤗 Hugging Face. It comprises selected tasks from GAIA, GSM8K, and SimpleQA:

<figure markdown>
  [![architecture](eval/eval-plot.png){ align="left" }](eval/eval-plot.png){target="_blank"}
</figure>

When comparing our results with smolagents using Claude 3.5 Sonnet, we observed the following outcomes (evaluation conducted on 2025-01-07, reference data [here](https://github.com/huggingface/smolagents/blob/c22fedaee17b8b966e86dc53251f210788ae5c19/examples/benchmark.ipynb)):

<figure markdown>
  [![architecture](eval/eval-plot-comparison.png){ width="60%" align="left" }](eval/eval-plot-comparison.png){target="_blank"}
</figure>

Interestingly, these results were achieved using zero-shot prompting in `freeact`, while the smolagents implementation utilizes few-shot prompting. To ensure a fair comparison, we employed identical evaluation protocols and tools. You can find all evaluation details [here](https://github.com/gradion-ai/freeact/tree/main/evaluation).
