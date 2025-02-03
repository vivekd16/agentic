from typing import Callable, Any

from agentic.tools import WeatherTool

from agentic import Agent, demo_loop

def weather_tool():
    return "The weather is nice today."

agent = Agent(
    name="Basic Agent",
    welcome="I am a simple agent here to help. I have a single weather function.",
    instructions="You are a helpful assistant.",
    model="gpt-4o-mini",
    functions=[WeatherTool()],
)

if __name__ == "__main__":
    demo_loop(agent)

