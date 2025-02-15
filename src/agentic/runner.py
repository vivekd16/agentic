import asyncio
import time
import os
import readline
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Type
import importlib.util
import inspect
import sys
from .fix_console import ConsoleWithInputBackspaceFixed
from fastapi import FastAPI, Request
from ray import serve
from threading import Thread
from rich.live import Live
from rich.markdown import Markdown
import uvicorn
# Global console for Rich
console = ConsoleWithInputBackspaceFixed()


from .actor_agents import RayFacadeAgent, _AGENT_REGISTRY
from agentic.events import (
    DebugLevel,
    Event,
    FinishCompletion,
    Prompt,
    PromptStarted,
    ResumeWithInput,
    StartCompletion,
    ToolCall,
    ToolResult,
    TurnEnd,
    WaitForInput,
    ToolError,
)


@dataclass
class Modelcost:
    model: str
    inputs: int
    calls: int
    outputs: int
    cost: float
    time: float


def print_italic(*args):
    print(*args)


@dataclass
class Aggregator:
    total_cost: float = 0.0
    context_size: int = 0


class RayAgentRunner:
    def __init__(self, agent: RayFacadeAgent, debug: str | bool = False) -> None:
        self.facade = agent
        if debug:
            self.debug = DebugLevel(debug)
        else:
            self.debug = DebugLevel(os.environ.get("AGENTIC_DEBUG") or "")
        self.app = FastAPI()
        self.app.get("/next_turn")(self.web_request)

    def web_request(self, prompt: str):
        return self.turn(prompt)
    
    def run_web_server(self):
        config = uvicorn.Config(self.app, host="0.0.0.0", port=8000, log_level="info")
        self.server = uvicorn.Server(config)
        self.server.run()

    def start_server_thread(self):
        self.server_thread = Thread(target=self.run_web_server)
        self.server_thread.start()
        return self.server_thread
    
    def stop_server(self):
        if self.server_thread:
            # Signal the server to exit
            self.server.should_exit = True
            # Wait for the thread to complete
            self.server_thread.join()
            self.server_thread = None

    def turn(self, request: str) -> str:
        """Runs the agent and waits for the turn to finish, then returns the results
        of all output events as a single string."""
        results = []
        for event in self.facade.next_turn(request, debug=self.debug):
            if self._should_print(event):
                results.append(str(event))

        return "".join(results)

    def __lshift__(self, prompt: str):
        print(self.turn(prompt))

    def _should_print(self, event: Event) -> bool:
        if self.debug.debug_all():
            return True
        if event.is_output and event.depth == 0:
            return True
        elif isinstance(event, ToolError):
            return self.debug != ""
        elif isinstance(event, (ToolCall, ToolResult)):
            return self.debug.debug_tools()
        elif isinstance(event, PromptStarted):
            return self.debug.debug_llm() or self.debug.debug_agents()
        elif isinstance(event, TurnEnd):
            return self.debug.debug_agents()
        elif isinstance(event, (StartCompletion, FinishCompletion)):
            return self.debug.debug_llm()
        else:
            return False

    def set_debug_level(self, level: str):
        self.debug = DebugLevel(level)
        self.facade.set_debug_level(self.debug)

    def repl_loop(self):
        #self.web_server = self.start_server_thread()
        hist = os.path.expanduser("~/.agentic_history")
        if os.path.exists(hist):
            readline.read_history_file(hist)

        print(self.facade.welcome)
        print("press <enter> to quit")

        fancy = False
        aggregator = Aggregator()

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

        continue_result = {}
        saved_completions = []

        while not fancy:
            try:
                # Get input directly from sys.stdin
                if not continue_result:
                    saved_completions = []
                    line = console.input(f"[{self.facade.name}]> ")
                    if line == "quit" or line == "":
                        break

                if line.startswith("."):
                    self.run_dot_commands(line)
                    readline.write_history_file(hist)
                    time.sleep(0.3)  # in case log messages are gonna come
                    continue

                for event in self.facade.next_turn(
                    line, continue_result, debug=self.debug
                ):
                    continue_result = {}
                    if event is None:
                        break
                    elif isinstance(event, WaitForInput):
                        replies = {}
                        for key, value in event.request_keys.items():
                            replies[key] = input(f"\n{value}\n:> ")
                        continue_result = replies
                    elif isinstance(event, FinishCompletion):
                        saved_completions.append(event)
                    if self._should_print(event):
                        print(str(event), end="")
                print()
                time.sleep(0.3)
                if not continue_result:
                    for row in self.print_stats_report(saved_completions, aggregator):
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

        self.stop_server()    

    def print_stats_report(
        self, completions: list[FinishCompletion], aggregator: Aggregator
    ):
        costs = dict[str, Modelcost]()
        for comp in completions:
            if comp.metadata["model"] not in costs:
                costs[comp.metadata["model"]] = Modelcost(
                    comp.metadata["model"], 0, 0, 0, 0, 0
                )
            mc = costs[comp.metadata["model"]]
            mc.calls += 1
            mc.cost += comp.metadata["cost"] * 100
            aggregator.total_cost += comp.metadata["cost"] * 100
            mc.inputs += comp.metadata["input_tokens"]
            mc.outputs += comp.metadata["output_tokens"]
            aggregator.context_size += (
                comp.metadata["input_tokens"] + comp.metadata["output_tokens"]
            )
            if "elapsed_time" in comp.metadata:
                try:
                    mc.time += comp.metadata["elapsed_time"].total_seconds()
                except:
                    pass
        values_list = list(costs.values())
        for mc in values_list:
            if mc == values_list[-1]:
                yield (
                    f"[{mc.model}: {mc.calls} calls, tokens: {mc.inputs} -> {mc.outputs}, {mc.cost:.2f} cents, time: {mc.time:.2f}s tc: {aggregator.total_cost:.2f} c, ctx: {aggregator.context_size:,}]"
                )
            else:
                yield (
                    f"[{mc.model}: {mc.calls} calls, tokens: {mc.inputs} -> {mc.outputs}, {mc.cost:.2f} cents, time: {mc.time:.2f}s]"
                )

    def run_dot_commands(self, line: str):
        global CURRENT_DEBUG_LEVEL

        if line.startswith(".history"):
            print(self.facade.get_history())
        elif line.startswith(".run"):
            agent_name = line.split()[1].lower()
            for agent in _AGENT_REGISTRY:
                if agent_name in agent.name.lower():
                    self.facade = agent
                    print(f"Switched to {agent_name}")
                    print(f"  {self.facade.welcome}")
                    break
        elif line == ".agent":
            print(self.facade.name)
            print_italic(self.facade.instructions)
            print("tools:")
            for tool in self.facade.list_tools():
                print(f"  {tool}")

        elif line == ".tools":
            print(self.facade.name)
            print("tools:")
            for tool in self.facade.list_tools():
                print(f"  {tool}")

        elif line == ".functions":
            print(self.facade.name)
            print("functions:")
            for func in self.facade.list_functions():
                print(f"  {func}")

        elif line == ".reset":
            self.facade.reset_history()
            print("Session cleared")

        elif line.startswith(".debug"):
            if len(line.split()) > 1:
                debug_level = line.split()[1]
            else:
                print(f"Debug level set to: {self.debug}")
                return
            if debug_level == "off":
                debug_level = ""
            self.set_debug_level(debug_level)
            print(f"Debug level set to: {self.debug}")

        elif line.startswith(".help"):
            print(
                """
            .agent - Dump the state of the active agent
            .load <filename> - Load an agent from a file
            .run <agent name> - switch the active agent
            .debug [<level>] - enable debug. Defaults to 'tools', or one of 'llm', 'tools', 'all', 'off'
            .settings - show the current config settings
            .help - Show this help
            .quit - Quit the REPL
            """
            )
            print("Debug level: ", self.debug)
            if len(_AGENT_REGISTRY) > 1:
                print("Loaded:")
                for agent in _AGENT_REGISTRY:
                    print(f"  {agent.name}")
            print("Current:")
            print(f"  {self.facade.name}")
        else:
            print("Unknown command: ", line)


def find_agent_objects(module_members: Dict[str, Any], agent_class: Type) -> List:
    agent_instances = []

    for name, obj in module_members.items():
        # Check for classes that inherit from Agent
        if isinstance(obj, agent_class):
            agent_instances.append(obj)

    return agent_instances


def load_agent(filename: str) -> Dict[str, Any]:
    try:
        # Create a spec for the module
        spec = importlib.util.spec_from_file_location("dynamic_module", filename)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load file: {filename}")

        # Create the module
        module = importlib.util.module_from_spec(spec)
        sys.modules["dynamic_module"] = module

        # Execute the module
        spec.loader.exec_module(module)

        # Find all classes defined in the module
        return dict(inspect.getmembers(module))

    except Exception as e:
        raise RuntimeError(f"Error loading file {filename}: {str(e)}")
