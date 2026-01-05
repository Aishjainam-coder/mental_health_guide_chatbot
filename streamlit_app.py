import streamlit as st
import os
import json
import requests
from groq import Groq

st.set_page_config(page_title="Mental Health Mentor", layout="wide")

st.markdown("# Mental Health Mentor")
st.write("Describe how you're feeling and get three short responses: Technical, Realistic, and Emotional support.")

# Chat-style CSS to approximate the earlier UI (bubbles and columns)
st.markdown('''
<style>
.chat-container { background: linear-gradient(180deg,#071129 0%, #081427 100%); padding:16px; border-radius:12px; color:#e6eef8 }
.user-bubble{ background:#6ee7b7;color:#042;padding:10px 14px;border-radius:12px;display:inline-block; float:right; margin:8px 0; max-width:60%;}
.bot-bubble{ background:#e6eef8;color:#061125;padding:12px 14px;border-radius:12px;display:inline-block; float:left; margin:8px 0; max-width:60%;}
.clearfix{clear:both}
.columns-row{display:flex;gap:12px;margin:10px 0}
.column{flex:1}
.column .bubble{background:#e6eef8;color:#061125;padding:12px;border-radius:12px}
.crisis-banner{background:#7f1d1d;color:#fff;padding:8px 12px;border-radius:8px;margin:10px 0}
</style>
''', unsafe_allow_html=True)

# Add a clear chat button
if st.button("Clear chat"):
    st.session_state.messages = []


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

# Display messages in chat-like UI
chat_html = '<div class="chat-container">'
for m in st.session_state.messages:
    if m["role"] == "user":
        # user bubble (right aligned)
        chat_html += f"<div class=\"user-bubble\">{m['text']}</div><div class=\"clearfix\"></div>"
    else:
        r = m.get('reply', {})
        # bot columns row
        tech = r.get('technical','')
        real = r.get('realistic','')
        emo = r.get('emotional','')
        chat_html += '<div class="columns-row">'
        chat_html += f"<div class=\"column\"><div class=\"bubble\"><strong>Technical</strong><div style=\"margin-top:8px\">{tech}</div></div></div>"
        chat_html += f"<div class=\"column\"><div class=\"bubble\"><strong>Realistic</strong><div style=\"margin-top:8px\">{real}</div></div></div>"
        chat_html += f"<div class=\"column\"><div class=\"bubble\"><strong>Emotional</strong><div style=\"margin-top:8px\">{emo}</div></div></div>"
        chat_html += '</div>'
        # crisis banner below if present
        emo_lower = (emo or '').lower()
        if any(k in emo_lower for k in ("immediate danger", "call emergency", "988", "suicid")):
            chat_html += f"<div class=\"crisis-banner\">{emo}</div>"

chat_html += '</div>'

st.markdown(chat_html, unsafe_allow_html=True)

st.markdown("---")
st.caption("This tool provides mental health guidance but is not a substitute for professional care.")
