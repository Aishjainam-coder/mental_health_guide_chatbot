import streamlit as st
import os
import json
from groq import Groq

st.set_page_config(page_title="Mental Health Mentor", layout="wide")

st.title("Mental Health Mentor")
st.write("Short, practical support: Technical, Realistic, and Emotional responses in three columns.")

# Load model name from env or allow override via UI
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def call_groq(message: str):
    api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ API key not found. Add GROQ_API_KEY to Streamlit Secrets or set it in the environment.")
        return None

    client = Groq(api_key=api_key)
    messages = [
        {"role": "system", "content": open('prompt.py').read()},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": message},
    ]

    # Call the Groq chat completion
    try:
        resp = client.chat.completions.create(model=MODEL_NAME, messages=messages)
        text = resp.choices[0].message.content
        return text
    except Exception as e:
        st.error(f"Model call failed: {str(e)}")
        return None

# Input area
with st.form("mh_form", clear_on_submit=False):
    user_input = st.text_area("How are you feeling?", height=120)
    submitted = st.form_submit_button("Send")

if submitted:
    if not user_input.strip():
        st.warning("Please write a message.")
    else:
        with st.spinner("Thinking..."):
            model_reply = call_groq(user_input)

        if model_reply:
            # Try to parse JSON
            try:
                parsed = json.loads(model_reply)
                technical = parsed.get('technical','')
                realistic = parsed.get('realistic','')
                emotional = parsed.get('emotional','')
            except Exception:
                # fallback: put whole message into emotional
                technical = ""
                realistic = ""
                emotional = model_reply

            c1, c2, c3 = st.columns(3)
            with c1:
                st.subheader("Technical")
                st.write(technical)
            with c2:
                st.subheader("Realistic")
                st.write(realistic)
            with c3:
                st.subheader("Emotional")
                st.write(emotional)

            # Danger hint: show a clear alert if emotional contains crisis text
            emo_lower = (emotional or '').lower()
            if any(k in emo_lower for k in ("immediate danger", "call emergency", "988", "suicid")):
                st.error("If you are in immediate danger, call emergency services (e.g., 911) now. If you are in the US, call or text 988 for the Suicide & Crisis Lifeline.")

# Footer notes
st.markdown("---")
st.caption("This tool provides mental health guidance but is not a substitute for professional care.")