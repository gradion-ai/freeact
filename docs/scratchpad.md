Freeact is a lightweight LLM agent library using Python as common language for describing actions and tools. Freeact agents are LLM agents that 

- code their own actions in Python instead of calling functions via JSON
- act by executing these *code actions* in a sandboxed environment
- can store code actions as *custom skills* in long-term memory
- use tools described in code and docstrings rather than JSON schema
- can use any feature from any Python package as tool definition
- can reuse custom skills as tools in code actions and improve on them
- can compose tools in code actions with the full versatility of Python
- supports usage and composition of any MCP server tool in code actions
- supports usage of any LLM from any provider as code action generator




Freeact agents are LLM agents that

- express their actions directly in executable code, called *code actions*, rather than through constrained formats like JSON
- can use any definition from any Python module as *skill definition* and utilize and compose them in generated code actions
- can have conversations with a user to interactively develop more complex *custom skills* and store them in long-term memory
- execute code actions in a secure sandbox based on IPython and Docker. This sandbox can run both locally and in the cloud.

Most LLMs today excel at understanding and generating code. 
Freeact therefore provides LLMs with skills defined in **plain Python source code** rather than tools described with a schema definition language.
This is usually source code of modules that provide the interfaces to larger packages, rather than implementation details that aren't relevant for usage. 

Because skills definitions and code actions share the same programming language, skills can be natively included and composed into code actions.
Another advantage of this approach is that code actions (= agent output) can be reused as skills (= agent input) for generating code actions of increasing complexity.
Since code actions can be stored as custom skills in long-term memory, this allows Freeact agents to learn from past experiences and improve over time.

To leverage the vast ecosystem of MCP servers and their tools, Freeact automatically generates Python client functions from MCP tool definitions and provides them as *skills* to Freeact agents.
Freeact agents can even leverage code snippets from tutorials, user guides, ..., etc. as guidance how to correctly use 3rd party Python packages in code actions.
These snippets are usually retrieved by freeact agents themselves using skills that provide specialized search functionality.

- simplify bullet points (plakativer, ...) -> move details/explanation to paragraphs below ...
- compare with standard tool use (equivalence and differences)
- explain skill more explicitly
- paper reference
- any LLM can be used
- no scaffold, LLM makes decisions
- Actions generated at one step can be reused as tools in later step to 
