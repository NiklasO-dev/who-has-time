(function () {
    var config = window.WHT_GRID;
    if (!config) return;

    var grid = document.getElementById("availability-grid");
    var wrapper = document.getElementById("grid-wrapper");
    if (!grid) return;

    var dayCount = grid.classList.contains("calendar-grid")
        ? 7
        : grid.querySelectorAll(".grid-day-header").length;
    if (dayCount) {
        grid.style.setProperty("--day-count", String(dayCount));
    }

    var selected = new Set(config.selectedSlots || []);
    var isDragging = false;
    var dragMode = null;
    var activeTab = config.mode === "select" ? "select" : "heatmap";

    var nameInput = document.getElementById("display-name");
    var saveBtn = document.getElementById("save-availability");
    var saveStatus = document.getElementById("save-status");
    var editLinkSection = document.getElementById("edit-link-section");
    var editUrlInput = document.getElementById("edit-url");
    var editToken = config.editToken || null;

    var i18n = config.i18n || {};
    var storageKey = config.storageKey;
    var nameKey = storageKey + "_name";
    var editKey = storageKey + "_edit";

    function showEditLink(url) {
        if (!editLinkSection || !editUrlInput || !url) return;
        editUrlInput.value = url;
        editLinkSection.hidden = false;
    }

    function loadFromStorage() {
        if (editToken) {
            if (config.editUrl) showEditLink(config.editUrl);
            return;
        }
        var storedToken = localStorage.getItem(editKey);
        var storedName = localStorage.getItem(nameKey);
        if (storedName && nameInput && !nameInput.value) {
            nameInput.value = storedName;
        }
        if (storedToken && config.loadUrlBase) {
            var url = config.loadUrlBase.replace("__TOKEN__", encodeURIComponent(storedToken));
            fetch(url)
                .then(function (r) {
                    if (!r.ok) throw new Error("not found");
                    return r.json();
                })
                .then(function (data) {
                    editToken = data.edit_token;
                    selected = new Set(data.selected_slots);
                    if (nameInput) nameInput.value = data.display_name;
                    syncCells();
                    if (data.edit_url) {
                        showEditLink(data.edit_url);
                    } else if (data.edit_token && config.editUrlBase) {
                        showEditLink(config.editUrlBase.replace("__TOKEN__", encodeURIComponent(data.edit_token)));
                    }
                })
                .catch(function () {
                    localStorage.removeItem(editKey);
                });
        }
    }

    var participantForm = document.querySelector(".participant-form");
    var heatmapEmpty = document.getElementById("grid-heatmap-empty");

    function syncCells() {
        grid.querySelectorAll(".grid-cell[data-index]").forEach(function (cell) {
            var idx = parseInt(cell.getAttribute("data-index"), 10);
            cell.classList.toggle("selected", selected.has(idx));
        });
    }

    function heatmapColor(count, total) {
        if (total <= 0 || count <= 0) return "";
        var ratio = count / total;
        var hue = Math.round(120 * ratio);
        var lightness = 45 + Math.round(25 * ratio);
        return "hsl(" + hue + ", 65%, " + lightness + "%)";
    }

    function setCellCountBadge(cell, count, show) {
        var countEl = cell.querySelector(".cell-count");
        if (show && count > 0) {
            if (!countEl) {
                countEl = document.createElement("span");
                countEl.className = "cell-count";
                cell.appendChild(countEl);
            }
            countEl.textContent = String(count);
        } else if (countEl) {
            countEl.remove();
        }
    }

    function responseTotal() {
        return parseInt(grid.getAttribute("data-response-count"), 10) || config.responseCount || 0;
    }

    function applyHeatmapView() {
        var total = responseTotal();
        grid.querySelectorAll(".grid-cell[data-index]").forEach(function (cell) {
            var count = parseInt(cell.getAttribute("data-count"), 10) || 0;
            cell.style.backgroundColor = heatmapColor(count, total);
            setCellCountBadge(cell, count, total > 0);
        });
        updateHeatmapEmptyState(total);
    }

    function applySelectView() {
        grid.querySelectorAll(".grid-cell[data-index]").forEach(function (cell) {
            cell.style.backgroundColor = "";
            setCellCountBadge(cell, 0, false);
        });
        syncCells();
        updateHeatmapEmptyState();
    }

    function updateHeatmapEmptyState(total) {
        if (!heatmapEmpty) return;
        if (total === undefined) total = responseTotal();
        heatmapEmpty.hidden = activeTab !== "heatmap" || total > 0;
    }

    function updateHeatmapCells(heatmap, total) {
        grid.setAttribute("data-response-count", String(total));
        config.responseCount = total;
        grid.querySelectorAll(".grid-cell[data-index]").forEach(function (cell) {
            var idx = parseInt(cell.getAttribute("data-index"), 10);
            cell.setAttribute("data-count", String(heatmap[idx] || 0));
        });
        if (activeTab === "heatmap") {
            applyHeatmapView();
        } else {
            updateHeatmapEmptyState(total);
        }
    }

    function setTab(tab) {
        activeTab = tab;
        grid.setAttribute("data-mode", tab === "heatmap" ? "heatmap" : "select");
        document.querySelectorAll(".grid-tab").forEach(function (btn) {
            var isActive = btn.getAttribute("data-tab") === tab;
            btn.classList.toggle("active", isActive);
            btn.setAttribute("aria-selected", isActive ? "true" : "false");
        });
        if (participantForm) {
            participantForm.hidden = tab === "heatmap";
        }
        if (tab === "heatmap") {
            applyHeatmapView();
        } else {
            applySelectView();
        }
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
                    edit_token: editToken
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
                    editToken = result.data.edit_token;
                    localStorage.setItem(editKey, editToken);
                    localStorage.removeItem(storageKey + "_response_id");
                    localStorage.setItem(nameKey, name);
                    if (result.data.heatmap) {
                        updateHeatmapCells(result.data.heatmap, result.data.response_count);
                    }
                    if (result.data.created && result.data.edit_url) {
                        showEditLink(result.data.edit_url);
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

    var attendeeCells = grid.querySelectorAll(".grid-cell[data-attendees]");
    if (attendeeCells.length) {
        var tooltip = document.createElement("div");
        tooltip.className = "grid-slot-tooltip";
        tooltip.setAttribute("role", "tooltip");
        tooltip.hidden = true;
        document.body.appendChild(tooltip);

        function hideTooltip() {
            tooltip.hidden = true;
        }

        function showTooltip(cell) {
            var raw = cell.getAttribute("data-attendees");
            if (!raw) {
                hideTooltip();
                return;
            }
            var names;
            try {
                names = JSON.parse(raw);
            } catch (err) {
                hideTooltip();
                return;
            }
            if (!names.length) {
                hideTooltip();
                return;
            }

            tooltip.textContent = "";
            var list = document.createElement("ul");
            names.forEach(function (name) {
                var item = document.createElement("li");
                item.textContent = name;
                list.appendChild(item);
            });
            tooltip.appendChild(list);
            tooltip.hidden = false;
            tooltip.style.visibility = "hidden";

            var rect = cell.getBoundingClientRect();
            var tipRect = tooltip.getBoundingClientRect();
            var left = rect.left + rect.width / 2 - tipRect.width / 2;
            var top = rect.top - tipRect.height - 8;

            if (left < 8) left = 8;
            if (left + tipRect.width > window.innerWidth - 8) {
                left = window.innerWidth - tipRect.width - 8;
            }
            if (top < 8) {
                top = rect.bottom + 8;
            }

            tooltip.style.left = left + "px";
            tooltip.style.top = top + "px";
            tooltip.style.visibility = "";
        }

        attendeeCells.forEach(function (cell) {
            cell.addEventListener("mouseenter", function () {
                showTooltip(cell);
            });
            cell.addEventListener("mouseleave", hideTooltip);
            cell.addEventListener("focus", function () {
                showTooltip(cell);
            });
            cell.addEventListener("blur", hideTooltip);
        });

        grid.addEventListener("mouseleave", hideTooltip);
        window.addEventListener("scroll", hideTooltip, true);
    }
})();
