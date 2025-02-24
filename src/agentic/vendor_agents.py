from abc import ABC, abstractmethod
from typing import Any, Dict, AsyncGenerator, List
import ray
from .events import Event, Result, Prompt, PromptStarted, TurnEnd, ChatOutput
from .actor_agents import ActorBaseAgent, RunContext
from .swarm.types import Response

@ray.remote
class VendorAgentBase(ActorBaseAgent, ABC):
    """Base class for vendor-specific agent implementations."""
    
    def __init__(self):
        super().__init__("VendorAgent")
        self._is_running = False
        self._config: Dict[str, Any] = {}

    @abstractmethod
    async def configure_agent(self, config: Dict[str, Any]) -> None:
        """Configure the agent with vendor-specific settings.
        
        Args:
            config: Dictionary containing vendor-specific configuration
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """Initialize and start the agent."""
        self._is_running = True

    @abstractmethod 
    async def stop(self) -> None:
        """Stop the agent."""
        self._is_running = False

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> AsyncGenerator[Event, None]:
        """Run the agent with the given input data.
        
        Args:
            input_data: Dictionary containing input data for the agent
            
        Yields:
            Event: Agent protocol events
        """
        pass

@ray.remote 
class LangGraphAgent(VendorAgentBase):
    """LangGraph implementation of the vendor agent protocol."""

    def __init__(self):
        super().__init__()
        self.graph = None

    async def configure_agent(self, config: Dict[str, Any]) -> None:
        """Configure the LangGraph agent.
        
        Args:
            config: Dictionary containing LangGraph configuration including the graph instance
        """
        if 'graph' not in config:
            raise ValueError("LangGraph configuration must include 'graph' instance")
        self.graph = config['graph']

    async def start(self) -> None:
        """Initialize and start the LangGraph agent."""
        await super().start()
        if not self.graph:
            raise RuntimeError("LangGraph agent not configured - call configure_agent first")

    async def stop(self) -> None:
        """Stop the LangGraph agent."""
        await super().stop()
        self.graph = None

    async def run(self, input_data: Dict[str, Any]) -> AsyncGenerator[Event, None]:
        """Run the LangGraph agent with the given input.
        
        This method translates LangGraph events into our Agent Protocol events.
        
        Args:
            input_data: Dictionary containing the input messages
            
        Yields:
            Event: Translated agent protocol events
        """
        if not self._is_running:
            raise RuntimeError("LangGraph agent not started")

        # Start the turn
        yield PromptStarted(self.name, input_data["messages"][-1]["content"], self.depth)

        # Stream graph updates and translate events
        messages = []
        async for event in self.graph.astream(input_data):
            for value in event.values():
                content = value["messages"][-1].content
                messages.append({"role": "assistant", "content": content})
                yield ChatOutput(self.name, {"content": content}, self.depth)

        # End the turn
        yield TurnEnd(
            self.name,
            messages,
            RunContext(agent_name=self.name, agent=self, debug_level=self.debug),
            self.depth
        )

    def handlePromptOrResume(self, prompt: Prompt) -> AsyncGenerator[Event, None]:
        """Handle a new prompt by running it through the LangGraph.
        
        Args:
            prompt: The prompt event containing the input message
            
        Yields:
            Event: Agent protocol events
        """
        return self.run({"messages": [{"role": "user", "content": prompt.payload}]})
