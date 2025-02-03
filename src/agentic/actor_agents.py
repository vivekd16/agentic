from thespian.actors import Actor, ActorSystem, ActorAddress
from typing import Any, Optional, Generator
from dataclasses import dataclass
from functools import partial
from collections import defaultdict
import json
from pprint import pprint
from datetime import datetime
import secrets

from typing import Callable, Any, List
from pydantic import Field
from swarm import Swarm
from swarm.types import AgentFunction, Function, ChatCompletionMessageToolCall, Response
from swarm.util import merge_chunk, debug_print

from .events import (
    Event,
    Prompt, 
    Output, 
    ChatOutput, 
    ToolCall, 
    ChatStart, 
    ChatEnd, 
    TurnEnd, 
    AgentResume,
    SetState, 
    AddChild, 
    PauseToolResult,
    PauseAgent,
    PauseAgentResult,
    PAUSE_AGENT_SENTINEL,
    PAUSE_FOR_CHILD_SENTINEL
)

from thespian.actors import Actor, ActorSystem

@dataclass
class AgentPauseContext:
    orig_history_length: int
    tool_partial_response: Response
    sender: Optional[Actor] = None

class ActorBaseAgent(Actor):
    name: str = "Agent"
    model: str = "gpt-4o"
    instructions: str = "You are a helpful agent."
    functions: List[AgentFunction] = []
    tool_choice: str = None
    parallel_tool_calls: bool = True
    paused_context: Optional[AgentPauseContext] = None
    debug: bool = False
    depth: int = 0

    def __init__(self):
        super().__init__()
        self.children = {}
        self.tools = []
        self.swarm = Swarm()
        self.history: list = []
    
    @property
    def myid(self):
        return self.myAddress

    def _yield_completion_steps(self, context_variables: dict = {}):
        llm_message = {
            "content": "",
            "sender": self.name,
            "role": "assistant",
            "function_call": None,
            "tool_calls": defaultdict(
                lambda: {
                    "function": {"arguments": "", "name": ""},
                    "id": "",
                    "type": "",
                }
            ),
        }
        yield ChatStart(self.name)
        completion = self.swarm.get_chat_completion(
            agent=self,
            history=self.history,
            context_variables=context_variables,
            model_override=None,
            stream=True,
            debug=self.debug,
        )

        for chunk in completion:
            delta = json.loads(chunk.choices[0].delta.model_dump_json())
            if delta["role"] == "assistant":
                delta["sender"] = self.name
            if not delta.get('tool_calls'):
                yield ChatOutput(self.name, delta, self.depth)
            delta.pop("role", None)
            delta.pop("sender", None)
            merge_chunk(llm_message, delta)
        yield ChatEnd(self.name, llm_message)

    def relay_message(self, actor_message, sender):
        # When paused waiting on a child, forward messages from the child to the original caller
        # This is what allows child events to bubble up to root
        if (
            self.paused_context and                     # when paused we might get child events
            sender != self.paused_context.sender and    # make sure its not another Root command
            not isinstance(actor_message, TurnEnd)      # child TurnEnd events need to be processed as 'resume'
        ):
            # If we are paused, we will only respond to a prompt
            self.send(self.paused_context.sender, actor_message)
            return True
        
        return False

    def receiveMessage(self, actor_message, sender):
        if self.relay_message(actor_message, sender):
            return
        #print(f"[RECEIVE: {self.myAddress}/{self.name}: {actor_message} from {sender}")

        match actor_message:
            case Prompt() | TurnEnd() | AgentResume():
                if isinstance(actor_message, Prompt):
                    self.debug = actor_message.debug
                    self.log(f"Prompt: {actor_message}")
                    self.depth = actor_message.depth
                    init_len = len(self.history)
                    context_variables = {}
                    self.history.append({"role": "user", "content": actor_message.payload})
                elif isinstance(actor_message, (TurnEnd, AgentResume)):
                    assert self.paused_context, "TurnEnd/Resume received but no paused context is set"
                    init_len = self.paused_context.orig_history_length
                    # This little tricky bit grabs the full child output from the TurnEnd event
                    # and appends it to our history as the tool call result
                    tool_msgs = self.paused_context.tool_partial_response.messages
                    tool_msgs[-1]['content'] = actor_message.result
                    self.history.extend(tool_msgs)
                    context_variables = actor_message.context_variables.copy()
                    # Child calls BACK to parent, so we need to restore our original 'sender'
                    sender = self.paused_context.sender
                    self.paused_context = None

                # This is the agent "turn" loop. We keep running as long as the agent
                # requests more tool calls.
                # Critically, if a "wait_for_human" tool is requested, then we save our
                # 'turn' state, send a 'gather_input' event, and then we return. The caller
                # should call send another prompt when they have it and we will resume the turn.

                while len(self.history) - init_len < 10:
                    for event in self._yield_completion_steps():
                        #print("[event] ", event.__dict__)
                        self.send(sender, event)

                    assert isinstance(event, ChatEnd)

                    llm_message = event.payload
                    # these lines from Swarm.. not sure what they do
                    llm_message["tool_calls"] = list(
                        llm_message.get("tool_calls", {}).values())
                    if not llm_message["tool_calls"]:
                        llm_message["tool_calls"] = None

                    debug_print(self.debug, "Received completion:", llm_message)

                    self.history.append(llm_message)
                    if not llm_message["tool_calls"]:
                        # No more tool calls, so assume this turn is done
                        break

                    # convert tool_calls to objects
                    tool_calls = []
                    for tool_call in llm_message["tool_calls"]:
                        self.send(sender, ToolCall(self.name, tool_call, self.depth))
                        self.log(f"Calling tool: {tool_call}")
                        function = Function(
                            arguments=tool_call["function"]["arguments"],
                            name=tool_call["function"]["name"],
                        )
                        tool_call_object = ChatCompletionMessageToolCall(
                            id=tool_call["id"], function=function, type=tool_call["type"]
                        )
                        tool_calls.append(tool_call_object)

                    # handle function calls, updating context_variables, and switching agents
                    partial_response = self.swarm.handle_tool_calls(
                        tool_calls, self.functions, context_variables, debug=self.debug,
                    )
                    self.log(f"Tool result: {partial_response.messages}")
                    # Fixme: handle this better
                    if partial_response.messages[-1]['content'] == PAUSE_FOR_CHILD_SENTINEL:
                        # agent needs to pause to wait for a child. Should have notified the child already
                        self.paused_context = AgentPauseContext(
                            orig_history_length=init_len,
                            tool_partial_response=partial_response,
                            sender=sender,
                        )
                        return
                    elif request_msg := PauseAgentResult.deserialize(partial_response.messages[-1]['content']):
                        # agent needs to pause, notify the Root
                        self.paused_context = AgentPauseContext(
                            orig_history_length=init_len,
                            tool_partial_response=partial_response,
                            sender=sender,
                        )
                        self.send(sender, PauseAgent(self.name, request_msg))
                        return
                    
                    self.history.extend(partial_response.messages)
                    context_variables.update(partial_response.context_variables)

                # Altough we emit interim events, we also publish all the messages from this 'turn'
                # in the final event. This lets a caller process our "function result" with a single event
                self.send(sender, TurnEnd(self.name, self.history[init_len:], context_variables))
                self.paused_context = None

            case SetState():
                self.state = actor_message.payload
                self.name = self.state.get('name')
                self.logger = self.state.get('logger')
                self.tools = self.state.get('functions')
                setattr(self, 'functions', self.tools)
                self.instructions = self.state.get('instructions')
                if 'model' in self.state:
                    self.model = self.state['model']

                self.send(sender, Output(self.name, f"State updated: {actor_message.payload}", self.depth))

            case AddChild():
                child = self.createActor(ActorBaseAgent)
                self.send(child, SetState(self.name, actor_message.payload | {'logger': self.logger}))
                name = actor_message.payload['name']
                self.children[name] = child

                f = partial(self.call_child, child)

                llm_name = f"call_{name.lower().replace(' ', '_')}"
                setattr(f, '__name__', llm_name)
                f.__doc__ = self.call_child.__doc__
                setattr(f, '__code__', self.call_child.__code__)
                #Keep the original arg list
                f.__annotations__ = self.call_child.__annotations__
                self.functions.append(f)

    def call_child(
            self, 
            child_ref, 
            message,
        ):
        self.send(child_ref, Prompt(self.name, message, depth=self.depth+1, debug=self.debug))
        return PauseToolResult()

    def log(self, message):
        if self.debug:
            self.send(self.logger, f"({self.name}) {message}")

