(function () {
    var config = window.WHT_ADMIN;
    if (!config || !config.sendLinksUrl) return;

    var sendBtn = document.getElementById("send-admin-links");
    var emailInput = document.getElementById("admin-links-email");
    var statusEl = document.getElementById("send-links-status");
    var i18n = config.i18n || {};

    function setStatus(msg, type) {
        if (!statusEl) return;
        statusEl.textContent = msg;
        statusEl.className = "send-link-status" + (type ? " " + type : "");
    }

    if (!sendBtn) return;

    sendBtn.addEventListener("click", function () {
        var email = emailInput ? emailInput.value.trim() : "";
        if (!email) {
            setStatus(i18n.emailRequired || "Please enter your email.", "error");
            return;
        }
        setStatus(i18n.sendingLink || "Sending…");
        sendBtn.disabled = true;
        fetch(config.sendLinksUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": config.csrfToken
            },
            body: JSON.stringify({ email: email })
        })
            .then(function (r) {
                return r.json().then(function (data) {
                    return { ok: r.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Send failed");
                }
                setStatus(i18n.linkSent || "Link sent!", "success");
            })
            .catch(function (err) {
                setStatus(err.message || i18n.linkSendFailed || "Could not send link.", "error");
            })
            .finally(function () {
                sendBtn.disabled = false;
            });
    });
})();
