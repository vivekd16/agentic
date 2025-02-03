import asyncio
from typing import Callable, Any

from agentic.tools import LinkedinDataTool
from agentic.tools import GoogleNewsTool

from agentic import Agent, repl_loop, PauseToolResult, demo_loop

def invoke_async(async_func: Callable, *args, **kwargs) -> Any:
    return asyncio.run(async_func(*args, **kwargs))

linkedin = LinkedinDataTool()
def search_profiles(name: str, company: str = ""):
    """ Searches for linkedin profiles. """
    return invoke_async(linkedin.linkedin_people_search, name=name, company=company)

def get_profile(url: str):
    return invoke_async(linkedin.get_linkedin_profile_info, url)

gnt = GoogleNewsTool()

def query_news(topic: str):
    return gnt.query_news(topic)

def get_human_input():
    return PauseToolResult()

producer = Agent(
    name="Producer",
    welcome="I am the news producer. Tell me the topic, and I'll get the news from my reporter.",
    instructions="You are a news producer. Call the reporter with the indicated topic.",
    model="gpt-4o-mini",
    functions=[search_profiles],
)
producer.add_child(
    name="News Reporter",
    instructions=f"""
Call Google News to get headlines on the indicated news topic.
""",
    functions=[query_news],
)

if __name__ == "__main__":
    demo_loop(producer)
