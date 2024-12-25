"""This module defines the interfaces of code action models. A code action
model is a model that responds with code if it decides to perform an action
in the environment.

This module defines the core interfaces that code action models must implement
to work with the `freeact` agent system. It defines abstract base classes for:

- The main model interface (`CodeActModel`)
- Model interaction turns (`CodeActModelTurn`)
- Model responses (`CodeActModelResponse`)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class CodeActModelResponse(ABC):
    """A response from a code action model.

    Represents a single response from the model, which may contain executable code,
    error information, and tool usage metadata.

    Attributes:
        text: The raw text response from the model.
        is_error: Whether this response represents an error condition.
    """

    text: str
    is_error: bool

    @property
    @abstractmethod
    def tool_use_id(self) -> str | None: ...

    @property
    @abstractmethod
    def tool_use_name(self) -> str | None: ...

    @property
    @abstractmethod
    def code(self) -> str | None:
        """Executable code from the model response if present."""


@dataclass
class StreamRetry:
    """Emitted in a response stream to inform about a retry event.

    Used when streaming responses encounter temporary failures and need to retry.

    Attributes:
        cause: The reason for the retry attempt.
        retry_wait_time: Time in seconds to wait before retrying.
    """

    cause: str
    retry_wait_time: float


class CodeActModelTurn(ABC):
    """A single turn of interaction with a code action model.

    Supports both bulk response retrieval and incremental streaming of the model's
    output. Each turn represents one complete model interaction, whether from a
    user query or execution feedback.
    """

    @abstractmethod
    async def response(self) -> CodeActModelResponse:
        """Get the complete response for this model interaction turn.

        Waits for and returns the full model response, including any code blocks
        and metadata about tool usage.
        """

    @abstractmethod
    def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        """Stream the model's response as it is generated.

        Yields chunks of the response as they become available, allowing for
        real-time processing of model output.

        Args:
            emit_retry (bool): If `True`, emit `StreamRetry` objects when retries occur.
                             If `False`, handle retries silently. Defaults to `False`.

        Yields:
            str | StreamRetry: Either a chunk of the response text, or a `StreamRetry`
                             object if a retry event occurs and `emit_retry` is `True`.
        """


class CodeActModel(ABC):
    """Interface for models that can generate code actions.

    A code action model handles both initial user queries and feedback from code
    execution results. It decides when to generate code for execution and when to
    provide final responses to the user.
    """

    def request(self, user_query: str, **kwargs):
        """Creates a new interaction turn from a user query.

        Args:
            user_query: The user's input query or request
            **kwargs: Additional model-specific parameters

        Returns:
            A new turn object representing this interaction
        """

    @abstractmethod
    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> CodeActModelTurn:
        """Create a new interaction turn from execution feedback.

        Initiates a new interaction based on feedback from previous code execution,
        allowing the model to refine or correct its responses. A feedback turn must
        follow a previous request turn or feedback turn.

        Args:
            feedback (str): The feedback text from code execution.
            is_error (bool): Whether the feedback represents an error condition.
            tool_use_id (str | None): Identifier for the specific tool use instance.
            tool_use_name (str | None): Name of the tool that was used.
            **kwargs: Additional model-specific parameters for the feedback.

        Returns:
            CodeActModelTurn: A new turn object representing this interaction.
        """
        ...
