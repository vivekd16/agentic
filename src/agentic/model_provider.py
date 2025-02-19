from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class ModelConfig:
    """Configuration for a model call"""
    model: str
    messages: list
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    tools: Optional[list] = None
    tool_choice: Optional[str] = None
    stream: bool = False
    stream_options: Dict[str, Any] = None
    parallel_tool_calls: bool = True  # Added field with default True

class ModelProvider(ABC):
    """Base class for model providers"""
    
    @abstractmethod
    def can_handle_model(self, model: str) -> bool:
        """Return True if this provider can handle the given model identifier"""
        pass
        
    @abstractmethod
    def prepare_completion_params(self, config: ModelConfig) -> Dict[str, Any]:
        """
        Transform the generic model config into provider-specific parameters.
        Returns dict of parameters to pass to litellm.completion
        """
        pass
        
    @abstractmethod
    def configure_litellm(self) -> None:
        """Configure litellm for this provider. Called during provider registration."""
        pass

class ModelRegistry:
    """Registry of model providers"""
    
    def __init__(self):
        self.providers: list[ModelProvider] = []
        
    def register_provider(self, provider: ModelProvider):
        """Add a new model provider"""
        provider.configure_litellm()
        self.providers.append(provider)
        
    def get_completion_params(self, config: ModelConfig) -> Dict[str, Any]:
        """Get the completion parameters for a given model configuration"""
        print(f"\nRegistry looking for provider to handle model: {config.model}")
        print(f"Number of registered providers: {len(self.providers)}")
        
        for provider in self.providers:
            print(f"Checking provider: {provider.__class__.__name__}")
            if provider.can_handle_model(config.model):
                print(f"Found matching provider: {provider.__class__.__name__}")
                return provider.prepare_completion_params(config)
                
        print("No provider found that can handle this model!")
        # Return original config as dict if no provider handles it
        return config.__dict__

# Global registry instance
model_registry = ModelRegistry()
