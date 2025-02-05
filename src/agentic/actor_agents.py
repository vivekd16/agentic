from thespian.actors import Actor, ActorSystem, ActorAddress
from typing import Any, Optional, Generator
from dataclasses import dataclass
from functools import partial
from collections import defaultdict
from pathlib import Path
import json
import os
import sys
from pprint import pprint
from datetime import datetime
from agentic.secrets import agentic_secrets
import readline
from pathlib import Path
import secrets
import os
import yaml
from jinja2 import Template
from rich.markdown import Markdown
from .fix_console import ConsoleWithInputBackspaceFixed
from rich.live import Live
from rich.progress import Progress
import rich.spinner

import yaml
from typing import Callable, Any, List
from pydantic import Field
from .swarm import Swarm
from .swarm.types import AgentFunction, Response, SwarmAgent
from .swarm.util import merge_chunk, debug_print
from jinja2 import Template
import litellm
from litellm.types.utils import ModelResponse, Message
from litellm import completion_cost
from litellm import token_counter

from .events import (
    Event,
    Prompt,
    Output,
    ChatOutput,
    ToolCall,
    StartCompletion,
    FinishCompletion,
    TurnEnd,
    AgentResume,
    SetState,
    AddChild,
    PauseToolResult,
    PauseAgent,
    PauseAgentResult,
)

from thespian.actors import Actor, ActorSystem
from .colors import Colors

# Global console for Rich
console = ConsoleWithInputBackspaceFixed()

@dataclass
class AgentPauseContext:
    orig_history_length: int
    tool_partial_response: Response
    sender: Optional[Actor] = None


