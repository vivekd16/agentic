import os
import readline
from dataclasses import dataclass
from agentic.fix_console import ConsoleWithInputBackspaceFixed
from rich.live import Live
from rich.markdown import Markdown
from typing import List, Tuple, Dict, Any, Type
import importlib.util
import inspect
import sys
from types import ModuleType
from typing import Dict, Type


import traceback
from agentic import AgentRunner, Agent
from agentic.events import FinishCompletion, WaitForInput

console = ConsoleWithInputBackspaceFixed()

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


ACTIVE_AGENTS: List[AgentRunner] = []
CURRENT_RUNNER: AgentRunner  | None = None
CURRENT_DEBUG_LEVEL = None

def find_agent_objects(module_members: Dict[str, Any], agent_class: Type) -> List[Agent]:
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

def run_dot_commands(line: str):
    global CURRENT_RUNNER, CURRENT_DEBUG_LEVEL

    if line.startswith(".load"):
        agent_file = line.split()[1]
        if not os.path.exists(agent_file):
            print(f"File {agent_file} does not exist")
            return
        agent = find_agent_objects(load_agent(agent_file), Agent)[0]
        if agent:
            runner = AgentRunner(agent)
            ACTIVE_AGENTS.append(runner)
            CURRENT_RUNNER = runner
            print(runner.agent.welcome)
    elif line.startswith(".run"):
        agent_name = line.split()[1].lower()
        for agent in ACTIVE_AGENTS:
            if agent_name in agent.agent.name.lower():
                CURRENT_RUNNER = agent
                print(f"Switched to {agent_name}")
                print(f"  {CURRENT_RUNNER.agent.welcome}")
                break
    elif line.startswith(".debug"):
        if len(line.split()) > 1:
            debug_level = line.split()[1]
        else:
            debug_level = 'all'
        CURRENT_DEBUG_LEVEL = debug_level
        print(f"Debug level set to {debug_level}")

    elif line.startswith(".help"):
        print("""
        .load <filename> - Load an agent from a file
        .run <agent name> - switch the active agent
        .debug [<level>] - enable debug. Default or one of 'llm', 'tools', 'all'
        .settings - show the current config settings
        .help - Show this help
        .quit - Quit the REPL
        """)
        if len(ACTIVE_AGENTS) > 1:
            print("Loaded:")
            for agent in ACTIVE_AGENTS:
                print(f"  {agent.agent.name}")
        print("Current:")
        if CURRENT_RUNNER:
            print(f"  {CURRENT_RUNNER.agent.name}")
        else:
            print("  None")
    else:
        print("Unknown command: ", line)


def repl_loop():
    hist = os.path.expanduser("~/.agentic_history")
    if os.path.exists(hist):
        readline.read_history_file(hist)
            
    fancy = False

    print("Use .help for help")
    while not fancy:
        try:
            # Get input directly from sys.stdin
            if CURRENT_RUNNER is None:
                line = console.input("> ")
            else:
                line = console.input(f"{CURRENT_RUNNER.agent.name} > ")

            readline.write_history_file(hist)
            if line == ".quit" or line == "":
                break

            if line.startswith("."):
                run_dot_commands(line)
                continue

            if CURRENT_RUNNER is None:
                print("Please use .load to load an agent first")
                continue

            CURRENT_RUNNER.debug = CURRENT_DEBUG_LEVEL
            CURRENT_RUNNER.start(line)
            saved_completions = []

            for event in CURRENT_RUNNER.next(include_completions=True):
                if event is None:
                    break
                elif isinstance(event, WaitForInput):
                    replies = {}
                    for key, value in event.request_keys.items():
                        replies[key] = input(f"\n{value}\n:> ")
                    CURRENT_RUNNER.continue_with(replies)
                elif isinstance(event, FinishCompletion):
                    saved_completions.append(event)
                else:
                    if CURRENT_RUNNER._should_print(event):
                        print(str(event), end="")
            print()
            for row in print_stats_report(saved_completions):
                console.out(row)
        except EOFError:
            print("\nExiting REPL.")
            break
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt. Type 'exit()' to quit.")
        except Exception as e:
            traceback.print_exc()
            print(f"Error: {e}")

def main():
    repl_loop()
    
if __name__ == "__main__":
    main()
