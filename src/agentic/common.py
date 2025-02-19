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

print("\n=== Initializing Agentic Model Providers ===")

# Import and register model providers
from .model_provider     import model_registry
from .openai_provider    import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .LMStudio_provider  import LMStudioProvider

print("Creating providers...")
openai_provider = OpenAIProvider()
anthropic_provider = AnthropicProvider()
lmstudio_provider = LMStudioProvider()

print("Registering providers with registry...")
# Register providers in priority order
# OpenAI first as it handles default case
model_registry.register_provider(openai_provider)
model_registry.register_provider(anthropic_provider)
model_registry.register_provider(lmstudio_provider)

print("Provider registration complete!")
print(f"Number of registered providers: {len(model_registry.providers)}")
for provider in model_registry.providers:
    print(f"- {provider.__class__.__name__}")

# Common aliases
Agent = RayFacadeAgent
AgentRunner = RayAgentRunner

def make_prompt(template: str, run_context: RunContext, **kwargs) -> str:
    context = run_context._context.copy() | kwargs
    return Template(template).render(context)
