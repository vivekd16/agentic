from typing import Any
from agentic.tools.weather_tool import WeatherTool

from agentic.common import Agent, AgentRunner


def weather_tool():
    return "The weather is nice today."


agent = Agent(
    name="Basic Agent",
    welcome="I am a simple agent here to help answer your weather questions.",
    instructions="You are a helpful assistant.",
    model="openai/gpt-4o-mini",
    tools=[WeatherTool()],
)

if __name__ == "__main__":
    AgentRunner(agent).repl_loop()
