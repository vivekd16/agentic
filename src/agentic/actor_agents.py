import atexit
from thespian.actors import Actor, ActorSystem, ActorAddress
from typing import Any, Optional, Generator
from dataclasses import dataclass
from functools import partial
from collections import defaultdict
from pathlib import Path
import json
import os
import time
import traceback
from copy import deepcopy
from pprint import pprint
from datetime import datetime
from agentic.agentic_secrets import agentic_secrets
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
from .swarm.types import (
    AgentFunction,
    Response,
    SwarmAgent,
    Result,
    ChatCompletionMessageToolCall,
    Function,
)
from .swarm.util import merge_chunk, debug_print
from jinja2 import Template
import litellm
from litellm.types.utils import ModelResponse, Message
from litellm import completion_cost
from litellm import token_counter

from .events import (
    Event,
    Prompt,
    PromptStarted,
    ResetHistory,
    Output,
    ChatOutput,
    ToolCall,
    ToolResult,
    StartCompletion,
    FinishCompletion,
    FinishAgentResult,
    TurnEnd,
    SetState,
    AddChild,
    WaitForInput,
    PauseForInputResult,
    PauseForChildResult,
    ResumeWithInput,
)

from thespian.actors import Actor, ActorSystem, PoisonMessage
from .colors import Colors

# Global console for Rich
console = ConsoleWithInputBackspaceFixed()


