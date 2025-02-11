from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from typing import List, Callable, Union, Optional
from agentic.agentic_secrets import agentic_secrets
from agentic.settings import settings

# Third-party imports
from pydantic import BaseModel

AgentFunction = Callable[[], Union[str, "SwarmAgent", dict]] | dict


class RunContext:
    def __init__(self, agent, context: dict = {}, agent_name: str = ""):
        self._context = context
        self.agent_name = agent_name
        self.agent = agent

    def __getitem__(self, key):
        return self._context.get(key, None)

    def get(self, key, default=None):
        return self._context.get(key, default)

    def __setitem__(self, key, value):
        self._context[key] = value

    def update(self, context: dict):
        self._context.update(context)

    def get_agent(self) -> "Agent":
        return self.agent

    def get_config(self, key, default=None):
        return settings.get(
            self.agent_name + "/" + key, settings.get(key, self.get(key, default))
        )

    def set_config(self, key, value):
        settings.set(self.agent_name + "/" + key, value)

    def get_secret(self, key, default=None):
        return agentic_secrets.get_secret(
            self.agent_name + "/" + key,
            agentic_secrets.get_secret(key, self.get(key, default)),
        )

    def get_context(self) -> dict:
        return self._context

    def error(self, *args):
        print("ERROR:", *args)

    def info(self, *args):
        print("INFO:", *args)

    def warn(self, *args):
        print("WARNING:", *args)

    def __repr__(self):
        return f"RunContext({self._context})"


class SwarmAgent(BaseModel):
    name: str = "Agent"
    model: str = "gpt-4o"
    instructions_str: str = "You are a helpful agent."
    tool_choice: str = "auto"
    parallel_tool_calls: bool = True
    trim_context: bool = True
    max_tokens: bool = None

    def get_instructions(self, context: RunContext) -> str:
        return self.instructions_str


class Result(BaseModel):
    """
    Encapsulates the possible return values for an agent function.

    Attributes:
        value (str): The result value as a string.
        agent (Agent): The agent instance, if applicable.
        context_variables (dict): A dictionary of context variables.
    """

    value: str = ""
    agent: Optional[SwarmAgent] = None
    context_variables: dict = {}
    tool_function: Optional[Function] = None


class Response(BaseModel):
    messages: List = []
    agent: Optional[SwarmAgent] = None
    # These are meant to be updates to Run Context variables. But I think it's easier for
    # tools to just update RunContext directly.
    context_variables: dict = {}
    last_tool_result: Optional[Result] = None