class Logger(Actor):
    def receiveMessage(self, message, sender):
        # format current time
        time = datetime.now().strftime("%H:%M:%S")
        # send message to console
        print(f"[{time} {message}]")


logger = None

def create_actor_system() -> tuple[ActorSystem, ActorAddress]:
    global logger

    asys = ActorSystem()
    if logger is None:
        logger = asys.createActor(Logger)
    return asys, logger

def get_funcs(thefuncs: list):
    useable = []
    for func in thefuncs:
        if callable(func):
            useable.append(func)
        else:
            useable.extend(func.get_tools())
    return useable 

def MakeAgent(name: str, instructions: str|None=None, functions: list = [], model: str|None=None):
    asys, logger = create_actor_system()
    instructions = instructions or "You are a helpful assistant."
    agent = asys.createActor(ActorBaseAgent, globalName = f"{name}-" + secrets.token_hex(4))
    model = model or "gpt-4o-mini"

    asys.ask(agent, SetState(name, {
        'name': name, 
        'logger': logger, 
        'instructions': instructions,
        'functions': get_funcs(functions),
        'model': model,
    }))
    return agent


class ActorAgent:   
    def __init__(
            self, 
            name, 
            instructions, 
            welcome: str|None=None,
            functions: list = [], 
            model: str|None=None,
        ):
        self._agent = MakeAgent(name, instructions, functions, model)
        self.actor = self._agent
        self.name = name
        self.welcome = welcome or f"Hello, I am {name}."
        
    def add_child(self, name: str, instructions: str, functions: list = [], model: str|None=None,
                  memories: list = []):
        asys, logger = create_actor_system()
        model = model or "gpt-4o-mini"
        asys.ask(self._agent, AddChild(name, {
            'name': name, 
            'logger': logger, 
            'instructions': instructions,
            'functions': get_funcs(functions),
            'model': model,
        }))

    def __repr__(self) -> str:
        return f"<ActorAgent: {self.name}>"
