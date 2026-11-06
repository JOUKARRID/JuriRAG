import hashlib
import json
import os
import time
from pathlib import Path

import requests

from config import (CLAUDE_MODEL, GEMINI_MODEL, GROQ_MODEL, LLM_BACKEND,
                    LLM_FALLBACK, OLLAMA_MODEL, OLLAMA_URL, REASONING_EFFORT)

# Fournisseurs compatibles avec le format OpenAI : (url, variable d'environnement, modèle)
OPENAI_STYLE = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "GEMINI_API_KEY", GEMINI_MODEL),
    "groq": ("https://api.groq.com/openai/v1/chat/completions",
             "GROQ_API_KEY", GROQ_MODEL),
}
RETRY_CODES = {429, 500, 502, 503, 504}  # erreurs temporaires : on réessaie

CACHE_FILE = Path("data/llm_cache.json")
_CACHE = None


def _cache():
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _CACHE = {}
    return _CACHE


def _cache_save():
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(_cache(), ensure_ascii=False), encoding="utf-8")


def _model_name(backend):
    if backend in OPENAI_STYLE:
        return OPENAI_STYLE[backend][2]
    return {"claude": CLAUDE_MODEL, "ollama": OLLAMA_MODEL}.get(backend, backend)


def _post_with_retry(url, headers, payload, tries=6):
    last = ""
    for attempt in range(tries):
        r = None
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
        except requests.RequestException as e:  # coupure réseau, délai dépassé
            last = f"Erreur réseau : {e}"
        if r is not None:
            if r.ok:
                return r.json()
            last = f"Erreur {r.status_code} : {r.text[:300]}"
            if r.status_code not in RETRY_CODES:
                raise RuntimeError(last)  # erreur définitive (clé, modèle...) : inutile de réessayer
        if attempt < tries - 1:
            wait = min(5 * 2 ** attempt, 40)
            print(f"  (service occupé, nouvel essai dans {wait}s)", flush=True)
            time.sleep(wait)
    raise RuntimeError(last)


def _call_openai_style(backend, system, user, max_tokens):
    url, env_var, model = OPENAI_STYLE[backend]
    key = os.environ.get(env_var)
    if not key:
        raise RuntimeError(f"Variable {env_var} absente. Dans le terminal : "
                           f'$env:{env_var} = "ta-cle"')
    tokens = max(max_tokens, 1500)  # marge : la réflexion consomme aussi des tokens
    effort = REASONING_EFFORT
    text = ""
    for _ in range(4):
        payload = {"model": model, "temperature": 0, "max_tokens": tokens,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}]}
        if effort:
            payload["reasoning_effort"] = effort
        try:
            data = _post_with_retry(url, {"Authorization": "Bearer " + key}, payload)
        except RuntimeError as e:
            # paramètre de réflexion refusé par ce modèle : on le retire et on recommence
            if effort and str(e).startswith("Erreur 400") and "reason" in str(e).lower():
                effort = None
                continue
            raise
        choice = data["choices"][0]
        text = (choice["message"].get("content") or "").strip()
        if choice.get("finish_reason") == "length" and tokens < 8000:
            tokens *= 2  # réponse coupée : on réessaie avec plus de place
            print("  (réponse tronquée, nouvel essai avec plus de place)", flush=True)
            continue
        return text
    return text


def _ask_backend(backend, system, user, max_tokens):
    if backend in OPENAI_STYLE:
        return _call_openai_style(backend, system, user, max_tokens)

    if backend == "claude":
        import anthropic  # lit la clé dans ANTHROPIC_API_KEY
        client = anthropic.Anthropic()
        r = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if b.type == "text")

    r = requests.post(OLLAMA_URL, timeout=900, json={
        "model": OLLAMA_MODEL, "stream": False, "options": {"temperature": 0},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}]})
    r.raise_for_status()
    return r.json()["message"]["content"]


def _ask_cached(backend, system, user, max_tokens):
    raw = "\n".join([backend, _model_name(backend), system, user])
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    cache = _cache()
    if key in cache:
        return cache[key]
    text = _ask_backend(backend, system, user, max_tokens)
    if text:  # on ne garde jamais une réponse vide
        cache[key] = text
        _cache_save()
    return text


def ask(system, user, max_tokens=1000):
    """Envoie une question au modèle choisi dans config.py et retourne le texte."""
    try:
        return _ask_cached(LLM_BACKEND, system, user, max_tokens)
    except RuntimeError:
        fb = LLM_FALLBACK
        if (fb and fb != LLM_BACKEND and fb in OPENAI_STYLE
                and os.environ.get(OPENAI_STYLE[fb][1])):
            print(f"  ({LLM_BACKEND} indisponible, bascule sur {fb})", flush=True)
            return _ask_cached(fb, system, user, max_tokens)
        raise