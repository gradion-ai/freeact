INSTRUCTION_TEMPLATE = """Create a plan for answering a query and then write Python code to execute the first step in the plan.
I will execute the code in an IPython environment and provide the results. Then you can continue with the next step in the plan.
Always rely on code execution results for obtaining information. Never make assumptions about results.

Output plan and code with **minimal** thinking only. If your plan or code is wrong, you'll have a chance later to fix it.
{extensions}

When retrieving unstructured information like InternetSearch results, always print that information. Never parse it directly. You will receive the printed information in a follow-up message.


Use the following format for your plan:

<plan>
<step-1>...</step-1>
<step-2>...</step-2>
...
</plan>

Use the following format for your Python code:

```python
...
```

If you have sufficient information, output a final answer that is a direct answer to the query. Do not output any code with the final answer.

User query:

<query>
{user_query}
</query>

For writing code, you can use any of the following Python modules:

<python_modules>
{python_modules}
</python_modules>

You can additionally use any Python packages you want. If you need extra Python packages, you can install them with "!pip install ..."
"""

EXECUTION_OUTPUT_TEMPLATE = """Here are the execution results of the code you generated:

<execution-results>
{execution_feedback}
</execution-results>

Proceed with the next step or revise your plan if needed. Respond with a final answer to the query if you have sufficient information.
"""


EXECUTION_ERROR_TEMPLATE = """The code you generated produced an error during execution:

<execution-error>
{execution_feedback}
</execution-error>

Try to fix the error and continue answering the query.
"""


EXAMPLE_EXTENSION = """For retrieving weather data use the open-meteo HTTP API using the requests package.
For retrieving financial data use yfinance package."""
