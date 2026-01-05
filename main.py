from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

from prompt import SYSTEM_PROMPT
from memory import get_memory, update_memory
import logging
import json
import time
import concurrent.futures

# Use Groq API client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Model to use (configure via env var)
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

# Warn at startup if the default model is the decommissioned one so the developer notices
logger = logging.getLogger("uvicorn.error")
if MODEL_NAME == "llama-3.1-70b-versatile":
    logger.warning("Using default GROQ model 'llama-3.1-70b-versatile'. If you see a model_decommissioned error, set GROQ_MODEL to a supported model. See https://console.groq.com/docs/deprecations")

app = FastAPI()

# Serve index.html at root (do not override API routes)
@app.get("/", include_in_schema=False)
def read_root():
    return FileResponse("index.html")

# Mount other static assets under /static if needed
app.mount("/static", StaticFiles(directory=".", html=True), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_id: str
    message: str

@app.post("/chat")
def chat(req: ChatRequest):
    logger = logging.getLogger("uvicorn.error")
    logger.info("/chat request received user_id=%s", req.user_id)

    # Allow tests to monkeypatch `client.chat`; require GROQ_API_KEY or a patched client
    if not os.getenv("GROQ_API_KEY") and not getattr(client, "chat", None):
        logger.error("GROQ_API_KEY not configured and no monkeypatched client available")
        raise HTTPException(
            status_code=500,
            detail="Groq API key not configured"
        )

    # Input validation: enforce reasonable length
    MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))
    if len(req.message or "") > MAX_MESSAGE_LENGTH:
        logger.warning("Message too long from user_id=%s length=%d", req.user_id, len(req.message or ""))
        raise HTTPException(status_code=400, detail=f"Message too long (max {MAX_MESSAGE_LENGTH} characters)")

    memory = get_memory(req.user_id)

    # Quick crisis detection (server-side) using simple keyword checks to avoid calling the model
    msg_lower = (req.message or "").lower()
    crisis_keywords = ["kill myself", "i want to die", "suicid", "end my life", "i can\'t go on", "hurt myself"]
    if any(k in msg_lower for k in crisis_keywords):
        logger.info("Crisis detected for user_id=%s, returning safe response", req.user_id)
        # Return immediate safe JSON per prompt safety rules
        safe = {
            "technical": "",
            "realistic": "",
            "emotional": (
                "I\'m really sorry you\'re feeling this way — if you are in immediate danger, please call emergency services (e.g., 911) now. "
                "If you are in the US, call or text 988 for the Suicide & Crisis Lifeline. "
                "Please consider contacting someone you trust or a local crisis hotline."
            )
        }
        return {"reply": safe}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": f"User memory: {memory}"},
        {"role": "user", "content": req.message}
    ]

    # Call model, with a retry if the output is not valid JSON
    def call_model_once(extra_system=None):
        msgs = messages.copy()
        if extra_system:
            msgs.insert(0, {"role":"system","content": extra_system})
        return client.chat.completions.create(model=MODEL_NAME, messages=msgs)

    # Call model, with a retry if the output is not valid JSON
    def call_model_once(extra_system=None):
        msgs = messages.copy()
        if extra_system:
            msgs.insert(0, {"role":"system","content": extra_system})
        return client.chat.completions.create(model=MODEL_NAME, messages=msgs)

    model_timeout = int(os.getenv('MODEL_TIMEOUT', '8'))
    logger.info("Calling model for user_id=%s model=%s (timeout=%ds)", req.user_id, MODEL_NAME, model_timeout)

    start_t = time.time()
    response = None
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_model_once)
            try:
                response = future.result(timeout=model_timeout)
                elapsed = time.time() - start_t
                logger.info("Model call completed in %.2fs", elapsed)
                if elapsed > 10:
                    logger.warning("Model call took long (%.2fs) for user_id=%s", elapsed, req.user_id)
            except concurrent.futures.TimeoutError:
                logger.warning("Model call timed out after %ds for user_id=%s", model_timeout, req.user_id)
                # Cancel the future and return a safe fallback reply
                future.cancel()
                reply = {'technical': '', 'realistic': '', 'emotional': 'The service is taking too long to respond. Please try again in a moment.'}
                return {'reply': reply}
    except Exception as e:
        error_msg = str(e)
        logger.exception("Model call failed: %s", error_msg)
        # Check for rate limit or quota issues
        if "rate limit" in error_msg.lower() or "429" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Groq API rate limit exceeded. Please try again later."
            )
        elif "quota" in error_msg.lower() or "insufficient" in error_msg.lower():
            raise HTTPException(
                status_code=402,
                detail="Groq API quota exceeded. Please check your plan and billing details."
            )
        # Handle decommissioned model error from Groq (explicit guidance)
        elif "decommissioned" in error_msg.lower() or "model_decommissioned" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=("The configured GROQ model appears to be decommissioned. "
                        "Please set a supported model in the GROQ_MODEL environment variable. "
                        "See: https://console.groq.com/docs/deprecations for recommended replacements. "
                        f"(Original error: {error_msg})")
            )
        raise HTTPException(
            status_code=500,
            detail=f"Groq API error: {error_msg}"
        )

    reply_text = response.choices[0].message.content

    # Try to parse JSON produced by system prompt (the model should output JSON with three keys)
    def parse_reply(text):
        try:
            parsed = json.loads(text)
            technical = parsed.get('technical')
            realistic = parsed.get('realistic')
            emotional = parsed.get('emotional')
            if not (technical and realistic and emotional):
                raise ValueError('Missing expected keys')
            return {'technical': technical, 'realistic': realistic, 'emotional': emotional}
        except Exception:
            return None

    reply = parse_reply(reply_text)
    if reply is None:
        # Retry once with explicit instruction to ONLY output JSON (be extra strict)
        stricter = SYSTEM_PROMPT + "\n\nSTRICT: Return only a single JSON object with keys technical, realistic, emotional, nothing else." 
        try:
            response2 = call_model_once(extra_system=stricter)
            reply2 = parse_reply(response2.choices[0].message.content)
            if reply2:
                reply = reply2
            else:
                # fallback JSON with the original text in the emotional slot
                reply = {'technical': '', 'realistic': '', 'emotional': reply_text}
        except Exception:
            reply = {'technical': '', 'realistic': '', 'emotional': reply_text}


    reply_text = response.choices[0].message.content

    # Try to parse JSON produced by system prompt (the model should output JSON with three keys)
    try:
        parsed = json.loads(reply_text)
        # Ensure keys exist
        technical = parsed.get('technical')
        realistic = parsed.get('realistic')
        emotional = parsed.get('emotional')
        if not (technical and realistic and emotional):
            raise ValueError('Missing expected keys')
        reply = { 'technical': technical, 'realistic': realistic, 'emotional': emotional }
    except Exception:
        # Fallback: attempt simple split by delimiter, or return whole text as 'emotional'
        parts = reply_text.split('---') if '---' in reply_text else None
        if parts and len(parts) >= 3:
            reply = { 'technical': parts[0].strip(), 'realistic': parts[1].strip(), 'emotional': parts[2].strip() }
        else:
            # Put whole reply under 'emotional' to be safe
            reply = { 'technical': '', 'realistic': '', 'emotional': reply_text }

    if "beginner" in req.message.lower():
        update_memory(req.user_id, {"level": "beginner"})

    return {"reply": reply}
