from agentic import Agent, AgentRunner, WaitForInput
from agentic.tools import GoogleNewsTool

gnt = GoogleNewsTool()

def query_news(topic: str):
    return gnt.query_news(topic)

def get_human_input(request_message: str):
    return WaitForInput(request_message)

newsAgent = Agent(
    name="News Gatherer",
    instructions="""
You do news research. If you dont know the topic, then
stop for human input on the topic. Then query the news for that topic. 
""",
    tools=[query_news, get_human_input],
)

if __name__ == "__main__":
    AgentRunner(newsAgent).repl_loop()