class ActorAgentRunner:
    def __init__(self, agent: ActorAgent, debug: bool = False) -> None:
        self.agent = agent
        self.asys, _ = create_actor_system()
        self.debug = debug

    def start(self, request: str):
        self.asys.tell(self.agent.actor, Prompt(self.agent.name, request, depth=0, debug=self.debug))

    def next(self, include_children: bool=True, timeout: int=10) -> Generator[Event, Any, Any]:
        while True:
            event: Event = self.asys.listen(timeout)
            if isinstance(event, (ChatStart, ChatEnd)):
                continue
            if isinstance(event, TurnEnd):
                break
            yield event

    def continue_with(self, response: str):
        self.asys.tell(self.agent.actor, TurnEnd(self.agent.name, [{"role": "user", "content": response}]))

def demo_loop(agent):
    runner = ActorAgentRunner(agent)

    print(agent.welcome)
    print("press <enter> to quit")
    while True:
        prompt = input("> ").strip()
        if prompt == 'quit' or prompt == '':
           break
        runner.start(prompt)

        for event in runner.next():
            #print("[event] " ,event.__dict__)
            if event is None:
                break
            elif event.requests_input():
                response = input(f"\n{event.request_message}\n>> ")
                runner.continue_with(response)
            else:
                if event.depth == 0:
                    print(event, end='')
        print()


def repl_loop(agent):
    asys, logger = create_actor_system()

    print(agent.welcome)
    while True:
        prompt = input("> ").strip()
        if prompt == 'quit':
           break

        # Send the prompt to the agent fire and forget
        asys.tell(agent.actor, Prompt(agent.name, prompt))
        linestart = True

        # And now read events waiting for the end
        while True:
            event = asys.listen(10)
            match event:
                case TurnEnd():
                    print()
                    linestart = True
                    break
                case Output() | ChatOutput():
                    if linestart:
                        print("."*(event.depth*4), end="")
                        linestart = False
                    print(event, end="")
                    if str(event).endswith('\n'):
                        linestart = True
                case ToolCall():
                    # using the logger for now, but could show in UI
                    #print(f"\n[tool - {event.agent}] ", event.payload, end="")
                    pass
                case PauseAgent():
                    response = input(f"\n{event.request_message} > ")
                    asys.tell(agent.actor, TurnEnd(agent.name, [{"role": "user", "content": response}]))
                    print(f"\n[Agent {event.agent} paused]")
                    