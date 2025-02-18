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
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict


@dataclass
class CodeActModelResponse(ABC):
    """A response from a code action model.

    Represents a single response from the model, which may contain executable code,
    error information, and tool usage metadata.

    Attributes:
        text: The raw text response from the model.
        is_error: Whether this response represents an error condition.
        token_usage: Provider-specific token usage data.
    """

    text: str
    is_error: bool
    token_usage: Dict[str, int] = field(default_factory=dict)

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
    def stream(self) -> AsyncIterator[str]:
        """Stream the model's response as it is generated.

        Yields chunks of the response as they become available, allowing for
        real-time processing of model output.
        """


class CodeActModel(ABC):
    """Interface for models that can generate code actions.

    A code action model handles both initial user queries and feedback from code
    execution results. It decides when to generate code for execution and when to
    provide final responses to the user.
    """

    @abstractmethod
    def request(self, user_query: str, **kwargs) -> CodeActModelTurn:
        """Creates a new interaction turn from a user query.

        Args:
            user_query: The user's input query or request
            **kwargs: Additional model-specific parameters

        Returns:
            CodeActModelTurn: A new turn object representing this interaction.
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
