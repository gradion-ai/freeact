## Overview

Freeact is a library of AI agents that use *code actions*—snippets of executable Python code—to dynamically interact with and adapt to their environment. Freeact agents:

- Have a broad action space since they can install and use any Python library in their code actions
- Autonomously improve their code actions by reflecting on observations from the environment, execution feedback, and human input
- Store code actions as custom skills in long-term memory for faster reuse, enabling the composition of higher-level capabilities

Freeact agents can be deployed out-of-the-box as general-purpose agents or specialized for particular environments using custom skills, domain knowledge, and runbooks:

- Custom skills provide optimized interfaces for interacting with specific environments (e.g., databases, APIs, etc.)
- Domain knowledge guides the agent to refine and adapt its skills within specialized domains
- Runbooks define agent behavior, rules and constraints in natural language

Freeact agents support multi-step reasoning, reflective improvement loops, and secure code execution in ipybox. They can also be integrated into multi-agent environments by leveraging existing multi-agent frameworks or encapsulating other agents as reusable skills.

## Installation
