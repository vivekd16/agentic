import atexit
import asyncio
from thespian.actors import (
    Actor,
    ActorSystem,
    PoisonMessage,
    ActorAddress,
    ActorExitRequest,
)
from typing import Any, Optional, Generator
from dataclasses import dataclass
from functools import partial
from collections import defaultdict
from pathlib import Path
from functools import partial
import inspect
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
import os
import yaml
from jinja2 import Template
from rich.markdown import Markdown
from .fix_console import ConsoleWithInputBackspaceFixed
from rich.live import Live

import yaml
from typing import Callable, Any, List
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client
from pydantic import Field
from .swarm import Swarm
from .swarm.types import (
    AgentFunction,
    Response,
    SwarmAgent,
    Result,
    RunContext,
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
from agentic.tools.registry import tool_registry, Tool

import inspect
import asyncio
import os
import yaml
from typing import List, Any, Callable



# Global console for Rich
console = ConsoleWithInputBackspaceFixed()


def wrap_llm_function(fname, doc, func, *args):
    f = partial(func, *args)
    setattr(f, "__name__", fname)
    f.__doc__ = doc
    setattr(f, "__code__", func.__code__)
    # Keep the original arg list
    f.__annotations__ = func.__annotations__
    return f


@dataclass
class AgentPauseContext:
    orig_history_length: int
    tool_partial_response: Response
    sender: Optional[Actor] = None
    tool_function: Optional[Function] = None


class ActorBaseAgent(SwarmAgent, Actor):
    name: str = "Agent"
    model: str = "gpt-4o"
    instructions_str: str = "You are a helpful agent."
    functions: List[AgentFunction] = []
    tool_choice: str = None
    parallel_tool_calls: bool = True
    paused_context: Optional[AgentPauseContext] = None
    debug: bool = False
    depth: int = 0
    children: dict = {}
    history: list = []
    # Memories are static facts that are always injected into the context on every turn
    memories: list[str] = []
    _logger: Actor = None
    # The Actor who sent us our Prompt
    _prompter: Actor = None
    max_tokens: int = None
    run_context: RunContext = None

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

    def get_instructions(self, context: RunContext):
        prompt = self.instructions_str
        if self.memories:
            prompt += """
<memory blocks>
{% for memory in MEMORIES -%}
{{memory|trim}}
{%- endfor %}
</memory>
"""
        return Template(prompt).render(
            context.get_context() | {"MEMORIES": self.memories}
        )

    def _yield_completion_steps(self, run_context: RunContext):
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
        yield StartCompletion(self.name, self.depth)

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
            run_context=run_context,
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
            self.depth,
        )

    def relay_message(self, actor_message, sender):
        if self._prompter and sender != self._prompter:
            # Relay sub-agent messages to our prompter so they "bubble up"
            self.send(self._prompter, actor_message)

    def receiveMessage(self, actor_message, sender):
        self.relay_message(actor_message, sender)
        self._swarm.llm_debug = os.environ.get("AGENTIC_DEBUG") == "llm"
        # print(f"[RECEIVE: {self.myAddress}/{self.name}: {actor_message} from {sender}")

        def report_calling_tool(name: str, args: dict):
            self.send(sender, ToolCall(self.name, name, args))

        def report_tool_result(name: str, result):
            self.send(sender, ToolResult(self.name, name, result))

        match actor_message:
            case Prompt() | TurnEnd() | ResumeWithInput():
                if isinstance(actor_message, Prompt):
                    self.run_context = (
                        RunContext(agent_name=self.name)
                        if self.run_context is None
                        else self.run_context
                    )
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
                    self.run_context.update(context_variables)
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
                        self.run_context,
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
                    for event in self._yield_completion_steps(self.run_context):
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
                        self.run_context,
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
                if isinstance(actor_message, (Prompt, TurnEnd)):
                    self.send(
                        sender,
                        TurnEnd(
                            self.name,
                            self.history[init_len:],
                            context_variables,
                            self.depth,
                        ),
                    )
                self.paused_context = None

            case SetState():
                self.inject_secrets_into_env()
                state = actor_message.payload
                remap = {"instructions": "instructions_str", "logger": "_logger"}

                for key in [
                    "name",
                    "logger",
                    "instructions",
                    "model",
                    "max_tokens",
                    "memories",
                ]:
                    if key in state:
                        setattr(self, remap.get(key, key), state[key])

                # Update our functions
                if "functions" in state:
                    self.functions = []
                    for f in state.get("functions"):
                        if isinstance(f, AddChild):
                            f = self._build_child_func(f)
                        self.functions.append(f)

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
        llm_name = f"call_{name.lower().replace(' ', '_')}"
        doc = f"Send a message to sub-agent {name}"

        return wrap_llm_function(llm_name, doc, self.call_child, child, event.handoff)

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


running_agents: list = []


def create_actor_system() -> tuple[ActorSystem, ActorAddress]:
    global logger

    if True:  # os.environ.get("AGENTIC_SIMPLE_ACTORS"):
        asys = ActorSystem()
    else:
        asys = ActorSystem("multiprocTCPBase")
    if logger is None:
        logger = asys.createActor(Logger)
    return asys, logger


