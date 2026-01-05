# Code Action Reuse

Any code action can be saved as a discoverable tool. This enables tool libraries to evolve as agents work. Composite code actions that chain multiple tools are a common example.

Freeact provides the [`saving-codeacts`](https://github.com/gradion-ai/freeact/tree/main/freeact/agent/config/templates/skills/saving-codeacts) skill for saving code actions as reusable tools. It separates interface (`api.py`) from implementation (`impl.py`). The interface contains the function signature, Pydantic models, and docstrings. The implementation contains the actual logic. 

This separation enables efficient tool discovery: agents inspect signatures and docstrings without loading implementation details. The implementation stays hidden, saving tokens and reducing distraction by keeping non-essential details out of context.

The following example shows how to [compose and save](#compose-and-save) a code action as a parameterized tool, then [discover and reuse](#discover-and-reuse) it in a new session.

## Compose and Save

!!! hint "Recorded session"

    A [recorded session](../recordings/saving-codeacts-1/conversation.html) of this example is appended [below](#recording-compose).

This example continues from [output parser generation](output-parser.md), where `search_repositories` was augmented with a `run_parsed()` function returning typed `Repository` objects. When asked to

> get the latest 5 commits of the 3 github repos of torvalds with the most stars. For each repo, output name, stars and the first line of commit messages, and the link to the commit

the agent discovers `search_repositories` and `list_commits` as appropriate tools and inspects their APIs. Because the enhanced `search_repositories` now defines typed output, the agent can compose both tools in a single code action, passing search results as input to `list_commits` calls. 

After executing the code action, when asked to

> save this as tool under category github, with username, top_n_repos, top_n_commits as parameter

the agent loads the `saving-codeacts` skill and follows its instructions to save the code action as a reusable, parameterized tool:

1. Creates the `gentools/github/commits_of_top_repos/` Python package
2. Defines the tool API with a parameterized `run()` function and Pydantic output models in `api.py`
3. Moves the implementation to `impl.py`, lazily imported by `run()`
4. Tests the saved tool to verify it works

The structure of the saved tool is:

```
gentools/
└── github/
    └── commits_of_top_repos/
        ├── __init__.py
        ├── api.py       # Public interface
        └── impl.py      # Implementation
```

[![Interactive mode](../recordings/saving-codeacts-1/conversation.svg)](../recordings/saving-codeacts-1/conversation.html){target="_blank" #recording-compose}

## Discover and Reuse

!!! hint "Recorded session"

    A [recorded session](../recordings/saving-codeacts-2/conversation.html) of this example is appended [below](#recording-reuse).

In a new session, the saved tool is discovered like any other Python tool. During discovery, only the API is inspected, not the implementation. When asked to

> get the latest 3 commits of the 2 github repos of torvalds with the most stars. For each repo, output name, stars and the first line of commit messages, and the link to the commit

the agent discovers the previously saved tool, inspects its API, and calls it with different parameters (`top_n_repos=2`, `top_n_commits=3`).

[![Interactive mode](../recordings/saving-codeacts-2/conversation.svg)](../recordings/saving-codeacts-2/conversation.html){target="_blank" #recording-reuse}
