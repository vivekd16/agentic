from openai import OpenAI
import streamlit as st

from agentic import AgentRunner
from agentic.events import ToolCall
from examples import all

if "messages" not in st.session_state:
    st.session_state.messages = []

selected_agent = st.selectbox(
    "", all, format_func=lambda x: x.name, on_change=lambda: st.session_state.clear()
)

if "agent" not in st.session_state:
    st.session_state.agent = selected_agent


if "agent" in st.session_state:
    agent = st.session_state.agent
    st.title(agent.name)
    with st.chat_message("assistant"):
        st.markdown(agent.welcome)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("thinking..."):
            if "runner" not in st.session_state or st.session_state.runner is None:
                st.session_state.runner = AgentRunner(agent)

            st.session_state.runner.start(prompt)

            def get_output():
                for event in st.session_state.runner.next():
                    if event is None:
                        break
                    yield str(event)

            with st.chat_message("assistant"):
                response = st.write_stream(get_output())

            st.session_state.messages.append({"role": "assistant", "content": response})
