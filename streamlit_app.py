import streamlit as st
import os
import json
import requests
from groq import Groq

st.set_page_config(page_title="Mental Health Mentor", layout="wide")

st.markdown("# Mental Health Mentor")
st.write("Describe how you're feeling and get three short responses: Technical, Realistic, and Emotional support.")

MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
API_URL = st.secrets.get("API_URL") or os.getenv("API_URL")  # optional: point to your FastAPI /chat endpoint

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {'role': 'user'|'bot', 'text': str, 'reply': {technical,realistic,emotional}}


def call_backend_api(message: str, timeout=15):
    url = API_URL.rstrip('/') + '/chat' if API_URL else None
    if not url:
        return None, "No API_URL configured"
    try:
        res = requests.post(url, json={"user_id": "streamlit-user", "message": message}, timeout=timeout)
        if res.status_code != 200:
            return None, f"Server returned {res.status_code}: {res.text}"
        data = res.json()
        return data.get('reply'), None
    except Exception as e:
        return None, str(e)


def call_groq_direct(message: str):
    api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        return None, "GROQ API key not configured"
    client = Groq(api_key=api_key)
    messages = [
        {"role": "system", "content": open('prompt.py').read()},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": message},
    ]
    try:
        resp = client.chat.completions.create(model=MODEL_NAME, messages=messages)
        text = resp.choices[0].message.content
        try:
            parsed = json.loads(text)
            return parsed, None
        except Exception:
            return {"technical": "", "realistic": "", "emotional": text}, None
    except Exception as e:
        return None, str(e)


# Input box
with st.form(key="input_form", clear_on_submit=True):
    user_text = st.text_area("How are you feeling?", key="user_text", height=120)
    submitted = st.form_submit_button("Send")

if submitted:
    if not user_text.strip():
        st.warning("Please enter a message.")
    else:
        # append user message to history
        st.session_state.messages.append({"role": "user", "text": user_text})

        # get reply from backend if configured, else Groq direct
        with st.spinner("Thinking..."):
            reply = None
            err = None
            if API_URL:
                reply, err = call_backend_api(user_text)
            else:
                reply, err = call_groq_direct(user_text)

        if err:
            # show an error bot message
            st.session_state.messages.append({"role": "bot", "reply": {"technical": "", "realistic": "", "emotional": f"Error: {err}"}})
        else:
            # normalize reply to have keys
            technical = reply.get('technical','') if isinstance(reply, dict) else ''
            realistic = reply.get('realistic','') if isinstance(reply, dict) else ''
            emotional = reply.get('emotional','') if isinstance(reply, dict) else ''
            st.session_state.messages.append({"role": "bot", "reply": {"technical": technical, "realistic": realistic, "emotional": emotional}})

# Display messages
for m in st.session_state.messages:
    if m["role"] == "user":
        st.markdown(f"**You:** {m['text']}")
    else:
        r = m.get('reply', {})
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            st.markdown("**Technical**")
            st.write(r.get('technical',''))
        with c2:
            st.markdown("**Realistic**")
            st.write(r.get('realistic',''))
        with c3:
            st.markdown("**Emotional**")
            st.write(r.get('emotional',''))
        # crisis banner
        emo_lower = (r.get('emotional','') or '').lower()
        if any(k in emo_lower for k in ("immediate danger", "call emergency", "988", "suicid")):
            st.error("If you are in immediate danger, call emergency services (e.g., 911) now. If you are in the US, call or text 988 for the Suicide & Crisis Lifeline.")

st.markdown("---")
st.caption("This tool provides mental health guidance but is not a substitute for professional care.")
