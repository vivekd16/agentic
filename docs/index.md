# Agentic

Agentic makes it easy to create AI agents - autonomous software programs that understand natural language
and can use tools to do work on your behalf.

Agentic is in the tradition of _opinionated frameworks_. We've tried to encode lots of sensisible
defaults and best practices into the design, testing and deployment of agents. 

Some key features:

- Approachable and simple to use
- Supports teams of cooperating agents
- Supports Human-in-the-loop
- Easy definition and use of lots of tools

But there is much more.


## Install

    pip install agent-kit

Note the package name: **agent-kit**.

Now setup an area to build and manage your agents:

    mkdir myagents
    cd myagents
    agentic init .

This will install some examples and a basic file structure into the directory `myagents`. You can name
or rename this folder however you like.

## Try it!
The easiest way to start is by configuring your OpenAI API key and running some example agents.
Visits the [models](./Models.md) documentation for information on using other models.

Set your OpenAI key:

    agentic set-secret OPENAI_API_KEY <your OpenAI API key>

(You can also just use OPENAI_API_KEY env var if you have it set.)

and now:

```python

% python examples/basic_agent.py
I am a simple agent here to help. I have a single weather function.
[Basic Agent]> what is the weather in San Francisco?
The current weather in San Francisco is as follows:

- **Temperature:** 48.2°F
- **Feels Like:** 46.3°F
- **Wind Speed:** 9.8 km/h
...
```

```python
% python examples/database_agent.py
Hi! I can help you run SQL queries on any standard database.
[Database Agent]> show me the tables in the db
INFO: Connecting to database: sqlite:///examples/chinook.db
The tables in the database are as follows:

1. albums
2. artists
3. customers
6. invoices
...
> how many invoices do we have?
There are a total of 412 invoices in the database.
> what is the total amount?
The total amount of all invoices is $2,328.60.
```

## What is an "AI Agent"?

An Agent is a semi-autonmous program powered by an LLM plus 
a set of "tools" which it uses to complete tasks or answer questions on your behalf.

### Types of agents

Some common types of agents include:

- Conversational agents
- Workflow automations
- Deep reasoning agents

## Building Agents

Agentic agents by default use the LLM **ReAct** pattern. This means:

- The LLM controls the execution flow of your agent
- You specify the tasks and flow of your agent via the LLM system prompt
- The agents gets one or more **tools** that it can use to accomplish its task
- The agent runs in this loop until it decides that it can't go further:
    - plan next step
    - generate text completion or tool call
        (platform executes tool call)
    - observe tool call results

Here is the "Hello World" example of ReAct agents:

```
def weather_tool():
    """ Returns the weather report """
    return "The weather is nice today."

agent = Agent(
    name="Basic Agent",
    welcome="I am a simple agent here to help. I have a single weather function.",
    instructions="You are a helpful assistant.",
    model="openai/gpt-4o-mini",
    functions=[weather_tool],
)

AgentRunner(agent).repl_loop()
```
This will start a command prompt where you can interact with your agent. Each time you
send a request the agent will run and process your request in a single **turn** and
print the result:

```python
$ python examples/basic_agent.py
I am a simple agent here to help. I have a single weather function.
[Basic Agent]> hi there
Hello! How can I assist you today?
> what is the weather in SF?
...
[openai/gpt-4o-mini: 3 calls, tokens: 168 -> 143, 0.02 cents, time: 15.92s]
```
We can see at the end that our converstation made 3 calls to the OpenAI API, those
calls took 15.92secs, and cost us 0.02 cents (2 hundredths of a penny).

## Components of an agent

An agent is _defined_ by its behavior - what is does as perceived from the outside. But
inside each agent has these properties:

- name
- instructions
- list of tools
- list of children agents
- chosen LLM model
- a 'welcome' message explaining the purpose of the agent

Notice that agents can call both `tools`, which are regular code functions, or
other agents, in the same way. 

Calling "sub agents" allows us to organize a set of multiple agents to solve
a single problem. The simplest example looks like this:

```python
from agentic.tools import GoogleNewsTool

producer = Agent(
    name="Producer",
    welcome="I am the news producer. Tell me the topic, and I'll get the news from my reporter.",
    instructions="You are a news producer. Call the reporter with the indicated topic.",
    model="gpt-4o-mini",
    tools=[
        Agent(
            name="News Reporter",
            instructions=f"""
        Call Google News to get headlines on the indicated news topic.
        """,
            tools=[GoogleNewsTool()],
        )
    ],
)
```
### Calling agents in sequence

Treating agents as a `subroutine` is useful, but sometimes we want `pipeline` semantics
where we want to invoke the next agent by "handing off" execution to that agent and
not waiting for it to return. We can use a `Pipeline` construct to support this
pattern:


```python
from agentic import Pipeline

pipeline = Pipeline(
    Agent(
        name="Producer",
        welcome="This is the pipeline demo.",
        instructions="Print the message 'I am A'",
    ),
    Agent(
        name="Agent B",
        instructions="Print the message 'and I am B'",
    )
)
AgentRunner(pipeline).run()
```