@dataclass
class AgentPauseContext:
    orig_history_length: int
    tool_partial_response: Response
    sender: Optional[Actor] = None
    tool_function: Optional[Function] = None


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
    # The Actor who sent us our Prompt
    _prompter: Actor = None
    max_tokens: int = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self):
        super().__init__()
        self.children = {}
        self._swarm = Swarm()
        self.history: list = []

    @property
    def myid(self):
        return self.myAddress

    def inject_secrets_into_env(self):
        """Ensure the appropriate API key is set for the given model."""
        for key in agentic_secrets.list_secrets():
            if key not in os.environ:
                os.environ[key] = agentic_secrets.get_secret(key)

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
            kwargs,  # kwargs to completion
            completion_response,  # response from completion
            start_time,
            end_time,  # start/end time
        ):
            try:
                response_cost = kwargs[
                    "response_cost"
                ]  # litellm calculates response cost for you
                self._callback_params["cost"] = response_cost
            except:
                pass
            self._callback_params["elapsed"] = end_time - start_time

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
            if not delta.get("tool_calls") and delta.get("content"):
                yield ChatOutput(self.name, delta, self.depth)
            delta.pop("role", None)
            delta.pop("sender", None)

        llm_message = litellm.stream_chunk_builder(chunks, messages=self.history)
        input = self.history[-1:]
        output = llm_message.choices[0].message

        if len(input) > 0:
            self._callback_params["input_tokens"] = token_counter(
                self.model, messages=self.history[-1:]
            )
        if output.content:
            self._callback_params["output_tokens"] = token_counter(
                self.model, text=llm_message.choices[0].message.content
            )
        # Have to calc cost after we have seen all the chunks
        debug_print(
            self._swarm.llm_debug, "That completion cost you: ", self._callback_params
        )

        yield FinishCompletion.create(
            self.name,
            llm_message.choices[0].message,
            self.model,
            self._callback_params.get("cost", 0),
            self._callback_params.get("input_tokens"),
            self._callback_params.get("output_tokens"),
            self._callback_params.get("elapsed"),
        )

    def relay_message(self, actor_message, sender):
        if self._prompter and sender != self._prompter:
            # Relay sub-agent messages to our prompter so they "bubble up"
            self.send(self._prompter, actor_message)

    def receiveMessage(self, actor_message, sender):
        self.relay_message(actor_message, sender)
        # print(f"[RECEIVE: {self.myAddress}/{self.name}: {actor_message} from {sender}")

        def report_calling_tool(name: str, args: dict):
            self.send(sender, ToolCall(self.name, name, args))

        def report_tool_result(name: str, result):
            self.send(sender, ToolResult(self.name, name, result))

        match actor_message:
            case Prompt() | TurnEnd() | ResumeWithInput():
                if isinstance(actor_message, Prompt):
                    self.debug = actor_message.debug
                    self._prompter = sender
                    # self.log(f"Prompt: {actor_message}")
                    self.depth = actor_message.depth
                    init_len = len(self.history)
                    context_variables = {}
                    self.history.append(
                        {"role": "user", "content": actor_message.payload}
                    )
                    self.send(
                        sender,
                        PromptStarted(self.name, actor_message.payload, self.depth),
                    )
                elif isinstance(actor_message, TurnEnd):
                    # Sub-agent call "as tool" has completed. So finish our tool call with the agent result as the tool result
                    if not self.paused_context:
                        self.log(
                            "Ignoring TurnEnd/ResumeWithInput event, parent not paused: ",
                            actor_message,
                        )
                        return
                    init_len = self.paused_context.orig_history_length
                    # This little tricky bit grabs the full child output from the TurnEnd event
                    # and appends it to our history as the tool call result
                    tool_msgs = self.paused_context.tool_partial_response.messages
                    tool_msgs[-1]["content"] = actor_message.result
                    self.history.extend(tool_msgs)

                    # Copy human input into our context
                    context_variables = actor_message.context_variables.copy()
                    # Child calls BACK to parent, so we need to restore our original 'sender'
                    sender = self.paused_context.sender
                    self.paused_context = None

                elif isinstance(actor_message, ResumeWithInput):
                    # Call resuming us with user input after wait. We re-call our tool function after merging the human results
                    if not self.paused_context:
                        self.log(
                            "Ignoring ResumeWithInput event, parent not paused: ",
                            actor_message,
                        )
                        return
                    init_len = self.paused_context.orig_history_length
                    # Copy human input into our context
                    context_variables = actor_message.request_keys.copy()
                    # Re-call our tool function
                    tool_function = self.paused_context.tool_function
                    if tool_function is None:
                        raise RuntimeError(
                            "Tool function not found on AgentResume event"
                        )
                    # FIXME: Would be nice to DRY up the tool call handling
                    partial_response = self._swarm.handle_tool_calls(
                        self,
                        [
                            ChatCompletionMessageToolCall(
                                id=(tool_function._request_id or ""),
                                function=tool_function,
                                type="function",
                            )
                        ],
                        self.functions,
                        context_variables,
                        self.debug,
                        report_calling_tool,
                        report_tool_result,
                    )
                    self.history.extend(partial_response.messages)
                    context_variables.update(partial_response.context_variables)

                # This is the agent "turn" loop. We keep running as long as the agent
                # requests more tool calls.
                # Critically, if a "wait_for_human" tool is requested, then we save our
                # 'turn' state, send a 'gather_input' event, and then we return. The caller
                # should call send another prompt when they have it and we will resume the turn.

                while len(self.history) - init_len < 10:
                    for event in self._yield_completion_steps():
                        # event] ", event.__dict__)
                        if event is None:
                            breakpoint()
                        self.send(sender, event)

                    assert isinstance(event, FinishCompletion)

                    response: Message = event.response
                    # these lines from Swarm.. not sure what they do

                    debug_print(self._swarm.llm_debug, "Received completion:", response)

                    self.history.append(response)
                    if not response.tool_calls:
                        # No more tool calls, so assume this turn is done
                        break

                    # handle function calls, updating context_variables, and switching agents
                    partial_response = self._swarm.handle_tool_calls(
                        self,
                        response.tool_calls,
                        self.functions,
                        context_variables,
                        self.debug,
                        report_calling_tool,
                        report_tool_result,
                    )

                    # FIXME: handle this better, and handle the case of multiple tool calls

                    last_tool_result: Result | None = partial_response.last_tool_result
                    if last_tool_result:
                        if PauseForChildResult.matches_sentinel(last_tool_result.value):
                            # agent needs to pause to wait for a child. Should have notified the child already
                            # child will call us back with TurnEnd
                            self.paused_context = AgentPauseContext(
                                orig_history_length=init_len,
                                tool_partial_response=partial_response,
                                sender=sender,
                            )
                            return
                        elif PauseForInputResult.matches_sentinel(
                            last_tool_result.value
                        ):
                            # tool function has request user input. We save the tool function so we can re-call it when
                            # we get the response back
                            self.paused_context = AgentPauseContext(
                                orig_history_length=init_len,
                                tool_partial_response=partial_response,
                                sender=sender,
                                tool_function=last_tool_result.tool_function,
                            )
                            self.send(
                                sender,
                                WaitForInput(
                                    self.name, last_tool_result.context_variables
                                ),
                            )
                            return
                        elif FinishAgentResult.matches_sentinel(
                            partial_response.messages[-1]["content"]
                        ):
                            # short-circuit any further agent execution. But for chat history we need to
                            # record a result from the tool call
                            msg = deepcopy(partial_response.messages[-1])
                            msg["content"] = ""
                            self.history.extend(partial_response.messages)
                            break

                    self.history.extend(partial_response.messages)
                    context_variables.update(partial_response.context_variables)

                # Altough we emit interim events, we also publish all the messages from this 'turn'
                # in the final event. This lets a caller process our "function result" with a single event
                if isinstance(actor_message, Prompt):
                    self.send(
                        sender,
                        TurnEnd(self.name, self.history[init_len:], context_variables),
                    )
                self.paused_context = None

            case SetState():
                self.inject_secrets_into_env()
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
                if "max_tokens" in state:
                    self.max_tokens = state["max_tokens"]

                self.send(
                    sender,
                    Output(
                        self.name, f"State updated: {actor_message.payload}", self.depth
                    ),
                )

            case AddChild():
                self.functions.append(self._build_child_func(actor_message))

            case ResetHistory():
                self.history = []

    def _build_child_func(self, event: AddChild) -> Callable:
        child = event.actor_ref
        name = event.agent
        self.children[name] = child

        f = partial(self.call_child, child, event.handoff)

        llm_name = f"call_{name.lower().replace(' ', '_')}"
        setattr(f, "__name__", llm_name)
        f.__doc__ = f"Send a message to sub-agent {name}"
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
        depth = self.depth if handoff else self.depth + 1
        self.send(
            child_ref,
            Prompt(
                self.name,
                message,
                depth=depth,
                debug=self.debug,
            ),
        )
        if handoff:
            return FinishAgentResult()
        else:
            return PauseForChildResult(values={})

    def log(self, *args):
        message = " ".join([str(a) for a in args])
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

    if os.environ.get("AGENTIC_SIMPLE_ACTORS"):
        asys = ActorSystem()
    else:
        asys = ActorSystem("multiprocTCPBase")
    if logger is None:
        logger = asys.createActor(Logger)
    return asys, logger


