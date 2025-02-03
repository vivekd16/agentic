from dataclasses import dataclass
from typing import Any
from swarm.types import Result
import json

@dataclass
class Event:
    agent: str
    type: str
    payload: Any
    depth: int = 0

    def print(self):
        print(self)

    def requests_input(self):
        return isinstance(self, PauseAgent)

    def __str__(self) -> str:
        return str(self.payload or '')
        
    def _safe(self, d, keys: list[str], default_val=None):
        for k in keys:
            if k in d:
                d = d[k]
            else:
                return default_val
        return d or default_val
    
class Prompt(Event):
    debug: bool = False

    def __init__(self, agent: str, message: str, depth: int = 0, debug: bool = False):
        super().__init__(agent, 'prompt', message, depth)
        self.debug = debug

class Output(Event):
    def __init__(self, agent: str, message: str, depth: int = 0):
        super().__init__(agent, 'output', message, depth=depth)

    def __str__(self) -> str:
        return str(self.payload or '')

    def __repr__(self) -> str:
        return repr(self.__dict__)
    
class ChatOutput(Output):
    def __init__(self, agent: str, payload: dict, depth: int = 0):
        Event.__init__(self, agent, 'chat_output', payload, depth)

    def __str__(self) -> str:
        return str(self.payload.get('content') or '')
    
    def __repr__(self) -> str:
        return repr(self.__dict__)
    
class ToolCall(Event):
    def __init__(self, agent: str, details: Any, depth: int = 0):
        super().__init__(agent, 'tool_call', details, depth=depth)

    def __str__(self):
        d = self.payload
        name = self._safe(d, ['function','name'])
        args = self._safe(d, ['function', 'arguments'], '{}')
        return "--"*(self.depth+1) + f"> {name}({args})"
    
class ChatStart(Event):
    def __init__(self, agent: str):
        super().__init__(agent, 'chat_start', {})

class ChatEnd(Event):
    def __init__(self, agent: str, llm_message: str):
        super().__init__(agent, 'chat_end', llm_message)

class TurnEnd(Event):
    def __init__(self, agent: str, messages: list, context_variables: dict = {}):
        super().__init__(agent, 'turn_end', {"messages": messages, "vars": context_variables})

    @property
    def messages(self):
        return self.payload['messages']

    @property
    def result(self):
        return self.messages[-1]['content']
    
    @property
    def context_variables(self):
        return self.payload['vars']    

class AgentResume(Event):
    def __init__(self, agent: str, response: str):
        super().__init__(agent, 'resume', response)

    @property
    def result(self):
        return self.payload
    
    @property
    def context_variables(self):
        return {}

class SetState(Event):
    def __init__(self, agent, state: dict):
        super().__init__(agent, 'set_state', state)

class AddChild(Event):
    def __init__(self, agent, state: dict):
        super().__init__(agent, 'add_child', state)

PAUSE_AGENT_SENTINEL = "__PAUSE__"
PAUSE_FOR_CHILD_SENTINEL = "__PAUSE__CHILD"

class PauseAgent(Event):
    # Whenenever the agent needs to pause, either to wait for human input or a response from
    # another agent, we emit this event.
    def __init__(self, agent, request_message: str):
        super().__init__(agent, PAUSE_AGENT_SENTINEL, request_message)

    @property
    def request_message(self):
        return self.payload

# Gonna snuggle this through the Swarm tool call
class PauseToolResult(Result):
    def __init__(self):
        super().__init__(value=PAUSE_FOR_CHILD_SENTINEL)

class PauseAgentResult(Result):
    def __init__(self, request_message: str):
        super().__init__(value=json.dumps(
            {"_key": PAUSE_AGENT_SENTINEL, 
             "request_message": request_message
            }))
    
    @staticmethod
    def deserialize(value):
        try:
            d = json.loads(value)
            if d.get('_key') == PAUSE_AGENT_SENTINEL:
                return d.get('request_message')
        except:
            return None
