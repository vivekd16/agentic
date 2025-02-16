from agentic.tools.weather_tool import WeatherTool
from agentic.tools.google_news import GoogleNewsTool
from agentic.tools.database_tool import DatabaseTool
from agentic.tools.automatic_tools import AutomaticTools
from agentic.tools.linkedin_tool import LinkedinDataTool
from agentic.tools.tavily_search_tool import TavilySearchTool
from agentic.tools.image_generator import OpenAIImageGenerator
from agentic.tools.imap_tool import IMAPTool
from agentic.tools.browser_use import BrowserUseTool

from agentic.common import Agent, AgentRunner
from agentic.tools.registry import tool_registry
from datetime import datetime

agent = Agent(
    name="Dynamic Agent",
    welcome="I have a list of tools which I can enable and use on-demand. Query the list of tools to start.",
    instructions="You are a helpful assistant. You can list tools or enable a tool for different purposes.",
    model="openai/gpt-4o-mini",
    tools=[
        AutomaticTools(
            tool_classes=[
                GoogleNewsTool, 
                WeatherTool, 
                DatabaseTool, 
                LinkedinDataTool, 
                OpenAIImageGenerator,
                TavilySearchTool,
                IMAPTool,
            ],
        ),
        BrowserUseTool(),
        # tool_registry.load_tool(
        #     "langchain_community.tools.DuckDuckGoSearchRun",
        #     requires=["duckduckgo-search", "langchain-community"]
        # ),
        # tool_registry.load_tool(
        #     "langchain_community.tools.shell.tool.ShellTool",
        #     requires=["langchain-community", "langchain-experimental"]
        # ),
    ],
)

if __name__ == "__main__":
    AgentRunner(agent).repl_loop()
