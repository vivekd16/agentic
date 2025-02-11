# Standard library imports
import asyncio
import json
import os
from collections import defaultdict
from typing import List, Callable, Union

# Package/library imports
import litellm
from litellm.utils import trim_messages

# Local imports
from .util import function_to_json, debug_print, merge_chunk
from .types import (
    SwarmAgent,
    AgentFunction,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
    Function,
    Response,
    Result,
    RunContext,
)

__CTX_VARS_NAME__ = "run_context"


class Swarm:
    def __init__(self, client=None):
        # LiteLLM doesn't require a client instance, but we'll keep the parameter
        # for backward compatibility
        self.llm_debug = os.environ.get("AGENTIC_DEBUG") == "llm"

    def get_chat_completion(
        self,
        agent: SwarmAgent,
        history: List,
        run_context: RunContext,
        model_override: str,
        stream: bool,
        debug: bool,
    ) -> ChatCompletionMessage:
        instructions = agent.get_instructions(run_context)
        messages = [{"role": "system", "content": instructions}] + history

        tools = [function_to_json(f) for f in agent.functions]
        # hide run_context from model
        for tool in tools:
            params = tool["function"]["parameters"]
            params["properties"].pop(__CTX_VARS_NAME__, None)
            if __CTX_VARS_NAME__ in params["required"]:
                params["required"].remove(__CTX_VARS_NAME__)

        # if agent.trim_context:
        #    messages = trim_messages(messages, model=model_override or agent.model)

        create_params = {
            "model": model_override or agent.model,
            "temperature": 0.0,
            "messages": messages,
            "tools": tools or None,
            "tool_choice": agent.tool_choice,
            "stream": stream,
            "stream_options": {"include_usage": True},
        }
        if agent.max_tokens:
            create_params["max_tokens"] = agent.max_tokens

        if tools:
            create_params["parallel_tool_calls"] = agent.parallel_tool_calls

        debug_print(self.llm_debug, "Getting chat completion for...:\n", create_params)
        # Use LiteLLM's completion instead of OpenAI's client
        print("Calling litellm completion with params: ", create_params)
        return litellm.completion(**create_params)

    def handle_function_result(self, result, debug) -> Result:
        match result:
            case Result() as result:
                return result

            case SwarmAgent() as agent:
                return Result(
                    value=json.dumps({"assistant": agent.name}),
                    agent=agent,
                )
            case _:
                try:
                    return Result(value=str(result))
                except Exception as e:
                    error_message = f"Failed to cast response to string: {result}. Make sure agent functions return a string or Result object. Error: {str(e)}"
                    debug_print(debug, error_message)
                    raise TypeError(error_message)

    def handle_tool_calls(
        self,
        agent: SwarmAgent,
        tool_calls: List[ChatCompletionMessageToolCall],
        functions: List[AgentFunction],
        run_context: RunContext,
        debug: bool,
        report_callback: Callable = None,
        report_tool_result: Callable = None,
    ) -> Response:
        function_map = {f.__name__: f for f in functions}
        partial_response = Response(messages=[], agent=None, context_variables={})

        for tool_call in tool_calls:
            name = tool_call.function.name
            # handle missing tool case, skip to next tool
            if name not in function_map:
                debug_print(debug, f"Tool {name} not found in function map.")
                partial_response.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "tool_name": name,
                        "content": f"Error: Tool {name} not found.",
                    }
                )
                continue
            args = json.loads(tool_call.function.arguments)
            debug_print(
                self.llm_debug, f"Processing tool call: {name} with arguments {args}"
            )

            func = function_map[name]
            # pass context_variables to agent functions
            if __CTX_VARS_NAME__ in func.__code__.co_varnames:
                args[__CTX_VARS_NAME__] = run_context

            if report_callback:
                report_callback(name, args)

            # Call the function!!
            # Wrap async functions in asyncio.run
            try:
                if asyncio.iscoroutinefunction(function_map[name]):
                    raw_result = asyncio.run(function_map[name](**args))
                else:
                    raw_result = function_map[name](**args)
            except Exception as e:
                raw_result = f"{name} - Error: {e}"
                run_context.error(raw_result)

            result: Result = self.handle_function_result(raw_result, debug)
            result.tool_function = Function(
                name=name,
                arguments=tool_call.function.arguments,
                _request_id=tool_call.id,
            )

            if report_tool_result:
                report_tool_result(name, result.value)

            tool_name_key = ""
            partial_response.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result.value,
                }
            )
            partial_response.last_tool_result = result
            partial_response.context_variables.update(result.context_variables)
            if result.agent:
                partial_response.agent = result.agent

        return partial_response

    def report_calling_tool(self, name: str, args: dict, sender):
        pass
