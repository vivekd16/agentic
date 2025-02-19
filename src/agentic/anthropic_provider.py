from .model_provider import ModelProvider, ModelConfig
from typing import Dict, Any
import litellm
import os

class AnthropicProvider(ModelProvider):
    """Provider for Anthropic models (Claude)"""
    
    def can_handle_model(self, model: str) -> bool:
        return model.startswith("anthropic/") or "claude" in model.lower()
        
    def prepare_completion_params(self, config: ModelConfig) -> Dict[str, Any]:
        """Transform generic config into Anthropic specific parameters"""
        params = config.__dict__.copy()
        
        # Remove anthropic/ prefix if present
        params["model"] = params["model"].replace("anthropic/", "")
        
        # Ensure API key is set
        if "ANTHROPIC_API_KEY" not in os.environ:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable must be set")
            
        return params
        
    def configure_litellm(self) -> None:
        """Configure litellm for Anthropic"""
        # Anthropic is supported by default in litellm
        pass
