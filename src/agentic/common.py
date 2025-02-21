from .runner import RayAgentRunner
from .events import SetState, AddChild, PauseForInputResult, WaitForInput
from .actor_agents import (
    ActorBaseAgent,
    RayFacadeAgent,
    handoff,
)
from .swarm.types import RunContext
from .workflow import Pipeline
from jinja2 import Template

# Common aliases
Agent = RayFacadeAgent
AgentRunner = RayAgentRunner

def make_prompt(template: str, run_context: RunContext, **kwargs) -> str:
    context = run_context._context.copy() | kwargs
    return Template(template).render(context)
