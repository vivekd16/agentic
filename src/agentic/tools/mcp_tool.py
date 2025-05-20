from typing import Any, Optional, Dict, List, Callable
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from litellm import experimental_mcp_client
from agentic.tools.base import BaseAgenticTool
from agentic.tools.utils.registry import tool_registry, Dependency
from agentic.events import ChatOutput, Event

@tool_registry.register(
    name="MCPTool",
    description="Universal wrapper for MCP tools that can work with any MCP server.",
    dependencies=[
        Dependency(
            name="mcp",
            version="1.5.0",
            type="pip",
        ),
    ],
    config_requirements=[]
)


class MCPTool(BaseAgenticTool):
    """Universal wrapper for MCP tools that can work with any MCP server."""
    
    def __init__(self, 
                 command: str,
                 args: list[str],
                 tool_name: Optional[str] = None,
                 env: Optional[Dict[str, str]] = None):
        """
        Initialize an MCP tool wrapper.
        
        Args:
            command: The command to run the MCP server (e.g. "python3", "npx")
            args: Arguments for the command (e.g. ["./mcp_server.py"])
            tool_name: Optional specific tool name to use from the MCP server
            env: Optional environment variables to pass to the MCP server
        """
        super().__init__()
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env or {}
        )
        self.tool_name = tool_name
        self.name = f"MCP-{tool_name}" if tool_name else "MCPTool"  # Add name attribute
        self._session = None
        self._tools = None
        self._stdio = None
        self._tool_schema_map = {}  # Store tool schemas for reference
        self._event_handlers = []  # Store event handlers
        
        # Initialize in a new event loop
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._init_session())
    
    def register_event_handler(self, handler):
        """Register an event handler function to receive events from this tool."""
        self._event_handlers.append(handler)
        
    def _emit_event(self, event: Event):
        """Emit an event to all registered handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Error in event handler: {e}")

    async def _init_session(self):
        """Initialize the MCP session if not already initialized."""
        if self._session is None:
            self._stdio = stdio_client(self.server_params)
            read, write = await self._stdio.__aenter__()
            self._session = ClientSession(read, write)
            await self._session.__aenter__()
            await self._session.initialize()
            
            # Load available tools
            self._tools = await experimental_mcp_client.load_mcp_tools(
                session=self._session,
                format="openai"
            )
            
            # Store tool schemas for reference
            for tool in self._tools:
                self._tool_schema_map[tool["function"]["name"]] = tool["function"].get("parameters", {})
                
            # Update name if we have only one tool
            if len(self._tools) == 1 and not self.tool_name:
                first_tool = self._tools[0]["function"]["name"]
                self.name = f"MCP-{first_tool}"

    def get_tools(self) -> List[Callable]:
        """Get the available MCP tools in OpenAI format."""
        if self._tools is None:
            raise RuntimeError("MCP session not initialized")
            
        # Convert MCP tools to callable functions
        tool_functions = []
        
        for tool in self._tools:
            if self.tool_name and tool["function"]["name"] != self.tool_name:
                continue
                
            # Get the tool's parameter schema
            tool_schema = tool["function"].get("parameters", {})
            required_params = tool_schema.get("required", [])
            properties = tool_schema.get("properties", {})
            
            # Create a dynamic wrapper with the correct signature based on the tool schema
            # This helps the agent understand the required parameters
            params = []
            for param_name in properties:
                if param_name in required_params:
                    params.append(f"{param_name}")
                else:
                    params.append(f"{param_name}=None")
            
            # Create function with proper signature
            func_name = tool["function"]["name"]
            func_def = f"def {func_name}({', '.join(params)}):\n    kwargs = locals().copy()\n    return self._call_mcp_tool('{func_name}', kwargs)"
            
            local_vars = {"self": self}
            exec(func_def, {"self": self}, local_vars)
            
            # Get the created function
            tool_wrapper = local_vars[func_name]
            
            # Format parameter documentation
            param_docs = []
            for param_name, param_info in properties.items():
                required = "required" if param_name in required_params else "optional"
                desc = param_info.get("description", "No description")
                param_type = param_info.get("type", "any")
                enum_values = param_info.get("enum", [])
                
                param_doc = f"  {param_name} ({param_type}, {required}): {desc}"
                if enum_values:
                    param_doc += f"\n    Allowed values: {', '.join(map(str, enum_values))}"
                param_docs.append(param_doc)

            # Set function metadata for OpenAI format
            tool_wrapper.__name__ = func_name
            tool_wrapper.__doc__ = (
                f"{tool['function'].get('description', '')}\n\n"
                f"Parameters:\n"
                f"{chr(10).join(param_docs)}\n"
            )
            
            tool_functions.append(tool_wrapper)
        
        return tool_functions
    
    def _convert_parameter_types(self, function_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Convert parameter types based on the schema."""
        schema = self._tool_schema_map.get(function_name, {})
        properties = schema.get("properties", {})
        
        for param_name, value in list(kwargs.items()):
            if param_name in properties:
                param_type = properties[param_name].get("type")
                
                # Skip None values
                if value is None:
                    continue
                
                # Convert to appropriate type based on schema
                if param_type == "integer" or param_type == "number":
                    try:
                        if isinstance(value, str):
                            if param_type == "integer":
                                kwargs[param_name] = int(value)
                            else:
                                kwargs[param_name] = float(value)
                    except (ValueError, TypeError):
                        print(f"Warning: Could not convert {param_name}={value} to {param_type}")
                
                # Handle boolean conversion
                elif param_type == "boolean" and isinstance(value, str):
                    if value.lower() in ("true", "yes", "1"):
                        kwargs[param_name] = True
                    elif value.lower() in ("false", "no", "0"):
                        kwargs[param_name] = False
        
        return kwargs
    
    def _call_mcp_tool(self, function_name: str, kwargs: Dict[str, Any]) -> Any:
        """Internal method to call an MCP tool with the appropriate arguments."""
        # Remove 'self' from kwargs if present
        if "self" in kwargs:
            del kwargs["self"]
        
        # Filter out None values for optional parameters
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        # Check required parameters against tool schema
        required_params = self._tool_schema_map.get(function_name, {}).get("required", [])
        for param in required_params:
            if param not in kwargs:
                return f"Error: Missing required parameter '{param}'"
        
        # Convert parameter types according to schema
        kwargs = self._convert_parameter_types(function_name, kwargs)
        
        # Create OpenAI tool format
        openai_tool = {
            "id": "tool_call_id",  # ID doesn't matter for MCP
            "type": "function",
            "function": {
                "name": function_name,
                "arguments": json.dumps(kwargs)
            }
        }
        
        result = self._loop.run_until_complete(
            self.call_tool(openai_tool)
        )
        
        # Generate a chat output event with the result
        # This ensures the UI can display the result properly
        if hasattr(result, 'content') and len(result.content) > 0:
            # Extract text from MCP Content object if available
            if hasattr(result.content[0], 'text'):
                text_content = result.content[0].text
                # Check if the result contains an error
                try:
                    result_json = json.loads(text_content)
                    if result_json.get("error"):
                        error_msg = f"Error from {function_name}: {result_json['error']}"
                        event = ChatOutput(self.name, {"content": error_msg, "role": "assistant"})
                    else:
                        event = ChatOutput(self.name, {"content": str(text_content), "role": "assistant"})
                except:
                    event = ChatOutput(self.name, {"content": str(text_content), "role": "assistant"})
                self._emit_event(event)
            else:
                # Fall back to string representation
                event = ChatOutput(self.name, {"content": str(result), "role": "assistant"})
                self._emit_event(event)
        else:
            # Handle other result formats
            event = ChatOutput(self.name, {"content": str(result), "role": "assistant"})
            self._emit_event(event)
        
        return result

    async def call_tool(self, openai_tool: dict) -> Any:
        """Call an MCP tool with given arguments."""
        if self._session is None:
            await self._init_session()
            
        result = await experimental_mcp_client.call_openai_tool(
            session=self._session,
            openai_tool=openai_tool
        )
        return result

    async def cleanup(self):
        """Cleanup MCP session."""
        if self._session:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._stdio:
            await self._stdio.__aexit__(None, None, None)
            self._stdio = None

    def __del__(self):
        """Ensure cleanup on deletion."""
        if self._session or self._stdio:
            try:
                self._loop.run_until_complete(self.cleanup())
            except:
                pass  # Ignore cleanup errors during deletion
            finally:
                self._loop.close() 