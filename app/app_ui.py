import asyncio
import streamlit as st
from client import MCPClient
import base64
import os
from faster_whisper import WhisperModel
import tempfile

# --- 1. Whisper Setup (CPU - Optimized for GTX 1650 users) ---
@st.cache_resource
def load_whisper():
    # 'int8' quantization makes this very fast even on old CPUs
    return WhisperModel("distil-small.en" "", device="cpu", compute_type="int8")


whisper_model = load_whisper()


def transcribe_audio(audio_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_file.getvalue())
        tmp_path = tmp.name

    segments, _ = whisper_model.transcribe(tmp_path, beam_size=5)
    text = " ".join([s.text for s in segments])

    os.remove(tmp_path)
    return text.strip()


# Create a global agent client
agent_client = MCPClient()
connected = False


async def async_interact(query):
    global connected
    if not connected:
        await agent_client.connect_to_server(r"./server/finance_server.py")
        connected = True
    # run the query and return result
    return await agent_client.ollama_process_query(query)


def interact(query):
    # wrap the async call in asyncio.run for synchronous use
    return asyncio.run(async_interact(query))

# Initialize and Display Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. The Multimodal Chat Input ---
# Native 2026 feature: accept_audio adds the mic icon inside the bar
user_input = st.chat_input("What is up?", accept_audio=True)

if user_input:
    prompt = ""

    # Priority 1: Use the audio if recorded
    if user_input.audio:
        with st.spinner("🦊 Foxy is listening..."):
            prompt = transcribe_audio(user_input.audio)
    # Priority 2: Use the text if typed
    elif user_input.text:
        prompt = user_input.text

    if prompt:
        # User side
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Assistant side
        with st.chat_message("assistant"):
            with st.spinner("Calculating..."):
                response = interact(prompt)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

elif not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write(
            "Hello, I'm your foxy finance expert. Click the 🎙️ to talk or type below!"
        )
