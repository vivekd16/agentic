import asyncio
from typing import Callable, Any

from tools import LinkedinDataTool
from tools import GoogleNewsTool

from agentic import MakeAgent, add_child, repl_loop

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

from agentic import create_actor_system

if __name__ == "__main__":
    create_actor_system()

    orchestrator = MakeAgent(
        name="Person Researcher",
    #     instructions="""
    # You do research on people. Given a name and a company:
    # 1. Search for matching profiles on linkedin.
    # 2. If you find a single strong match, then prepare a background report on that person.
    # 3. If you find multiple matches, then print the matches and NEED INPUT and stop. If the response
    # identifies a profile then go back to step 2.
    # If you are missing info, then seek clarification from the user.
    # """,
        functions=[search_profiles],
    )
    add_child(
        orchestrator, 
        name="Person Report Writer",
        instructions="""
You will receive the URL to a linkedin profile. Retreive the profile and
write a background report on the person, focusing on their career progression
and current role.
""",
        functions=[get_profile],
    )


    producer = MakeAgent(
        name="Producer",
        instructions="You are a news producer. Call the reporter with the indicated topic.",
        model="gpt-4o-mini",
    )
    add_child(
        producer, 
        name="News Reporter",
        instructions=f"""
    Call Google News to get headlines on the indicated news topic.
    """,
        functions=[query_news],
    )

    root_reporter = MakeAgent(
        name="News Reporter",
        instructions="""
    Call Google News to get headlines on the indicated news topic.
    """,
        functions=[query_news],
    )

    repl_loop(producer, "Producer")
