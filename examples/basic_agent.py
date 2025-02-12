from typing import Callable, Any
from agentic.tools.weather_tool import WeatherTool

from agentic import Agent, AgentRunner


def weather_tool():
    return "The weather is nice today."


agent = Agent(
    name="Basic Agent",
    welcome="I am a simple agent here to help. I have a single weather function.",
    instructions="You are a helpful assistant.",
    model="openai/gpt-4o-mini",  # anthropic/claude-3-5-haiku-20241022", #claude-3-5-sonnet-20240620",
    tools=[WeatherTool()],
)

if __name__ == "__main__":
    AgentRunner(agent).repl_loop()
