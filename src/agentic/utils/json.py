from litellm.types.utils import Message, ChatCompletionMessageToolCall
from pydantic import BaseModel
from datetime import datetime

def make_json_serializable(obj):
    """Recursively convert dictionary values to JSON-serializable types."""
    if isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, Message):
        # Convert Message object to a dictionary manually
        result = {
            "role": obj.role,
            "content": make_json_serializable(obj.content),
            "function_call": make_json_serializable(obj.function_call),
        }

        tool_calls = []
        for tc in obj.tool_calls or []:
            if isinstance(tc, ChatCompletionMessageToolCall):
                tool_calls.append({
                    "function": {
                        "arguments": make_json_serializable(tc.function.arguments) if tc.function.arguments else None,
                        "name": tc.function.name if tc.function.name else None,
                    } if tc.function else None,
                    "id": tc.id,
                    "type": tc.type
                })
            elif isinstance(tc, dict):
                tool_calls.append(tc)

        result["tool_calls"] = tool_calls
        return result
    elif isinstance(obj, BaseModel):
        return obj.model_dump()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):  # For objects like RunContext
        return str(obj)
    return obj
