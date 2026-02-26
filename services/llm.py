"""
Groq LLaMA service -- all LLM interactions live here.

Three main capabilities:
1. extract_resume_fields  -- pull structured data from free-form English text
2. professionalize        -- rewrite resume sections in polished English
3. process_voice_command  -- understand edit / delete / add instructions
"""

import json
import os
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"


def _load_key():
    """Read the key from .env if not already in the environment."""
    global GROQ_API_KEY
    if GROQ_API_KEY:
        return GROQ_API_KEY
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("GROQ_API_KEY="):
                    GROQ_API_KEY = line.strip().split("=", 1)[1]
                    break
    return GROQ_API_KEY


def _chat(messages: list, temperature: float = 0.3, max_tokens: int = 2048) -> str:
    """Send a chat completion request to Groq and return the assistant text."""
    key = _load_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]


# ── 1. Extract structured resume fields from free text ────────────────────

EXTRACT_SYSTEM = """You are a resume-data extractor. Given English text spoken by a user, extract ONLY the information that is clearly present.

Return STRICTLY valid JSON with these keys (omit keys whose value you cannot determine):
{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "linkedin": "string or null",
  "github": "string or null",
  "summary": "string or null",
  "education": [{"institution": "", "degree": "", "year": ""}],
  "skills": ["skill1", "skill2"],
  "experience": [{"company": "", "role": "", "duration": "", "bullets": [""]}],
  "projects": [{"name": "", "description": "", "tech_stack": [""]}]
}

Rules:
- Return ONLY the JSON object, no markdown, no explanation.
- For list fields, return [] if nothing found.
- For string fields, return null if nothing found.
- Preserve the user's data accurately; do not invent information."""


def extract_resume_fields(english_text: str) -> dict:
    """Extract structured resume data from free-form English text."""
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": english_text},
    ]
    raw = _chat(messages, temperature=0.1)
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[EXTRACT] Failed to parse JSON:\n{raw}")
        return {}


# ── 2. Professionalize resume content ─────────────────────────────────────

PROFESSIONALIZE_SYSTEM = """You are a professional resume writer. Given resume data as JSON, rewrite every text field to sound polished, concise, and professional, suitable for a modern tech resume.

Rules:
- Keep all factual information intact -- names, dates, companies, technologies.
- Improve grammar, wording, and impact of bullet points.
- The summary should be 2-3 compelling sentences.
- Skills list stays as-is (just clean formatting).
- Return the SAME JSON structure with improved text.
- Return ONLY valid JSON, no markdown, no explanation."""


def professionalize(resume_data: dict) -> dict:
    """Rewrite resume content to be professional quality."""
    messages = [
        {"role": "system", "content": PROFESSIONALIZE_SYSTEM},
        {"role": "user", "content": json.dumps(resume_data, indent=2)},
    ]
    raw = _chat(messages, temperature=0.4)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[PROFESSIONALIZE] Failed to parse JSON:\n{raw}")
        return resume_data  # return original if parsing fails


# ── 3. Process voice commands (edit / delete / add) ───────────────────────

COMMAND_SYSTEM = """You are a resume-editing assistant. The user will give a voice command about their resume.
You have the current resume data and must determine what action to take.

Possible actions:
1. "delete" -- remove something from the resume
2. "edit"   -- change/update a specific value
3. "add"    -- add new information

Return STRICTLY valid JSON:
{
  "action": "delete" | "edit" | "add",
  "field": "name|email|phone|linkedin|github|summary|education|skills|experience|projects",
  "details": "what specifically to delete/edit/add",
  "value": "the new value if editing or adding (null for delete)",
  "index": null or integer (0-based index for list items, null for simple fields)
}

Rules:
- Return ONLY the JSON, no explanation.
- If the command is unclear, set action to "unknown" and put a clarification in "details".
- For deleting a skill, set field="skills", and put the skill name in "details".
- For deleting an experience entry, set field="experience" and index to the position.
- For deleting a project, set field="projects" and index to the position.
- For editing a simple field like name/email, set field and value accordingly."""


def process_voice_command(command_text: str, current_resume: dict) -> dict:
    """Interpret a voice command and return the action to perform."""
    user_msg = (
        f"Current resume data:\n{json.dumps(current_resume, indent=2)}\n\n"
        f"User command: {command_text}"
    )
    messages = [
        {"role": "system", "content": COMMAND_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    raw = _chat(messages, temperature=0.1)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[COMMAND] Failed to parse JSON:\n{raw}")
        return {"action": "unknown", "details": "Could not understand the command"}
