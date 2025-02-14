from agentic.common import Agent, AgentRunner
from agentic.tools.text_to_speech_tool import TextToSpeechTool
from agentic.tools.auth_rest_api_tool import AuthorizedRESTAPITool
from agentic.tools.google_news import GoogleNewsTool
from agentic.models import CLAUDE, GPT_4O_MINI, GPT_4O

#model = "groq/llama-3.3-70b-versatile"
model = GPT_4O

reporter_agents = []
for topic in [
    "AI News",
    "Sports",
    "Finance"
]:
    prompt_key = topic.replace(" ", "_").upper() + "_REPORTER"
    reporter = Agent(
        name=f"{topic} Reporter",
        instructions="{{" + prompt_key + "}}",
        model=CLAUDE,
        tools=[GoogleNewsTool()],
        max_tokens=8192,
    )
    reporter_agents.append(reporter)

producer = Agent(
    name="Podcast Producer",
    welcome="I am a podcast producer. I can produce a daily news podcast.",
    instructions="{{FULL_PRODUCER}}",
    model=model,
    max_tokens=16 * 1000,
    tools=[TextToSpeechTool()] + reporter_agents,
)

uploader = Agent(
    name="TransistorFM",
    welcome="I can work with podcast episodes via the Transistor.fm API.",
    instructions="{{TRANSISTOR_FM}}",
    tools=[AuthorizedRESTAPITool("header", "TRANSISTOR_API_KEY", "x-api-key")],
    memories=["Default show ID is 60214"],
    model=model,
)

producer.add_tool(uploader)

if __name__ == "__main__":
    AgentRunner(producer).repl_loop()
