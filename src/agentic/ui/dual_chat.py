import streamlit as st


def init_session_state():
    if "messages_left" not in st.session_state:
        st.session_state.messages_left = []
    if "messages_right" not in st.session_state:
        st.session_state.messages_right = []


def display_chat(messages, col, chat_id):
    # Display chat messages
    for message in messages:
        with col.container():
            col.write(f"**{message['role']}**: {message['content']}")

    # Input for new messages
    user_input = col.text_input("Enter your message:", key=f"input_{chat_id}")

    if col.button("Send", key=f"send_{chat_id}"):
        if user_input:
            # Add user message
            messages.append({"role": "user", "content": user_input})
            # Simulate response (you can replace this with actual chat logic)
            messages.append(
                {"role": "assistant", "content": f"Response to: {user_input}"}
            )
            # Clear input
            st.session_state[f"input_{chat_id}"] = ""


def main():
    st.title("Dual Chat Windows")

    # Initialize session state
    init_session_state()

    # Create two columns for side-by-side chat windows
    col1, col2 = st.columns(2)

    # Add headers for each chat window
    with col1:
        st.header("Chat Window 1")
    with col2:
        st.header("Chat Window 2")

    # Display both chat windows
    display_chat(st.session_state.messages_left, col1, "left")
    display_chat(st.session_state.messages_right, col2, "right")

    # Add a clear button for both chats
    if st.button("Clear Both Chats"):
        st.session_state.messages_left = []
        st.session_state.messages_right = []
        st.experimental_rerun()


if __name__ == "__main__":
    main()
