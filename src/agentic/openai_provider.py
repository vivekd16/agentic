from .model_provider import ModelProvider, ModelConfig
from typing import Dict, Any
import litellm
import os

class OpenAIProvider(ModelProvider):
    """Provider for OpenAI models, including GPT-4O"""
    
    def can_handle_model(self, model: str) -> bool:
        # Handle:
        # 1. Explicit openai/ prefix
        # 2. gpt- prefix 
        # 3. No prefix but gpt in name
        # 4. Default model when none specified
        return (
            model.startswith("openai/") or 
            model.startswith("gpt-") or
            "gpt" in model.lower() or
            model == ""  # Handle empty/None case
        )
        
    def prepare_completion_params(self, config: ModelConfig) -> Dict[str, Any]:
        """Transform generic config into OpenAI specific parameters"""
        params = config.__dict__.copy()
        
        # Handle default model case
        if not params["model"] or params["model"] == "":
            params["model"] = "gpt-4o-mini"
            
        # Remove openai/ prefix if present
        params["model"] = params["model"].replace("openai/", "")
        
        # Ensure API key is set
        if "OPENAI_API_KEY" not in os.environ:
            raise RuntimeError("OPENAI_API_KEY environment variable must be set")
            
        return params
        
    def configure_litellm(self) -> None:
        """Configure litellm for OpenAI"""
        # OpenAI is supported by default in litellm
        pass
