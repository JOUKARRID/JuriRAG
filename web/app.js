const form = document.querySelector("#question-form");
const questionInput = document.querySelector("#question");
const domainSelect = document.querySelector("#domain");
const retrieveToggle = document.querySelector("#retrieve-only");
const submitButton = document.querySelector("#submit-button");
const resultPanel = document.querySelector("#result-panel");
const resultError = document.querySelector("#result-error");
const answerText = document.querySelector("#answer-text");
const sourcesSection = document.querySelector("#sources-section");
const sourceList = document.querySelector("#source-list");
const resultTitle = document.querySelector("#result-title");
const resultKicker = document.querySelector("#result-kicker");
const domainTag = document.querySelector("#domain-tag");

function setStatus(id, value, state) {
  document.querySelector(`#${id}-status`).textContent = value;
  const dot = document.querySelector(`#${id}-dot`);
  dot.classList.toggle("good", state === "good");
  dot.classList.toggle("bad", state === "bad");
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    setStatus("api", "Connectée", "good");
    const count = Object.values(health.collections || {}).reduce((sum, n) => sum + n, 0);
    setStatus("index", count ? `${count.toLocaleString("fr-FR")} passages` : "Indisponible", count ? "good" : "bad");
    const llmText = health.llm?.configured
      ? `${health.llm.backend} · prêt`
      : `${health.llm?.backend || "LLM"} · clé absente`;
    setStatus("llm", llmText, health.llm?.configured ? "good" : "bad");
    document.querySelector("#sidebar-dot").style.background = health.status === "ready" ? "#45a875" : "#d3a44e";
  } catch {
    setStatus("api", "Hors ligne", "bad");
    setStatus("index", "Indisponible", "bad");
    setStatus("llm", "Indisponible", "bad");
    document.querySelector("#sidebar-dot").style.background = "#d57a65";
  }
}

function clearResult() {
  resultError.hidden = true;
  resultError.textContent = "";
  answerText.textContent = "";
  sourceList.replaceChildren();
  sourcesSection.hidden = true;
}

function renderSources(sources) {
  if (!sources.length) return;
  document.querySelector("#source-count").textContent = `${sources.length} extrait${sources.length > 1 ? "s" : ""}`;
  for (const [index, source] of sources.entries()) {
    const card = document.createElement("article");
    card.className = "source-card";
    const meta = document.createElement("div");
    meta.className = "source-meta";
    const details = [source.title, source.article, source.page ? `p. ${source.page}` : null, source.date].filter(Boolean);
    meta.textContent = `[${index + 1}] ${details.join(" · ")}`;
    card.append(meta);
    if (source.text) {
      const text = document.createElement("div");
      text.className = "source-text";
      text.textContent = source.text;
      card.append(text);
    }
    sourceList.append(card);
  }
  sourcesSection.hidden = false;
}

function domainName(domain) {
  return ({ travail: "Droit du travail", impots: "Fiscalité", cnss: "CNSS", autre: "Hors périmètre" })[domain] || domain;
}

async function ask(question) {
  clearResult();
  resultPanel.hidden = false;
  resultTitle.textContent = "Recherche en cours…";
  resultKicker.textContent = retrieveToggle.checked ? "RECHERCHE HYBRIDE" : "RÉPONSE";
  domainTag.textContent = "";
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "Recherche…";
  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        domain: domainSelect.value,
        mode: retrieveToggle.checked ? "retrieve" : "answer",
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Erreur serveur (${response.status}).`);
    resultTitle.textContent = retrieveToggle.checked ? "Extraits retrouvés" : "Réponse";
    domainTag.textContent = domainName(data.domain);
    if (data.answer) answerText.textContent = data.answer;
    renderSources(data.sources || []);
    if (retrieveToggle.checked && !(data.sources || []).length) answerText.textContent = "Aucun extrait n’a été retrouvé.";
  } catch (error) {
    resultTitle.textContent = "La requête a échoué";
    resultError.textContent = error.message || "Erreur inattendue.";
    resultError.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "Interroger";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (question) ask(question);
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    questionInput.value = button.dataset.question;
    questionInput.focus();
  });
});

retrieveToggle.addEventListener("change", () => {
  document.querySelector("#mode-hint").textContent = retrieveToggle.checked
    ? "Recherche vectorielle + BM25 en local, sans appel au fournisseur LLM."
    : "Réponse complète avec génération LLM et sources citées.";
});

document.querySelector("#theme-button").addEventListener("click", () => {
  document.body.classList.toggle("dark");
});

loadHealth();
