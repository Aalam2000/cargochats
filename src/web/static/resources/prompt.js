(function () {
  const root = document.querySelector(".page");
  if (!root) return;

  const resourceId = root.dataset.resourceId;

  const modelEl = document.getElementById("modelSelect");
  const historyPairsEl = document.getElementById("historyPairs");
  const systemPromptEl = document.getElementById("systemPrompt");
  const outOfScopeEl = document.getElementById("outOfScopeEnabled");

  const sourcesListEl = document.getElementById("sourcesList");
  const btnAddSource = document.getElementById("btnAddSource");

  const btnSave = document.getElementById("btnSave");
  const btnBack = document.getElementById("btnBack");
  const statusBox = document.getElementById("statusBox");

  function getTokenFromUrl() {
    const t = new URLSearchParams(window.location.search).get("token");
    return t && t.trim() ? t.trim() : null;
  }

  function withToken(url) {
    const token = getTokenFromUrl();
    if (!token) return url;
    return url.includes("?")
      ? `${url}&token=${encodeURIComponent(token)}`
      : `${url}?token=${encodeURIComponent(token)}`;
  }

  (function patchBackLink() {
    const token = getTokenFromUrl();
    if (!token) return;
    btnBack.href = withToken(btnBack.getAttribute("href"));
  })();

  function showStatus(type, text) {
    statusBox.style.display = "block";
    statusBox.className = `status ${type}`; // ok | err | info
    statusBox.textContent = text;
  }

  function clearStatus() {
    statusBox.style.display = "none";
    statusBox.textContent = "";
    statusBox.className = "status";
  }

  async function postJson(url, body) {
    const res = await fetch(withToken(url), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body || {}),
    });

    let data = null;
    try { data = await res.json(); } catch (_) {}

    if (!res.ok) {
      const msg = (data && (data.detail || data.error)) ? (data.detail || data.error) : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  function addSourceRow(value) {
    const row = document.createElement("div");
    row.className = "source-row";
    row.style.cssText = "display:flex; gap:10px; align-items:center; margin-bottom:10px;";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "source-url";
    input.placeholder = "https://docs.google.com/...";
    input.value = value || "";
    input.style.flex = "1";

    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn secondary btn-del";
    del.textContent = "Удалить";
    del.addEventListener("click", () => row.remove());

    row.appendChild(input);
    row.appendChild(del);
    sourcesListEl.appendChild(row);
  }

  // подвесим delete на уже существующие строки (из шаблона)
  sourcesListEl.querySelectorAll(".source-row .btn-del").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const row = e.target.closest(".source-row");
      if (row) row.remove();
    });
  });

  btnAddSource.addEventListener("click", () => addSourceRow(""));

  function collectSources() {
    const urls = [];
    sourcesListEl.querySelectorAll(".source-url").forEach((inp) => {
      const v = (inp.value || "").trim();
      if (v) urls.push(v);
    });
    return urls;
  }

  btnSave.addEventListener("click", async () => {
    clearStatus();

    const model = (modelEl.value || "").trim();
    const system_prompt = (systemPromptEl.value || "").trim();

    let history_pairs = null;
    const rawHp = (historyPairsEl.value || "").trim();
    if (rawHp !== "") {
      const n = Number(rawHp);
      if (!Number.isFinite(n) || n < 0 || n > 50) {
        showStatus("err", "History должен быть числом 0..50.");
        return;
      }
      history_pairs = Math.floor(n);
    }

    const google_sources = collectSources();
    const out_of_scope_enabled = !!outOfScopeEl.checked;

    btnSave.disabled = true;
    try {
      await postJson(`/ui/resources/${resourceId}/prompt/save`, {
        model,
        system_prompt,
        history_pairs,
        google_sources,
        out_of_scope_enabled,
      });
      showStatus("ok", "Сохранено.");
    } catch (e) {
      showStatus("err", `Ошибка сохранения: ${e.message}`);
    } finally {
      btnSave.disabled = false;
    }
  });
})();