```
$ python examples/handoff_demo.py
This is the handoff demo.
> run
I am A
and I am B
> 
```

## The _Actor Model_

Since the introduction of "function calling" by OpenAI, most frameworks have built around
the idea of agent "tools" as functions. The function calling model works very well with
web framework technologies which are designed around the synchronous request-response
model of the HTTP protocol.

The problem is that function calling generally assumes synchronous semantics and strictly 
typed parameters and return values. Both of these make poor assumptions when dealing with
AI agents. Since agents can easily be long-running, it is much better assume an event-driven
model (sending messages, and waiting for events) than a synchronous one. Strict typing
is useful in compiled code, but LLMs are really best with text and language, not strict
compiler types.

Agentic uses the [Actor Model](https://en.wikipedia.org/wiki/Actor_model) which is a software
architecture that long pre-dates (from 1973!) the rise of GenAI. The model was created as
an architecture for building concurrent systems.

As you start building more complex agents, you want them to run longer, be decomposable
into multiple units, and have flexible behavior like stopping for human input. The actor
model on which Agentic is built make these more complex use cases easy.

## Tools as Agents

Agentic assumes an event driven model for agents. We send events to agents when we want
them to do something, and the agent publishes events back to us with the results. Because
event driven is so key, _tool calling_ is also event driven. Although the framework
hides most of the details, every tool (function) call happens asynchronously. One of
the implications of this design is that tools can "interrupt" the agent, and wait for
human input. When your agent is waiting for input it is effectively paused, consuming
no resources. This means that complex patterns like "send an email for clarification,
and wait for the reply" are easy and low-cost to build.

## Complete example

```python
from agentic import Agent, AgentRunner
from agentic.tools import LinkedinTool, HumanInterruptTool

researcher = Agent(
    name="Person Researcher",
    instructions="""
You do research on people. Given a name and a company:
1. Search for matching profiles on linkedin.
2. If you find multiple matches, then ask stop and ask the user for clarification. 
3. Once you have a single match, then prepare a background report on that person.
""",
    model="openai://gpt-4o-mini",
    tools=[
        LinkedinTool(), 
        HumanInterruptTool(),
        Agent(
            name = "Person Report Writer",
            instructions="""...""",
            tools=[LinkedinTool()],
            model="anthropic://claude-sonnet-3.5",
        )
    ]
)

runner = AgentRunner(agent)
runner.repl_loop()
```

**Breaking down our example**

First we define our top-level agent, the "Person Researcher", give it a goal
and a task list, an LLM model, and some tools:

- A linkedin tool for searching for linkedin profiles
- A "Human interrupt" tool which the agent can call to ask for human help

Now, we define a "sub agent" for this agent to use as another tool. This
is the "Person Report Writer" agent, with its own instruction and a 
different LLM model. We include this agent in the list of tools for the Researcher.

**Running our agent**

To run our agent, we construct an `AgentRunner`. This object manages
a single multi-turn session interacting with our agent.

Here is the complete (condensed) run output:

```markdown
(agentic) scottp@MacBook-Air agentic % python examples/people_researcher.py 
I am the People Researcher. Tell me who you want to know about.
> marc benioff
--> search_profiles({"name":"marc benioff"})
--> get_human_input({"request_message":"I found multiple profiles for Marc..."})
I found multiple LinkedIn profiles for Marc Benioff. Here are the details:

1. **Marc Benioff**  
   - **Headline:** Chair & CEO at Salesforce  
   ...

2. **Marc Benioff**  
   - **Headline:** Bachelor's degree at Brunel University London  
   ...
...
Please let me know which profile you would like to know more about. 
> 1
call_person_report_writer({"message":"Please prepare a background report on Marc Benioff..."})
--> get_profile({"url":"https://www.linkedin.com/in/marcbenioff"})
### Background Report on Marc Benioff
**Current Role:**
Marc Benioff is the Chair and CEO of Salesforce, a leading cloud-based software company headquartered in San Francisco, California. Under his leadership, Salesforce has become a pioneer in customer relationship management (CRM) software and has significantly influenced the tech industry with its innovative solutions and commitment to social responsibility.

**Career Progression:**
- **Early Career:** Marc Benioff began his career at Oracle Corporation, where he worked for 13 years. During his time at Oracle, he held various positions, gaining valuable experience in software development and sales.
...
```

Our agent starts by calling the `search_profiles` function on the
`LinkedInTool`. When it finds multiple results it calls the `HumanInterruptTool`
to request input.

Once the user answers the interrupt, then the agent resumes operating. It
calls our "Person Report Writer" agent which retrieves the full LinkedIn
profile and creates the person report.


## Tools

Tools can be functions, instance methods, or other agents. See [Tools](Tools.md) for the
overview of how to use tools with your agents.

## Guide to building agents

Visit [Building Agents](./Building_Agents.md) for details on building your own agents.

### Examples

Look in the [examples](./examples/) folder.

## Try the web UI (using streamlit)

    agentic ui