def shutdown_actor_system():
    asys = ActorSystem("multiprocTCPBase")
    asys.shutdown()


atexit.register(shutdown_actor_system)


class HandoffAgentWrapper:
    def __init__(self, agent):
        self.agent = agent

    def get_agent(self):
        return self.agent


def handoff(agent, **kwargs):
    """Signal that a child agent should take over the execution context instead of being
    called as a subroutine."""
    return HandoffAgentWrapper(agent)


class AgentBase:
    pass


class ActorAgent(AgentBase):
    def __init__(
        self,
        name: str,
        instructions: str | None = "You are a helpful assistant.",
        welcome: str | None = None,
        tools: list = [],
        model: str | None = None,
        template_dir: str | Path = None,
        max_tokens: int = None,
    ):
        self.name = name
        self.welcome = welcome or f"Hello, I am {name}."
        self.model = model or "gpt-4o-mini"
        self.template_dir = template_dir
        self._tools = tools
        self.max_tokens = max_tokens

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
            # globalName=f"{self.name}-{secrets.token_hex(4)}"
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
                    "max_tokens": self.max_tokens,
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
                useable.append(
                    AddChild(
                        func.name,
                        func._actor,
                    )
                )
            elif isinstance(func, HandoffAgentWrapper):
                # add a child agent as a tool
                useable.append(
                    AddChild(
                        func.agent.name,
                        func.agent._actor,
                        handoff=True,
                    )
                )
            else:
                useable.extend(func.get_tools())
        return useable

    def add_child(self, child_agent: "ActorAgent"):
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


