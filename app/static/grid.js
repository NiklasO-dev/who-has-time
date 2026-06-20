(function () {
    var config = window.WHT_GRID;
    if (!config) return;

    var grid = document.getElementById("availability-grid");
    var wrapper = document.getElementById("grid-wrapper");
    if (!grid) return;

    var dayCount = grid.querySelectorAll(".grid-day-header").length;
    grid.style.setProperty("--day-count", String(dayCount));

    var selected = new Set(config.selectedSlots || []);
    var isDragging = false;
    var dragMode = null;
    var activeTab = config.mode === "select" ? "select" : "heatmap";

    var nameInput = document.getElementById("display-name");
    var saveBtn = document.getElementById("save-availability");
    var saveStatus = document.getElementById("save-status");
    var responseId = config.responseId || null;

    var i18n = config.i18n || {};
    var storageKey = config.storageKey;
    var nameKey = storageKey + "_name";
    var responseKey = storageKey + "_response_id";

    function loadFromStorage() {
        if (responseId) return;
        var storedId = localStorage.getItem(responseKey);
        var storedName = localStorage.getItem(nameKey);
        if (storedName && nameInput && !nameInput.value) {
            nameInput.value = storedName;
        }
        if (storedId && config.loadUrlBase) {
            var url = config.loadUrlBase.replace("__ID__", encodeURIComponent(storedId));
            fetch(url)
                .then(function (r) {
                    if (!r.ok) throw new Error("not found");
                    return r.json();
                })
                .then(function (data) {
                    responseId = data.id;
                    selected = new Set(data.selected_slots);
                    if (nameInput) nameInput.value = data.display_name;
                    syncCells();
                })
                .catch(function () {
                    localStorage.removeItem(responseKey);
                });
        }
    }

    function syncCells() {
        grid.querySelectorAll(".grid-cell[data-index]").forEach(function (cell) {
            var idx = parseInt(cell.getAttribute("data-index"), 10);
            cell.classList.toggle("selected", selected.has(idx));
        });
    }

    function updateHeatmapCells(heatmap, total) {
        grid.querySelectorAll(".grid-cell[data-index]").forEach(function (cell) {
            var idx = parseInt(cell.getAttribute("data-index"), 10);
            var count = heatmap[idx] || 0;
            cell.setAttribute("data-count", String(count));
            if (total > 0) {
                var ratio = count / total;
                var hue = Math.round(120 * ratio);
                var lightness = 45 + Math.round(25 * ratio);
                cell.style.backgroundColor = "hsl(" + hue + ", 65%, " + lightness + "%)";
                var countEl = cell.querySelector(".cell-count");
                if (!countEl) {
                    countEl = document.createElement("span");
                    countEl.className = "cell-count";
                    cell.appendChild(countEl);
                }
                countEl.textContent = String(count);
            }
        });
    }

    function setTab(tab) {
        activeTab = tab;
        grid.setAttribute("data-mode", tab === "heatmap" ? "heatmap" : "select");
        document.querySelectorAll(".grid-tab").forEach(function (btn) {
            var isActive = btn.getAttribute("data-tab") === tab;
            btn.classList.toggle("active", isActive);
            btn.setAttribute("aria-selected", isActive ? "true" : "false");
        });
        syncCells();
    }

    document.querySelectorAll(".grid-tab").forEach(function (btn) {
        btn.addEventListener("click", function () {
            setTab(btn.getAttribute("data-tab"));
        });
    });

    function toggleCell(cell, forceOn) {
        if (!config.canEdit || activeTab !== "select") return;
        var idx = parseInt(cell.getAttribute("data-index"), 10);
        var turnOn = forceOn !== undefined ? forceOn : !selected.has(idx);
        if (turnOn) selected.add(idx);
        else selected.delete(idx);
        cell.classList.toggle("selected", selected.has(idx));
    }

    function onPointerDown(e) {
        if (!config.canEdit || activeTab !== "select") return;
        var cell = e.target.closest(".grid-cell[data-index]");
        if (!cell) return;
        e.preventDefault();
        isDragging = true;
        dragMode = !selected.has(parseInt(cell.getAttribute("data-index"), 10));
        toggleCell(cell, dragMode);
    }

    function onPointerEnter(e) {
        if (!isDragging) return;
        var cell = e.target.closest(".grid-cell[data-index]");
        if (cell) toggleCell(cell, dragMode);
    }

    function onPointerUp() {
        isDragging = false;
        dragMode = null;
    }

    grid.addEventListener("mousedown", onPointerDown);
    grid.addEventListener("mouseenter", onPointerEnter, true);
    document.addEventListener("mouseup", onPointerUp);

    grid.addEventListener("touchstart", function (e) {
        onPointerDown(e);
    }, { passive: false });

    grid.addEventListener("touchmove", function (e) {
        if (!isDragging) return;
        e.preventDefault();
        var touch = e.touches[0];
        var el = document.elementFromPoint(touch.clientX, touch.clientY);
        if (el) {
            var cell = el.closest(".grid-cell[data-index]");
            if (cell) toggleCell(cell, dragMode);
        }
    }, { passive: false });

    document.addEventListener("touchend", onPointerUp);
    document.addEventListener("touchcancel", onPointerUp);

    function setStatus(msg, type) {
        if (!saveStatus) return;
        saveStatus.textContent = msg;
        saveStatus.className = "save-status" + (type ? " " + type : "");
    }

    if (saveBtn) {
        saveBtn.addEventListener("click", function () {
            var name = nameInput ? nameInput.value.trim() : "";
            if (!name) {
                setStatus(i18n.nameRequired || "Please enter your name.", "error");
                return;
            }
            setStatus(i18n.saving || "Saving…");
            fetch(config.saveUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": config.csrfToken
                },
                body: JSON.stringify({
                    display_name: name,
                    selected_slots: Array.from(selected),
                    response_id: responseId
                })
            })
                .then(function (r) {
                    return r.json().then(function (data) {
                        return { ok: r.ok, data: data };
                    });
                })
                .then(function (result) {
                    if (!result.ok) {
                        throw new Error(result.data.error || "Save failed");
                    }
                    responseId = result.data.id;
                    localStorage.setItem(responseKey, responseId);
                    localStorage.setItem(nameKey, name);
                    if (result.data.heatmap) {
                        updateHeatmapCells(result.data.heatmap, result.data.response_count);
                    }
                    setStatus(i18n.saved || "Saved!", "success");
                })
                .catch(function (err) {
                    setStatus(err.message || i18n.saveFailed || "Save failed.", "error");
                });
        });
    }

    syncCells();
    loadFromStorage();
})();
