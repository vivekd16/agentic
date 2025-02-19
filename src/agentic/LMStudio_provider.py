import requests
from typing import Dict, Any, Optional
import pprint

from .model_provider import ModelProvider, ModelConfig

class LMStudioProvider(ModelProvider):
    """Provider for LM Studio models"""
    
    def __init__(self, host: str = "localhost", port: int = 1234):
        self.base_url = f"http://{host}:{port}/v1"
        print(f"Initializing LMStudio provider with base_url: {self.base_url}")
        
    def can_handle_model(self, model: str) -> bool:
        can_handle = model.startswith("lmstudio/")
        print(f"LMStudio provider checking if can handle {model}: {can_handle}")
        return can_handle
        
    def prepare_completion_params(self, config: ModelConfig) -> Dict[str, Any]:
        """Transform generic config into LM Studio specific parameters"""
        print("\nPreparing params for LMStudio completion...")
        print(f"Input config: {config}")
        
        params = config.__dict__.copy()
        
        # Get the actual model name without the lmstudio/ prefix
        actual_model = params["model"].replace("lmstudio/", "")
        
        # Set up parameters for litellm to use OpenAI provider with our local endpoint
        params.update({
            "model": actual_model,
            "api_base": self.base_url,
            "api_key": "not-needed",
            "custom_llm_provider": "openai"  # Tell litellm to use OpenAI's API format
        })
        
        print("Final params being sent to litellm:")
        pprint.pprint(params)
        return params
        
    def configure_litellm(self) -> None:
        """Nothing to configure as we're using the OpenAI provider"""
        pass

    def ensure_available(self, model_id: str) -> Optional[str]:
        """Verify LM Studio server is running and model is available."""
        try:
            response = requests.get(f"{self.base_url}/models")
            if response.status_code == 200:
                models = response.json()
                print(f"Available LMStudio models: {[m['id'] for m in models['data']]}")
            else:
                print(f"LMStudio server returned status code: {response.status_code}")
            return None
        except Exception as e:
            return f"Error checking LM Studio: {str(e)}"
