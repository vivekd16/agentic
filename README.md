# Agentic

Agentic makes it easy to create AI agents - autonomous software programs that understand natural language
and can use tools to do work on your behalf.

Agentic is in the tradition of _opinionated frameworks_. We've tried to encode lots of sensisible
defaults and best practices into the design, testing and deployment of agents. 

Some key features:

- Approachable and simple to use, but flexible enough to support the most complex agents
- Supports teams of cooperating agents
- Supports Human-in-the-loop
- Easy definition and use of tools
- Built in library of production-tested tools

Visits the docs: https://supercog-ai.github.io/agentic/



## Install

`pip install agents-kit`

We recommend installing into a virtual env.

After you install, setup a folder to hold your agents, then run:

`agentic init .`

The CLI will setup the current directory to contain your agents.

The install will copy examples and a basic file structure into the directory `myagents`. You can name
or rename this folder however you like.

## Intro Tutorial

Visit [the docs](https://supercog-ai.github.io/agentic/) for a tutorial on getting started
with the framework.

## Dependencies

Agentic builds on `Litellm` to enable consistent support for many different LLM models.

Under the covers, Agentic uses [Ray](https://github.com/ray-project/ray) to host and
run your agents. Ray implements an _actor model_ which implements a much better 
architecture for running complex agents than a typical web framework.

## Why does this exist?

Yup, there's a lot of agent frameworks. But many of these are "gen 1" frameworks - designed
before anyone had really built agents and tried to put them into production. Agentic is informed
by our learnings at Supercog from building and running hundreds of agents over the past year.

Some reasons why Agentic is different:

- We have a thin abstraction over the LLM. The "agent loop" code is a 
[couple hundred lines](./src/agentic/actor_agents.py) 
calling directly into the LLM API (the OpenAI _completion_ API via _Litellm_).
- Logging is **built-in** and usable out of the box. Trace agent runs, tool calls, and LLM completions
with ability to control the right level of detail.
- Very simple and well designed abstractions with just a few nouns: Agent, Tool, Run, Pipeline. You can easily
build complex agent teams and flows, but don't have to assemble the _computational graph_ by hand.
- Agents are asynchronous and generate typed events, not just text. Consuming an event stream
allows lots of rich interactions and different media types.
- Event streams can have _multiple channels_, so your agent can "run in the background" and
still notify you of what is happening.
- Human-in-the-loop is built into the framework, not hacked in. An agent can wait indefinitely,
or get notification from any channel like an email or webhook.
- Context length, token usage, and timing usage data is emitted in a standard form.
- Tools are designed to support configuration and authentication, not just run on a sea of random env vars.
- Use tools from almost any framework, including MCP and Composio.


