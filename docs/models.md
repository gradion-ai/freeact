# Supported models

The following models have been [evaluated](evaluation.md) with `freeact`:

- Claude 3.5 Sonnet (20241022)
- Claude 3.5 Haiku (20241022)
- Gemini 2.0 Flash (experimental)
- Qwen 2.5 Coder 32B Instruct
- DeepSeek V3

For these models, `freeact` provides model-specific prompt templates. 

!!! Note

    In addition to the models we evaluated, `freeact` also supports the [integration](integration.md) of new models from any provider that is compatible with the [OpenAI Python SDK](https://github.com/openai/openai-python), including open models deployed locally with [ollama](https://ollama.com/) or [TGI](https://huggingface.co/docs/text-generation-inference/index), for example.

!!! Tip

    For best performance, we recommend Claude 3.5 Sonnet, with DeepSeek V3 as a close second. Support for Gemini 2.0 Flash, Qwen 2.5 Coder, and DeepSeek V3 remains experimental as we continue to optimize their prompt templates.
