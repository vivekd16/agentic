# Standard library imports
import asyncio
import json
import os
from collections import defaultdict
from typing import List, Callable, Union

# Package/library imports
from litellm import completion
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
        context_variables: RunContext,
        model_override: str,
        stream: bool,
        debug: bool,
    ) -> ChatCompletionMessage:
        instructions = (
            agent.instructions(context_variables)
            if callable(agent.instructions)
            else agent.instructions
        )
        messages = [{"role": "system", "content": instructions}] + history

        tools = [function_to_json(f) for f in agent.functions]
        # hide context_variables from model
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
        return completion(**create_params)

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
        context_variables: dict,
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
            run_context = RunContext(context_variables, agent.name)
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

    # def run_and_stream(
    #     self,
    #     agent: SwarmAgent,
    #     messages: List,
    #     context_variables: dict = {},
    #     model_override: str = None,
    #     debug: bool = False,
    #     max_turns: int = float("inf"),
    #     execute_tools: bool = True,
    # ):
    #     active_agent = agent
    #     context_variables = copy.deepcopy(context_variables)
    #     history = copy.deepcopy(messages)
    #     init_len = len(messages)

    #     while len(history) - init_len < max_turns:

    #         message = {
    #             "content": "",
    #             "sender": agent.name,
    #             "role": "assistant",
    #             "function_call": None,
    #             "tool_calls": defaultdict(
    #                 lambda: {
    #                     "function": {"arguments": "", "name": ""},
    #                     "id": "",
    #                     "type": "",
    #                 }
    #             ),
    #         }

    #         # get completion with current history, agent
    #         completion = self.get_chat_completion(
    #             agent=active_agent,
    #             history=history,
    #             context_variables=context_variables,
    #             model_override=model_override,
    #             stream=True,
    #             debug=debug,
    #         )

    #         yield {"delim": "start"}
    #         for chunk in completion:
    #             # LiteLLM's streaming format is compatible with OpenAI's
    #             delta = json.loads(chunk.choices[0].delta.json())
    #             if delta["role"] == "assistant":
    #                 delta["sender"] = active_agent.name
    #             yield delta
    #             delta.pop("role", None)
    #             delta.pop("sender", None)
    #             merge_chunk(message, delta)
    #         yield {"delim": "end"}

    #         message["tool_calls"] = list(
    #             message.get("tool_calls", {}).values())
    #         if not message["tool_calls"]:
    #             message["tool_calls"] = None
    #         debug_print(self.llm_debug, "Received completion:", message)
    #         history.append(message)

    #         if not message["tool_calls"] or not execute_tools:
    #             debug_print(debug, "Ending turn.")
    #             break

    #         # convert tool_calls to objects
    #         tool_calls = []
    #         for tool_call in message["tool_calls"]:
    #             function = Function(
    #                 arguments=tool_call["function"]["arguments"],
    #                 name=tool_call["function"]["name"],
    #             )
    #             tool_call_object = ChatCompletionMessageToolCall(
    #                 id=tool_call["id"], function=function, type=tool_call["type"]
    #             )
    #             tool_calls.append(tool_call_object)

    #         # handle function calls, updating context_variables, and switching agents
    #         partial_response = self.handle_tool_calls(
    #             tool_calls, active_agent.functions, context_variables, debug
    #         )
    #         history.extend(partial_response.messages)
    #         context_variables.update(partial_response.context_variables)
    #         if partial_response.agent:
    #             active_agent = partial_response.agent

    #     yield {
    #         "response": Response(
    #             messages=history[init_len:],
    #             agent=active_agent,
    #             context_variables=context_variables,
    #         )
    #     }

    # def run(
    #     self,
    #     agent: SwarmAgent,
    #     messages: List,
    #     context_variables: dict = {},
    #     model_override: str = None,
    #     stream: bool = False,
    #     debug: bool = False,
    #     max_turns: int = float("inf"),
    #     execute_tools: bool = True,
    # ) -> Response:
    #     if stream:
    #         return self.run_and_stream(
    #             agent=agent,
    #             messages=messages,
    #             context_variables=context_variables,
    #             model_override=model_override,
    #             debug=debug,
    #             max_turns=max_turns,
    #             execute_tools=execute_tools,
    #         )
    #     active_agent = agent
    #     context_variables = copy.deepcopy(context_variables)
    #     history = copy.deepcopy(messages)
    #     init_len = len(messages)

    #     while len(history) - init_len < max_turns and active_agent:

    #         # get completion with current history, agent
    #         completion = self.get_chat_completion(
    #             agent=active_agent,
    #             history=history,
    #             context_variables=context_variables,
    #             model_override=model_override,
    #             stream=stream,
    #             debug=debug,
    #         )
    #         message = completion.choices[0].message
    #         debug_print(debug, "Received completion:", message)
    #         message.sender = active_agent.name
    #         history.append(
    #             json.loads(message.model_dump_json())
    #         )  # to avoid OpenAI types (?)

    #         if not message.tool_calls or not execute_tools:
    #             debug_print(debug, "Ending turn.")
    #             break

    #         # handle function calls, updating context_variables, and switching agents
    #         partial_response = self.handle_tool_calls(
    #             message.tool_calls, active_agent.functions, context_variables, debug
    #         )
    #         history.extend(partial_response.messages)
    #         context_variables.update(partial_response.context_variables)
    #         if partial_response.agent:
    #             active_agent = partial_response.agent

    #     return Response(
    #         messages=history[init_len:],
    #         agent=active_agent,
    #         context_variables=context_variables,
    #     )
