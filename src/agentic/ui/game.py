from openai import OpenAI
import streamlit as st

from agentic import AgentRunner
from agentic.events import ToolCall
from examples import all


col1, col2 = st.columns(2)

# Add headers for each chat window
with col1:
    st.header("Chat Window 1")
with col2:
    st.header("Chat Window 2")

selected_agent1 = None
selected_agent2 = None

with col1.container():
    if "messages1" not in st.session_state:
        st.session_state.messages1 = []

    if "agent1" not in st.session_state:
        st.session_state.agent1 = selected_agent1

    selected_agent1 = st.selectbox(
        "",
        all,
        format_func=lambda x: x.name,
        on_change=lambda: st.session_state.clear(),
        key="sel1",
    )

    if selected_agent1:  # Check if an agent is selected
        st.session_state.agent1 = selected_agent1
        agent = selected_agent1
        st.title(agent.name)
        with st.chat_message("assistant"):
            st.markdown(agent.welcome)

        for message in st.session_state.messages1:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("What is up?", key="col1chat"):
            st.session_state.messages1.append({"role": "user", "content": prompt})
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

                st.session_state.messages1.append(
                    {"role": "assistant", "content": response}
                )


with col2.container():
    if "messages2" not in st.session_state:
        st.session_state.messages2 = []

    if "agent2" not in st.session_state:
        st.session_state.agent2 = selected_agent2

    selected_agent2 = st.selectbox(
        "",
        all,
        format_func=lambda x: x.name,
        on_change=lambda: st.session_state.clear(),
        key="sel2",
    )
    if selected_agent2:  # Check if an agent is selected
        st.session_state.agent2 = selected_agent2
        agent = selected_agent2
        st.title(agent.name)
        with st.chat_message("assistant"):
            st.markdown(agent.welcome)

        for message in st.session_state.messages2:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("What is up?", key="col2chat"):
            st.session_state.messages2.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("thinking..."):
                if "runner" not in st.session_state or st.session_state.runner is None:
                    st.session_state.runner2 = AgentRunner(agent2)

                st.session_state.runner2.start(prompt)

                def get_output():
                    for event in st.session_state.runner2.next():
                        if event is None:
                            break
                        yield str(event)

                with st.chat_message("assistant"):
                    response = st.write_stream(get_output())

                st.session_state.messages2.append(
                    {"role": "assistant", "content": response}
                )
