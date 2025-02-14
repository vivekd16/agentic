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

The list of tools on an agent should be modifiable at any time:

    agent.add_tool(tool)
    agent.remove_tool(tool)

However, tools probably shouldn't modify the running agent directly. Safer that
they publish events like `EnableTool` which can be handled properly by the
framework (there might be security controls or what not).