def register_agent(agent):
    running_agents.append(agent)


def shutdown_agents():
    for agent in running_agents:
        agent.shutdown()


atexit.register(shutdown_agents)


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
        template_path: str | Path = None,
        max_tokens: int = None,
        memories: list[str] = [],
    ):
        self.name = name
        self.welcome = welcome or f"Hello, I am {name}."
        self.model = model or "gpt-4o-mini"
        caller_frame = inspect.currentframe()
        if caller_frame:
            caller_file = inspect.getframeinfo(caller_frame.f_back).filename
            directory = os.path.dirname(caller_file)
            # Get just the filename without extension
            base = os.path.splitext(os.path.basename(caller_file))[0]

            # Create new path with .prompts.yaml extension
            template_path = os.path.join(directory, f"{base}.prompts.yaml")

        # Get the file where Agent() was called
        self.template_path = template_path
        self._tools = tools
        self.max_tokens = max_tokens
        self.memories = memories

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
        register_agent(self)

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
                    "memories": self.memories,
                },
            ),
        )

    def shutdown(self):
        asys, logger = create_actor_system()
        asys.tell(self._actor, ActorExitRequest())

    def add_tool(self, tool: Any):
        self._tools.append(tool)
        self._update_state({"functions": self._get_funcs(self._tools)})

    def _update_state(self, state: dict):
        asys, logger = create_actor_system()
        asys.ask(
            self._actor,
            SetState(self.name, state),
        )

    def _get_funcs(self, thefuncs: list):
        useable = []
        for func in thefuncs:
            if callable(func):
                tool_registry.ensure_dependencies(func)
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
            elif isinstance(func, Tool):
                # Wrap the Tool instance to be callable using its underlying function attribute.
                tool_registry.ensure_dependencies(func)
                wrapped_tool = wrap_llm_function(func.name, func.description, func.function)
                # Preserve the original Tool instance if needed
                wrapped_tool._original_tool = func
                useable.append(wrapped_tool)
            else:
                tool_registry.ensure_dependencies(func)
                useable.extend(func.get_tools())
        return useable

    @staticmethod
    def invoke_async(async_func: Callable, *args, **kwargs) -> Any:
        return asyncio.run(async_func(*args, **kwargs))

    def add_child(self, child_agent: "ActorAgent"):
        """
        Add a child agent to this agent.

        Args:
            child_agent: Another ActorAgent instance to add as a child
        """
        self.add_tool(child_agent)

    @property
    def prompt_variables(self) -> dict:
        """Dictionary of variables to make available to prompt templates."""
        paths_to_search = [self.template_path]

        for path in [Path(p) for p in paths_to_search]:
            if path.exists():
                with open(path, "r") as f:
                    prompts = yaml.safe_load(f)
                return prompts

        return {"name": "John Doe"}

    @property
    def safe_name(self) -> str:
        """Renders the ActorAgent's name, but filesystem safe."""
        return "".join(c if c.isalnum() else "_" for c in self.name).lower()

    async def connect_mcp(self, command: str, args: List[str] = None) -> "ActorAgent":
        """
        Connect to an MCP server and register its tools with this agent.

        Args:
            command (str): The command to run the MCP server (e.g. "python", "uv run")
            args (List[str]): Optional list of arguments for the command

        Returns:
            self: Returns the agent instance for method chaining
        """
        server_params = StdioServerParameters(command=command, args=args or [])

        # Connect to MCP server and load tools
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize connection
                await session.initialize()

                tools = await session.list_tools()

                # Wrap each MCP tool as an Agent tool and add it
                for mcp_tool in tools.tools:
                    self.add_tool(
                        Tool(
                            mcp_tool.name,
                            mcp_tool.description,
                            self._create_mcp_tool_runner(session, mcp_tool.name),
                            []
                        )
                    )

        return self

    def _create_mcp_tool_runner(
        self, session: "ClientSession", tool_name: str
    ) -> Callable:
        """Create an async runner function for an MCP tool."""

        async def run_tool(**kwargs) -> Any:
            return await session.call_tool(tool_name, arguments=kwargs)

        return run_tool

    def connect_mcp_sync(self, command: str, args: List[str] = None) -> "ActorAgent":
        """
        Synchronous wrapper for connect_mcp.

        Args:
            command (str): The command to run the MCP server.
            args (List[str]): Optional list of arguments for the command.

        Returns:
            self: Returns the agent instance for method chaining.
        """
        return self.invoke_async(self.connect_mcp, command, args)

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
        elif isinstance(event, (ToolCall, ToolResult)):
            return "tools" in flag
        elif isinstance(event, PromptStarted):
            return "llm" in flag or "agents" in flag
        elif isinstance(event, TurnEnd):
            return "agents" in flag
        elif isinstance(event, (StartCompletion, FinishCompletion)):
            return "llm" in flag
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
                        yield event
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