class ActorBaseAgent(SwarmAgent, Actor):
    name: str = "Agent"
    model: str = "gpt-4o"
    instructions: str = "You are a helpful agent."
    functions: List[AgentFunction] = []
    tool_choice: str = None
    parallel_tool_calls: bool = True
    paused_context: Optional[AgentPauseContext] = None
    debug: bool = False
    depth: int = 0
    children: dict = {}
    history: list = []
    _logger: Actor = None

    class Config:
        arbitrary_types_allowed=True

    def __init__(self):
        super().__init__()
        self.children = {}
        self._swarm = Swarm()
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
        yield StartCompletion(self.name)

        self._callback_params = {}
        def custom_callback(
            kwargs,                 # kwargs to completion
            completion_response,    # response from completion
            start_time, end_time    # start/end time
        ):
            try:
                response_cost = kwargs["response_cost"] # litellm calculates response cost for you
                self._callback_params['cost'] = response_cost
            except:
                pass
            self._callback_params['elapsed'] = end_time - start_time
            

        # Assign the custom callback function
        litellm.success_callback = [custom_callback]

        completion = self._swarm.get_chat_completion(
            agent=self,
            history=self.history,
            context_variables=context_variables,
            model_override=None,
            stream=True,
            debug=self.debug,
        )

        # With 'streaming' we get the response back in chunks. For the output text
        # we want to emit events progressively with that output, but for tool calls
        # we just want to detect the single tool call and describe it in the final 'llm_result'
        # that we return at the end.

        chunks = []
        for chunk in completion:
            chunks.append(chunk)
            delta = json.loads(chunk.choices[0].delta.model_dump_json())
            if delta["role"] == "assistant":
                delta["sender"] = self.name
            if not delta.get("tool_calls") and delta.get('content'):
                yield ChatOutput(self.name, delta, self.depth)
            delta.pop("role", None)
            delta.pop("sender", None)

        llm_message = litellm.stream_chunk_builder(chunks, messages=self.history)
        input = self.history[-1:]
        output = llm_message.choices[0].message
        
        if len(input) > 0:
             self._callback_params['input_tokens'] = token_counter(self.model, messages=self.history[-1:])
        if output.content:
            self._callback_params['output_tokens'] = token_counter(self.model, text=llm_message.choices[0].message.content)
        # Have to calc cost after we have seen all the chunks
        debug_print(self.debug, "That completion cost you: ", self._callback_params)

        yield FinishCompletion.create(
            self.name, 
            llm_message.choices[0].message,
            self.model,
            self._callback_params.get('cost', 0),
            self._callback_params.get('input_tokens'),
            self._callback_params.get('output_tokens'),
            self._callback_params.get('elapsed'),
        )

    def relay_message(self, actor_message, sender):
        # When paused waiting on a child, forward messages from the child to the original caller
        # This is what allows child events to bubble up to root
        if (
            self.paused_context  # when paused we might get child events
            and sender
            != self.paused_context.sender  # make sure its not another Root command
            and not isinstance(
                actor_message, TurnEnd
            )  # child TurnEnd events need to be processed as 'resume'
        ):
            # If we are paused, we will only respond to a prompt
            self.send(self.paused_context.sender, actor_message)
            return True

        return False

    def receiveMessage(self, actor_message, sender):
        if self.relay_message(actor_message, sender):
            return
        # print(f"[RECEIVE: {self.myAddress}/{self.name}: {actor_message} from {sender}")

        match actor_message:
            case Prompt() | TurnEnd() | AgentResume():
                if isinstance(actor_message, Prompt):
                    self.debug = actor_message.debug
                    self.log(f"Prompt: {actor_message}")
                    self.depth = actor_message.depth
                    init_len = len(self.history)
                    context_variables = {}
                    self.history.append(
                        {"role": "user", "content": actor_message.payload}
                    )
                elif isinstance(actor_message, (TurnEnd, AgentResume)):
                    assert (
                        self.paused_context
                    ), f"TurnEnd/Resume received but no paused context is set in {self.name}"
                    init_len = self.paused_context.orig_history_length
                    # This little tricky bit grabs the full child output from the TurnEnd event
                    # and appends it to our history as the tool call result
                    tool_msgs = self.paused_context.tool_partial_response.messages
                    tool_msgs[-1]["content"] = actor_message.result
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
                        #print("[eeeevent] ", event.__dict__)
                        self.send(sender, event)

                    assert isinstance(event, FinishCompletion)

                    response: Message = event.response
                    # these lines from Swarm.. not sure what they do

                    debug_print(self.debug, "Received completion:", response)
                    
                    self.history.append(response)
                    if not response.tool_calls:
                        # No more tool calls, so assume this turn is done
                        break

                    # handle function calls, updating context_variables, and switching agents
                    partial_response = self._swarm.handle_tool_calls(
                        response.tool_calls,
                        self.functions,
                        context_variables,
                        debug=self.debug,
                    )
                    self.log(f"Tool result: {partial_response.messages}")
                    # Fixme: handle this better
                    if (
                        PauseToolResult.matches_sentinel(partial_response.messages[-1]["content"])
                    ):
                        # agent needs to pause to wait for a child. Should have notified the child already
                        self.paused_context = AgentPauseContext(
                            orig_history_length=init_len,
                            tool_partial_response=partial_response,
                            sender=sender,
                        )
                        return
                    elif request_msg := PauseAgentResult.deserialize(
                        partial_response.messages[-1]["content"]
                    ):
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
                self.send(
                    sender,
                    TurnEnd(self.name, self.history[init_len:], context_variables),
                )
                self.paused_context = None

            case SetState():
                state = actor_message.payload
                self.name = state.get("name")
                self._logger = state.get("logger")
                self.functions = []
                for f in state.get("functions"):
                    if isinstance(f, AddChild):
                        f = self._build_child_func(f)
                    self.functions.append(f)
                self.instructions = state.get("instructions")
                if "model" in state:
                    self.model = state["model"]

                self.send(
                    sender,
                    Output(
                        self.name, f"State updated: {actor_message.payload}", self.depth
                    ),
                )

            case AddChild():
                self.functions.append(
                    self._build_child_func(actor_message)
                )

    def _build_child_func(self, event: AddChild) -> Callable:
        child = event.actor_ref
        name = event.agent
        self.children[name] = child

        f = partial(self.call_child, child, event.handoff)

        llm_name = f"call_{name.lower().replace(' ', '_')}"
        setattr(f, "__name__", llm_name)
        f.__doc__ = self.call_child.__doc__
        setattr(f, "__code__", self.call_child.__code__)
        # Keep the original arg list
        f.__annotations__ = self.call_child.__annotations__
        return f

    def call_child(
        self,
        child_ref,
        handoff: bool,
        message,
    ):
        self.send(
            child_ref,
            Prompt(self.name, message, depth=self.depth + 1, debug=self.debug),
        )
        return PauseToolResult()

    def log(self, message):
        if self.debug:
            self.send(self._logger, f"({self.name}) {message}")


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

