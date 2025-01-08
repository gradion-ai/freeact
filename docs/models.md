# Supported models

The following models are currently supported:

- `claude-3-5-sonnet-20241022`
- `claude-3-5-haiku-20241022`
- `gemini-2.0-flash-exp`

For most use cases, we recommend `claude-3-5-sonnet-20241022` due to its robust performance. The `gemini-2.0-flash-exp` integration allows developers to replace Gemini’s native code execution with [`ipybox`](https://gradion-ai.github.io/ipybox/)—a secure, locally deployable sandbox that supports extended execution timeouts, on-the-fly package installations, automatic plot generation, and additional features. Note that `gemini-2.0-flash-exp` support is still experimental.
