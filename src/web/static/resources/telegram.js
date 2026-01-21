document.addEventListener("DOMContentLoaded", () => {
    console.log("[telegram] loaded");

    const root = document.querySelector(".page");
    if (!root) return;

    const resourceId = root.dataset.resourceId;

    const phoneEl = document.getElementById("tgPhone");
    const apiIdEl = document.getElementById("tgApiId");
    const apiHashEl = document.getElementById("tgApiHash");
    const openaiEl = document.getElementById("openaiResource");
    const promptEl = document.getElementById("promptResource");

    const btnSave = document.getElementById("btnSave");
    const btnBack = document.getElementById("btnBack");
    const btnToggleHash = document.getElementById("btnToggleHash");
    const btnActivate = document.getElementById("btnActivate");
    const btnToggleSession = document.getElementById("btnToggleSession");

    const statusBox = document.getElementById("statusBox");

    const lampEl = document.getElementById("sessionLamp");
    const lampTextEl = document.getElementById("sessionLampText");

    const activationModal = document.getElementById("activationModal");
    const activationCodeEl = document.getElementById("tgActivateCode");
    const btnActivationCancel = document.getElementById("btnActivationCancel");
    const btnActivationConfirm = document.getElementById("btnActivationConfirm");
    const activationStatus = document.getElementById("activationStatus");

    const hasHash = root.dataset.hasHash === "1";
    const hashMask = root.dataset.hashMask || "";
    const DEFAULT_MASK = "*".repeat(16);

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
        if (!token || !btnBack) return;
        btnBack.href = withToken(btnBack.getAttribute("href"));
    })();

    function showStatus(type, text) {
        if (!statusBox) return;
        statusBox.style.display = "block";
        statusBox.className = `status ${type}`; // ok | err | info
        statusBox.textContent = text;
    }

    function clearStatus() {
        if (!statusBox) return;
        statusBox.style.display = "none";
        statusBox.textContent = "";
        statusBox.className = "status";
    }

    function showActivationStatus(type, text) {
        if (!activationStatus) return;
        activationStatus.style.display = "block";
        activationStatus.className = `status ${type}`; // ok | err | info
        activationStatus.textContent = text;
    }

    function clearActivationStatus() {
        if (!activationStatus) return;
        activationStatus.style.display = "none";
        activationStatus.textContent = "";
        activationStatus.className = "status";
    }

    async function postJson(url, body) {
        const res = await fetch(withToken(url), {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            credentials: "same-origin",
            body: JSON.stringify(body || {}),
        });

        let data = null;
        try {
            data = await res.json();
        } catch (_) {}

        if (!res.ok) {
            let msg = (data && (data.detail || data.error))
                ? (data.detail || data.error)
                : `HTTP ${res.status}`;

            if (data && typeof data.retry_after === "number") {
                msg += ` (подожди ${data.retry_after} сек)`;
            }
            throw new Error(msg);
        }

        return data;
    }

    function isActivated() {
        return root.dataset.sessionActivated === "1";
    }

    function currentSessionEnabled() {
        return root.dataset.sessionEnabled === "1";
    }

    function updateLamp() {
        const activated = isActivated();
        const enabled = currentSessionEnabled();
        const sessionId = root.dataset.sessionId || "";

        if (lampEl) {
            lampEl.classList.toggle("on", activated);
            lampEl.classList.toggle("off", !activated);
        }
        if (lampTextEl) {
            const a = activated ? "Сессия активна" : "Сессия не активна";
            const e = enabled ? "воркер включен" : "воркер выключен";
            const s = sessionId ? `· session_id=${sessionId}` : "";
            lampTextEl.textContent = `${a} · ${e} ${s}`.trim();
        }
    }

    function refreshEnableButton() {
        if (!btnToggleSession) return;

        // Доступна только при активной сессии: скрываем и дизейблим.
        if (!isActivated()) {
            btnToggleSession.disabled = true;
            btnToggleSession.style.display = "none";
            return;
        }

        btnToggleSession.style.display = "";
        btnToggleSession.disabled = false;
    }

    function applySessionState(state) {
        // state: {session_id, is_enabled, is_activated}
        root.dataset.sessionId = state.session_id || "";
        root.dataset.sessionEnabled = state.is_enabled ? "1" : "0";
        root.dataset.sessionActivated = state.is_activated ? "1" : "0";

        if (btnToggleSession) {
            btnToggleSession.textContent = state.is_enabled ? "Выключить сессию" : "Включить сессию";
        }

        updateLamp();
        refreshEnableButton();
    }

    // INIT
    updateLamp();
    refreshEnableButton();

    // api_hash mask behavior
    if (apiHashEl) {
        apiHashEl.addEventListener("focus", () => {
            if (hasHash && (apiHashEl.value === hashMask || apiHashEl.value === DEFAULT_MASK)) {
                apiHashEl.value = "";
            }
        });

        apiHashEl.addEventListener("blur", () => {
            const v = (apiHashEl.value || "").trim();
            if (hasHash && v === "") apiHashEl.value = hashMask || DEFAULT_MASK;
        });
    }

    if (btnToggleHash && apiHashEl) {
        btnToggleHash.addEventListener("click", () => {
            const isPassword = apiHashEl.getAttribute("type") === "password";
            apiHashEl.setAttribute("type", isPassword ? "text" : "password");
            btnToggleHash.textContent = isPassword ? "Скрыть" : "Показать";
        });
    }

    function parseOptionalInt(el) {
        if (!el) return null;
        const raw = (el.value || "").trim();
        if (!raw) return null;
        const n = Number(raw);
        if (!Number.isFinite(n) || n % 1 !== 0) return NaN;
        return n;
    }

    // SAVE
    if (btnSave) {
        btnSave.addEventListener("click", async () => {
            clearStatus();
            showStatus("info", "Сохраняю...");

            const api_id = parseOptionalInt(apiIdEl);
            if (api_id !== null) {
                if (!Number.isFinite(api_id) || api_id <= 0) {
                    showStatus("err", "Telegram API ID должен быть целым числом > 0.");
                    return;
                }
            }

            let api_hash = (apiHashEl?.value || "").trim();
            if (hasHash && (api_hash === (hashMask || DEFAULT_MASK))) api_hash = null;

            const openai_resource_id = parseOptionalInt(openaiEl);
            if (openai_resource_id !== null && !Number.isFinite(openai_resource_id)) {
                showStatus("err", "OpenAI ресурс выбран некорректно.");
                return;
            }

            const prompt_resource_id = parseOptionalInt(promptEl);
            if (prompt_resource_id !== null && !Number.isFinite(prompt_resource_id)) {
                showStatus("err", "Prompt ресурс выбран некорректно.");
                return;
            }

            btnSave.disabled = true;
            try {
                await postJson(`/ui/resources/${resourceId}/telegram/save`, {
                    phone: (phoneEl?.value || "").trim() || null,
                    api_id,
                    api_hash,
                    openai_resource_id,
                    prompt_resource_id,
                });
                showStatus("ok", "Сохранено.");
            } catch (e) {
                showStatus("err", `Ошибка сохранения: ${e.message}`);
            } finally {
                btnSave.disabled = false;
            }
        });
    }

    // MODAL helpers
    function openActivationModal() {
        if (!activationModal) return;
        clearActivationStatus();
        activationCodeEl.value = "";
        activationModal.classList.remove("hidden");
        activationCodeEl.focus();
    }

    function closeActivationModal() {
        if (!activationModal) return;
        activationModal.classList.add("hidden");
    }

    if (activationModal) {
        activationModal.addEventListener("click", (e) => {
            if (e.target === activationModal) closeActivationModal();
        });
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeActivationModal();
    });

    if (btnActivationCancel) {
        btnActivationCancel.addEventListener("click", () => closeActivationModal());
    }

    // ACTIVATE: start => send code (сначала проверка на бэке: ALREADY_ACTIVATED / ALREADY_STARTED / CODE_SENT)
    if (btnActivate) {
        btnActivate.addEventListener("click", async () => {
            clearStatus();

            const phone = (phoneEl?.value || "").trim();
            if (!phone) {
                showStatus("err", "Укажи телефон (E.164), чтобы запросить код.");
                return;
            }

            btnActivate.disabled = true;
            try {
                const resp = await postJson(
                    `/ui/resources/${resourceId}/telegram/session/activation/start`,
                    { phone }
                );

                const d = resp.detail || "";

                if (d === "ALREADY_ACTIVATED") {
                    applySessionState(resp);
                    showStatus("ok", "Сессия уже активна. Повторная активация не требуется.");
                    return;
                }

                if (d === "ALREADY_STARTED") {
                    showStatus("ok", "Код уже запрошен ранее. Введи код подтверждения.");
                    openActivationModal();
                    return;
                }

                if (d === "CODE_SENT") {
                    const metaParts = [
                        resp.sent_type ? `тип=${resp.sent_type}` : null,
                        resp.code_len ? `код=${resp.code_len} цифр` : null,
                        resp.timeout ? `timeout=${resp.timeout}` : null,
                        resp.next_type ? `next=${resp.next_type}` : null,
                    ].filter(Boolean);

                    showStatus(
                        "ok",
                        metaParts.length
                            ? `Telegram принял запрос (${metaParts.join(", ")}). Введи код подтверждения.`
                            : "Telegram принял запрос. Введи код подтверждения."
                    );

                    openActivationModal();
                    return;
                }

                showStatus("err", `Неожиданный ответ start: ${JSON.stringify(resp)}`);
            } catch (e) {
                showStatus("err", `Ошибка отправки кода: ${e.message}`);
            } finally {
                btnActivate.disabled = false;
            }
        });
    }

    // CONFIRM activation (code)
    if (btnActivationConfirm) {
        btnActivationConfirm.addEventListener("click", async () => {
            clearActivationStatus();

            const code = (activationCodeEl?.value || "").trim();
            if (!code) {
                showActivationStatus("err", "Введи код подтверждения.");
                return;
            }

            btnActivationConfirm.disabled = true;
            showActivationStatus("info", "Проверяю код...");

            try {
                const resp = await postJson(
                    `/ui/resources/${resourceId}/telegram/session/activation/confirm`,
                    { code }
                );
                applySessionState(resp);
                closeActivationModal();
                showStatus("ok", "Сессия активирована.");
            } catch (e) {
                showActivationStatus("err", `Ошибка: ${e.message}`);
            } finally {
                btnActivationConfirm.disabled = false;
            }
        });
    }

    // ENABLE/DISABLE (только если активирована)
    if (btnToggleSession) {
        btnToggleSession.addEventListener("click", async () => {
            clearStatus();

            if (!isActivated()) {
                showStatus("err", "Нельзя включить: сначала активируй сессию через код Telegram.");
                return;
            }

            const nextEnabled = !currentSessionEnabled();
            btnToggleSession.disabled = true;
            showStatus("info", "Применяю...");

            try {
                const resp = await postJson(
                    `/ui/resources/${resourceId}/telegram/session/set_enabled`,
                    { is_enabled: nextEnabled }
                );
                applySessionState(resp);
                showStatus("ok", nextEnabled ? "Сессия включена." : "Сессия выключена.");
            } catch (e) {
                showStatus("err", `Ошибка переключения: ${e.message}`);
            } finally {
                refreshEnableButton();
            }
        });
    }
});