class HandoffAgentWrapper:
    def __init__(self, agent):
        self.agent = agent

    def get_agent(self):
        return self.agent

def handoff(agent, **kwargs):
    """ Signal that a child agent should take over the execution context instead of being
        called as a subroutine. """
    return HandoffAgentWrapper(agent)    

class AgentBase:
    pass

class ActorAgent(AgentBase):
    def __init__(
        self,
        name: str,
        instructions: str | None = None,
        welcome: str | None = None,
        tools: list = [],
        model: str | None = None,
        template_dir: str | Path = None
    ):
        self.name = name
        self.welcome = welcome or f"Hello, I am {name}."
        self.model = model or "gpt-4o-mini"
        self.template_dir = template_dir
        self._tools = tools
        
        # Initialize the base actor
        self._init_base_actor(instructions)
        
        # Ensure API key is set
        self.ensure_api_key_for_model(self.model)

    def _init_base_actor(self, instructions: str | None):
        """Initialize the underlying actor system with the given instructions."""
        asys, logger = create_actor_system()
        
        # Process instructions if provided
        if instructions:
            template = Template(instructions)
            self.instructions = template.render(**self.prompt_variables)
        else:
            self.instructions = "You are a helpful assistant."
            
        # Create the base actor
        self._actor = asys.createActor(
            ActorBaseAgent, 
            # We don't stricly need names, and Im not sure if it changes behavior in case you
            # tried to use the same name, like for a test.
            #globalName=f"{self.name}-{secrets.token_hex(4)}"
        )
        
        # Set initial state. Small challenge is that a child agent might have been
        # provided in tools. But we need to initialize ourselve
        asys.ask(
            self._actor,
            SetState(
                self.name,
                {
                    "name": self.name,
                    "logger": logger,
                    "instructions": self.instructions,
                    "functions": self._get_funcs(self._tools),
                    "model": self.model,
                },
            ),
        )

    def _get_funcs(self, thefuncs: list):
        useable = []
        for func in thefuncs:
            if callable(func):
                useable.append(func)
            elif isinstance(func, AgentBase):
                # add a child agent as a tool
                useable.append(AddChild(
                        func.name,
                        func._actor,
                    )
                )
            else:
                useable.extend(func.get_tools())
        return useable


    def add_child(self, child_agent: 'ActorAgent'):
        """
        Add a child agent to this agent.
        
        Args:
            child_agent: Another ActorAgent instance to add as a child
        """
        asys, logger = create_actor_system()
        
        # sending the AddChild event has the effect of adding the child function
        # to our list of tool functions
        asys.ask(
            self._actor,
            AddChild(
                child_agent.name,
                child_agent._actor,
            ),
        )

    @property
    def prompt_variables(self) -> dict:
        """Dictionary of variables to make available to prompt templates."""
        prompts_filename = f"{self.safe_name}.prompts.yaml"
        paths_to_search = [
            self.template_dir if self.template_dir else Path.cwd(),
        ]

        for path in paths_to_search:
            prompts_file = Path(path) / prompts_filename
            print(prompts_file)

            if prompts_file.exists():
                with open(prompts_file, "r") as f:
                    prompts = yaml.safe_load(f)
                return prompts

        return {"name": "John Doe"}

    @property
    def safe_name(self) -> str:
        """Renders the ActorAgent's name, but filesystem safe."""
        return "".join(c if c.isalnum() else "_" for c in self.name).lower()

    def ensure_api_key_for_model(self, model: str):
        """Ensure the appropriate API key is set for the given model."""
        for key in agentic_secrets.list_secrets():
            if key not in os.environ:
                os.environ[key] = agentic_secrets.get_secret(key)

    def __repr__(self) -> str:
        return f"<ActorAgent: {self.name}>"


