EXECUTION_OUTPUT_TEMPLATE = """The code was executed successfully. Here is the output:

<execution-output>
{execution_feedback}
</execution-output>

Based on this result, you can now:
1. Interpret the output for the user
2. Determine if additional code execution is needed
3. Refine your approach if the results aren't as expected

Remember to explain what the output means in relation to the user's original request.
"""


EXECUTION_ERROR_TEMPLATE = """The code execution resulted in an error. Here's the error message:

<error-message>
{execution_feedback}
</error-message>

Please:
1. Carefully analyze the error message to identify the root cause
2. Explain the issue to the user in simple terms
3. Revise your code to address the specific error
4. Consider common causes for this type of error:
   - Syntax errors
   - Missing imports or undefined variables
   - Type mismatches
   - Logic errors in your implementation
   - Missing dependencies that need installation

When submitting revised code, focus on addressing the specific error while maintaining your overall solution approach.
"""
