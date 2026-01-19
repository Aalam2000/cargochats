(function () {
  const root = document.querySelector(".page");
  if (!root) return;

  const resourceId = root.dataset.resourceId;

  const apiKeyEl = document.getElementById("apiKey");
  const btnToggle = document.getElementById("btnToggle");
  const btnSave = document.getElementById("btnSave");
  const btnCheck = document.getElementById("btnCheck");
  const btnBack = document.getElementById("btnBack");
  const statusBox = document.getElementById("statusBox");

  let hasKey = root.dataset.hasKey === "1";
  let keyMask = root.dataset.keyMask || "";
  const DEFAULT_MASK = "*".repeat(24);

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

  function getKeyValue() {
    return (apiKeyEl.value || "").trim();
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

  // если ключ сохранён — при фокусе очищаем звёзды (чтобы можно было ввести новый),
  // при уходе — возвращаем звёзды, если оставили пусто.
  apiKeyEl.addEventListener("focus", () => {
    if (hasKey && keyMask && apiKeyEl.value === keyMask) apiKeyEl.value = "";
  });

  apiKeyEl.addEventListener("blur", () => {
    if (hasKey && keyMask && getKeyValue() === "") apiKeyEl.value = keyMask;
  });

  btnToggle.addEventListener("click", () => {
    const isPassword = apiKeyEl.getAttribute("type") === "password";
    apiKeyEl.setAttribute("type", isPassword ? "text" : "password");
    btnToggle.textContent = isPassword ? "Скрыть" : "Показать";
  });

  btnSave.addEventListener("click", async () => {
    clearStatus();

    const v = getKeyValue();

    // если ключ уже сохранён и поле не меняли — ничего не делаем
    if (hasKey && keyMask && v === keyMask) {
      showStatus("info", "Ключ уже сохранён.");
      return;
    }

    if (!v) {
      showStatus("err", "Введите API-ключ.");
      return;
    }

    btnSave.disabled = true;
    btnCheck.disabled = true;

    try {
      await postJson(`/ui/resources/${resourceId}/openai/key`, { api_key: v });

      hasKey = true;
      if (!keyMask) keyMask = DEFAULT_MASK;

      root.dataset.hasKey = "1";
      root.dataset.keyMask = keyMask;

      apiKeyEl.value = keyMask;
      apiKeyEl.setAttribute("type", "password");
      btnToggle.textContent = "Показать";

      showStatus("ok", "Сохранено.");
    } catch (e) {
      showStatus("err", `Ошибка сохранения: ${e.message}`);
    } finally {
      btnSave.disabled = false;
      btnCheck.disabled = false;
    }
  });

  btnCheck.addEventListener("click", async () => {
    clearStatus();

    const v = getKeyValue();

    const useStored = hasKey && ((keyMask && v === keyMask) || v === "");
    if (!useStored && !v) {
      showStatus("err", "Введите API-ключ.");
      return;
    }

    btnSave.disabled = true;
    btnCheck.disabled = true;

    try {
      showStatus("info", "Проверяю...");
      const body = useStored ? {} : { api_key: v };
      const r = await postJson(`/ui/resources/${resourceId}/openai/check`, body);

      if (r && r.ok === true) showStatus("ok", "Ключ работает.");
      else showStatus("err", (r && (r.error || r.detail)) ? (r.error || r.detail) : "Ключ не работает.");
    } catch (e) {
      showStatus("err", `Проверка не прошла: ${e.message}`);
    } finally {
      btnSave.disabled = false;
      btnCheck.disabled = false;
    }
  });
})();