from rich.live import Live
from rich.markdown import Markdown
from rich.columns import Columns
from rich.spinner import Spinner
from rich.console import Console
from rich.layout import Layout
class ActorAgentRunner:
    def __init__(self, agent: ActorAgent, debug: bool = False) -> None:
        self.agent = agent
        self.asys, _ = create_actor_system()
        self.debug = debug

    def start(self, request: str):
        self.asys.tell(
            self.agent._actor,
            Prompt(self.agent.name, request, depth=0, debug=self.debug),
        )

    def run_sync(self, request: str, debug: bool = False) -> str:
        """ Runs the agent and waits for the turn to finish, then returns the results
            of all output events as a single string."""
        if debug:
            self.debug = True        
        self.start(request)
        results = []
        for event in self.next(include_children=False):
            if self.debug:
                print(f"{event.debug(True)}")
            results.append(str(event))

        return "".join(results)
    
    def next(
        self, include_children: bool = True, timeout: int = 10, include_completions: bool = False,
    ) -> Generator[Event, Any, Any]:
        while True:
            event: Event = self.asys.listen(timeout)
            if not include_completions and isinstance(event, (StartCompletion, FinishCompletion)):
                continue
            if isinstance(event, TurnEnd):
                break
            yield event

    def continue_with(self, response: str):
        self.asys.tell(
            self.agent._actor,
            TurnEnd(self.agent.name, [{"role": "user", "content": response}]),
        )

    def repl_loop(self):
        hist = os.path.expanduser("~/.agentic_history")
        if os.path.exists(hist):
            readline.read_history_file(hist)

        print(self.agent.welcome)
        print("press <enter> to quit")

        @dataclass
        class Modelcost:
            model: str
            inputs: int 
            calls: int
            outputs: int
            cost: float
            time: float

        def print_stats_report(completions: list[FinishCompletion]):
            costs = dict[str, Modelcost]()
            for comp in completions:
                if comp.metadata['model'] not in costs:
                    costs[comp.metadata['model']] = Modelcost(
                        comp.metadata['model'],
                        0,
                        0,
                        0,
                        0,
                        0
                    )
                mc = costs[comp.metadata['model']]
                mc.calls += 1
                mc.cost += comp.metadata['cost']*100
                mc.inputs += comp.metadata['input_tokens']
                mc.outputs += comp.metadata['output_tokens']
                if 'elapsed_time' in comp.metadata:
                    mc.time += comp.metadata['elapsed_time'].total_seconds()
            for mc in costs.values():
                yield ( 
                    f"[{mc.model}: {mc.calls} calls, tokens: {mc.inputs} -> {mc.outputs}, {mc.cost:.2f} cents, time: {mc.time:.2f}s]"
                )
                
        saved_completions = []

        while True:
            try:
                # Get input directly from sys.stdin
                line = console.input("> ")

                if line == "quit" or line == "":
                    break

                output = ""
                with console.status("[bold blue]thinking...", spinner="dots") as status:
                    with Live(Markdown(output), refresh_per_second=1, auto_refresh=True) as live:
                        spinner = rich.spinner.Spinner("dots")
                        self.start(line)

                        for event in self.next(include_completions=True):
                            if event is None:
                                break
                            elif event.requests_input():
                                response = input(f"\n{event.request_message}\n>>>> ")
                                self.continue_with(response)
                            elif isinstance(event, FinishCompletion):
                                saved_completions.append(event)
                            else:
                                if event.depth == 0:
                                    output += str(event)
                                    live.update(Markdown(output))
                        output += "\n\n"
                        live.update(Markdown(output))
                for row in print_stats_report(saved_completions):
                    console.out(row)
                readline.write_history_file(hist)
            except EOFError:
                print("\nExiting REPL.")
                break
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt. Type 'exit()' to quit.")
            except Exception as e:
                print(f"Error: {e}")