class ActorAgentRunner:
    def __init__(self, agent: ActorAgent, debug: bool = False) -> None:
        self.agent = agent
        self.asys, _ = create_actor_system()
        self.debug = debug or os.environ.get("AGENTIC_DEBUG")

    def start(self, request: str):
        self.asys.tell(
            self.agent._actor,
            Prompt(self.agent.name, request, depth=0, debug=self.debug),
        )

    def turn(self, request: str, debug: bool = False) -> str:
        """Runs the agent and waits for the turn to finish, then returns the results
        of all output events as a single string."""
        if debug:
            self.debug = True
        self.start(request)
        results = []
        for event in self.next(include_children=False):
            if self.debug:
                print(f"{event.debug(True)}")

            if self._should_print(event):
                results.append(str(event))

        return "".join(results)

    def __lshift__(self, prompt: str):
        print(self.turn(prompt))

    def _should_print(self, event: Event) -> bool:
        flag = self.debug or ""
        if flag == True or flag == "all":
            return True
        if event.is_output:
            return True
        elif isinstance(event, (ToolCall, ToolResult, PromptStarted)):
            return "tools" in flag
        else:
            return False

    def next(
        self,
        include_children: bool = True,
        timeout: int = 10,
        include_completions: bool = False,
    ) -> Generator[Event, Any, Any]:
        agents_running = set([self.agent.name])
        waiting_final_timestamp = None
        while True:
            event: Event = (
                self.asys.listen(1)
                if waiting_final_timestamp
                else self.asys.listen(timeout)
            )
            if event is None:
                break
            if isinstance(event, PoisonMessage):
                print("Agent unexpected error: ", event)
                continue
            if event.agent not in agents_running:
                agents_running.add(event.agent)
            if not include_completions and isinstance(
                event, (StartCompletion, FinishCompletion)
            ):
                continue
            if isinstance(event, TurnEnd):
                agents_running.remove(event.agent)
                if len(agents_running) == 0:
                    # All agents are finished
                    if waiting_final_timestamp:
                        break
                    else:
                        waiting_final_timestamp = time.time()
            yield event

    def reset_session(self):
        """Clears the chat history from the agent"""
        self.asys.tell(
            self.agent._actor,
            ResetHistory(self.agent.name),
        )

    def continue_with(self, response: dict):
        self.asys.tell(
            self.agent._actor,
            ResumeWithInput(self.agent.name, response),
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
                if comp.metadata["model"] not in costs:
                    costs[comp.metadata["model"]] = Modelcost(
                        comp.metadata["model"], 0, 0, 0, 0, 0
                    )
                mc = costs[comp.metadata["model"]]
                mc.calls += 1
                mc.cost += comp.metadata["cost"] * 100
                mc.inputs += comp.metadata["input_tokens"]
                mc.outputs += comp.metadata["output_tokens"]
                if "elapsed_time" in comp.metadata:
                    mc.time += comp.metadata["elapsed_time"].total_seconds()
            for mc in costs.values():
                yield (
                    f"[{mc.model}: {mc.calls} calls, tokens: {mc.inputs} -> {mc.outputs}, {mc.cost:.2f} cents, time: {mc.time:.2f}s]"
                )

        saved_completions = []
        fancy = False

        while fancy:
            try:
                # Get input directly from sys.stdin
                line = console.input("> ")

                if line == "quit" or line == "":
                    break

                output = ""
                with console.status("[bold blue]thinking...", spinner="dots") as status:
                    with Live(
                        Markdown(output),
                        refresh_per_second=1,
                        auto_refresh=not self.debug,
                    ) as live:
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
                traceback.print_exc()
                print(f"Error: {e}")

        while not fancy:
            try:
                # Get input directly from sys.stdin
                line = console.input("> ")

                if line == "quit" or line == "":
                    break

                self.start(line)

                for event in self.next(include_completions=True):
                    if event is None:
                        break
                    elif isinstance(event, WaitForInput):
                        replies = {}
                        for key, value in event.request_keys.items():
                            replies[key] = input(f"\n{value}\n:> ")
                        self.continue_with(replies)
                    elif isinstance(event, FinishCompletion):
                        saved_completions.append(event)
                    else:
                        if self._should_print(event):
                            print(str(event), end="")
                print()
                for row in print_stats_report(saved_completions):
                    console.out(row)
                readline.write_history_file(hist)
            except EOFError:
                print("\nExiting REPL.")
                break
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt. Type 'exit()' to quit.")
            except Exception as e:
                traceback.print_exc()
                print(f"Error: {e}")
