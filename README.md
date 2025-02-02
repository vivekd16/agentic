# Agentic

A new, easy to use AI Agents framework.

## Basic example

```python
import Agent, LinkedinTool, HumanInterruptTool, PromptEvent

researcher = Agent(
    name="Person Researcher",
    system_prompt="""
You do research on people. Given a name and a company:
1. Search for matching profiles on linkedin.
2. If you find a single strong match, then prepare a background report on that person.
3. If you find multiple matches, then ask stop and ask the user for clarification. Then go back to step 1.
If you are missing info, then seek clarification from the user.
""",
    tools=[LinkedinTool(), HumanInterruptTool()],
    model="openai://gpt-4o-mini",
)

researcher.add_child(
    Agent(
        name = "Person Report Writer",
        system_prompt="""
    You will receive the URL to a linkedin profile. Retrive the profile and
    write a background report on the person, focusing on their career progression
    and current role.
        """,
        tools=[LinkedinTool(['get_profile'])],
        operations="prepare_person_report(linkedin_url)",
        model="anthropic://claude-sonnet-3.5",
    )
)

runner = AgentRunner(researcher, memory=True)

print("People researcher is ready! Tell me who you want to research.")
print("Use 'quit' to stop.")
while True:
    query = input("> ").strip()
    if query == 'quit':
        break
    event = runner.next(PromptEvent(query))
    while event.is_finish_event:
        if event.request_human:
            print(event)
            response = input(":> ")
            event.set_response(response)
        else:
            print(event)
        event = runner.next(event)
```

**Breaking down our example**

First we define our top-level agent, the "Person Researcher", give it a goal
and a task list, an LLM model, and some tools:

- A linkedin tool for search for linkedin profiles
- A "Human interrupt" tool which the agent can call to ask for human help

Now, we define a "sub agent" for this agent to use as another tool. This
is the "Person Report Writer" agent, with its own instruction and a 
different LLM model. We connect this agent to the top level via:

    operations="prepare_person_report(linkedin_url)",

This essentially creates a tool function in the parent with the given name
and params. We could omit this parameter and we would get a general function
like:
    
    call_person_report_writer(input)

taken from the agent name.

**Running our agent**

To run our agent, we construct an `AgentRunner`. This object manages
a single multi-turn single session interacting with our agent.

Suppose our user input is:

    Sam Altman

We call `start` to start our agent, and it returns an initial event.
Now we enter a loop until we receive a `finish` event from the agent.

- The initial user prompt is passed to our Researcher agent. It considers
its system instruction and the user input. Based on this it generates 
a tool call to `LinkedinTool.search_profiles`. 
- The `search_profiles` function is called, and the result is return
to the agent, which "observes" this result and generates the next
event (the "observation" event.)
- The agent "loops" and determines that multiple profiles were returned,
so it creates a tool call to `human_interrupt` passing that function
the list of profiles.
- The runner returns the human interrupt event setting `event.request_human`
to be the agent request. We print that event, collect input from the user,
and then set their input as the `response` on the event. This will automatically
get appened to the agent context on the next loop.
- On `runner.next` the agent considers its next action. Assuming that the user
specific a particular profile to research, it generates
a tool call to `prepare_person_report` to create the report. If the user had
responded "I don't know", then the agent could decide it can't go any further
and just return the `finish` event.
- The `prepare_person_report` function now activates our "Person Report Writer"
agent, with the profile URL as input, but a new LLM context.

So our full chat looks like:

```
People researcher is ready! Tell me who you want to research.
Use 'quit' to stop.
> Sam Altman
[...event: processing input: Sam Altman]
[...event: tool call: search_profiles]
Ok, I found these 5 matching profiles...
[...event: tool observation]
[...event: tool call: human_interrupt]
I have found multiple profiles for Sam Altman: ..... which one should I research?
:> use the first one
[...event observation] 
Ok, let me prepare the research report.
[...event tool call: prepare_person_report]
[...sub event: processing input: https://linkedin.com/r/samaltman]
[...sub event: <output>...]
[...event: observation]     (back in Person Researcher)
Here is the professional background for Sam Altman...
....
And now humanity is doomed.
[...event: finish]
> quit
```

### Things to note

The list of tools on an agent should be modifiable at any time:

    agent.add_tool(tool)
    agent.remove_tool(tool)

However, tools probably shouldn't modify the running agent directly. Safer that
they publish events like `EnableTool` which can be handled properly by the
framework (there might be security controls or what not).

**RunContext**

PydanticAI uses this object, and I have the same (same name!) in Supercog. Real tools
will often want to retrieve bits of context like the current agent name, or running
user, etc... An example of where we use this in SC is an "email_user" function which looks
up the current user email in the RunContext.

**Run state**

Langgraph has a `state` notion, a dict that is passed between nodes. I have a feeling
that this is poor encapsulation and probably leads to poor code. Letta has "memory blocks"
which can be shared between agents, and this feels like probably a better design choice where
you very explicitly decide to share state rather than just using tool inputs and outputs.

A good example of this is if agent B needs to return a large chunk of info to agent A
(like the contents of a file), then it could put the file to a memory block and 
return a reference to that block in its call response to agent A. 




