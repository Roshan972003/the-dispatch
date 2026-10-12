"""Thin Gemini REST client (Gemini Flash only, per the brief)."""
import json, time
import httpx
from app import config

class LLMUnavailable(Exception):
    pass

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

def generate(system, prompt, schema=None, temperature=0.4, fast=False):
    return generate_parts(system, [{"text": prompt}], schema, temperature, fast)

def generate_parts(system, parts, schema=None, temperature=0.4, fast=False):
    """parts: [{"text": ...}] or with audio [{"inline_data": {"mime_type": "audio/ogg", "data": <base64>}}, {"text": ...}]."""
    if not config.GEMINI_API_KEY:
        raise LLMUnavailable("GEMINI_API_KEY is not set")
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": temperature}}
    if fast:        # interactive taps: skip the extra reasoning pass (about 4x quicker on the same rewrite). The batch editorial pass keeps full thinking.
        body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
    if schema:
        body["generationConfig"]["responseMimeType"] = "application/json"
        body["generationConfig"]["responseSchema"] = schema
    last = None
    for attempt in range(4):
        try:
            r = httpx.post(URL.format(model=config.GEMINI_MODEL), headers={"x-goog-api-key": config.GEMINI_API_KEY}, json=body, timeout=55)
            if r.status_code in (429, 500, 503):
                last = f"HTTP {r.status_code}"; time.sleep(2 * (attempt + 1)); continue
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            return json.loads(text) if schema else text
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
            last = str(e)[:150]; time.sleep(1.5 * (attempt + 1))
    raise LLMUnavailable(f"Gemini call failed: {last}")
