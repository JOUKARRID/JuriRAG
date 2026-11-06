import os
import time

import requests

from config import GROQ_MODEL, LLM_BACKEND, LLM_FALLBACK

print("Backend principal      :", LLM_BACKEND)
print("Secours                :", LLM_FALLBACK)
print("GROQ_API_KEY définie   :", bool(os.environ.get("GROQ_API_KEY")))
print("GEMINI_API_KEY définie :", bool(os.environ.get("GEMINI_API_KEY")))

key = os.environ.get("GROQ_API_KEY")
if not key:
    raise SystemExit('Clé Groq absente dans CE terminal. Tape : $env:GROQ_API_KEY = "ta-cle"')

t0 = time.time()
r = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {key}"},
    json={"model": GROQ_MODEL, "max_tokens": 500,
          "messages": [{"role": "user", "content": "Réponds par le seul mot : OK"}]},
    timeout=60)
print(f"\nCode HTTP : {r.status_code}  ({time.time() - t0:.1f}s)")
if r.ok:
    data = r.json()
    print("Modèle utilisé par Groq :", data.get("model"))
    print("Réponse :", data["choices"][0]["message"]["content"])
else:
    print(r.text[:400])