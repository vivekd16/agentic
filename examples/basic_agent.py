from typing import Callable, Any

from agentic.tools import WeatherTool

from agentic import Agent, demo_loop

def weather_tool():
    return "The weather is nice today."

agent = Agent(
    name="Basic Agent",
    welcome="I am a simple agent here to help. I have a single weather function.",
    instructions="You are a helpful assistant.",
    model="openai/gpt-4o", #anthropic/claude-3-5-haiku-20241022", #claude-3-5-sonnet-20240620",
    functions=[WeatherTool()],
)

if __name__ == "__main__":
    demo_loop(agent)

