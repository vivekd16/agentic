from agentic import Agent, AgentRunner
from agentic.tools.text_to_speech_tool import TextToSpeechTool
from agentic.tools.auth_rest_api_tool import AuthorizedRESTAPITool
from agentic.tools.google_news import GoogleNewsTool
from agentic.models import CLAUDE, GPT_4O_MINI

#model = "groq/llama-3.3-70b-versatile"
model = GPT_4O_MINI

producer = Agent(
    name="Podcast Producer",
    welcome="I am a podcast producer. I can produce a daily news podcast.",
    instructions="{{PRODUCER}}",
    model=model,
    tools=[TextToSpeechTool()],
)
reporter = Agent(
    name="AI News Reporter",
    instructions="{{REPORTER}}",
    model=CLAUDE,
    tools=[GoogleNewsTool()]
)

producer.add_tool(reporter)

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
