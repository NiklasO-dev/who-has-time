(function () {
    var config = window.WHT_DATE_PICKER;
    if (!config) return;

    var rangeMode = document.getElementById("date-mode-range");
    var pickMode = document.getElementById("date-mode-pick");
    var timesMode = document.getElementById("time-mode-times");
    var wholeDayMode = document.getElementById("time-mode-whole-day");
    var rangeFields = document.getElementById("range-date-fields");
    var pickFields = document.getElementById("pick-date-fields");
    var timeFields = document.getElementById("time-fields");
    var timezoneFields = document.getElementById("timezone-fields");
    var timezoneInput = document.getElementById("timezone");
    var calendar = document.getElementById("date-picker-calendar");
    var pickedInput = document.getElementById("picked_dates");
    var pickCount = document.getElementById("pick-count");
    var pickStartHidden = document.getElementById("pick_start_date");
    var pickEndHidden = document.getElementById("pick_end_date");
    var pickWindowStart = document.getElementById("pick_window_start");
    var pickWindowEnd = document.getElementById("pick_window_end");
    var startDate = document.getElementById("start_date");
    var endDate = document.getElementById("end_date");
    var locked = !!config.locked;
    var selected = new Set();

    function parseIso(value) {
        if (!value) return null;
        var parts = value.split("-");
        if (parts.length !== 3) return null;
        return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    }

    function formatIso(d) {
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, "0");
        var day = String(d.getDate()).padStart(2, "0");
        return y + "-" + m + "-" + day;
    }

    function loadSelected() {
        selected = new Set();
        try {
            var data = JSON.parse(pickedInput.value || "[]");
            if (Array.isArray(data)) {
                data.forEach(function (item) {
                    selected.add(String(item));
                });
            }
        } catch (e) {
            selected = new Set();
        }
    }

    function saveSelected() {
        var values = Array.from(selected).sort();
        pickedInput.value = JSON.stringify(values);
        if (pickCount) {
            pickCount.textContent = config.countLabel.replace("{count}", String(values.length));
        }
    }

    function isPickMode() {
        return pickMode && pickMode.checked;
    }

    function isWholeDay() {
        return wholeDayMode && wholeDayMode.checked;
    }

    function syncModes() {
        var pick = isPickMode();
        if (rangeFields) rangeFields.hidden = pick;
        if (pickFields) pickFields.hidden = !pick;

        if (startDate) {
            if (pick) startDate.removeAttribute("name");
            else startDate.setAttribute("name", "start_date");
            startDate.disabled = pick || locked;
        }
        if (endDate) {
            if (pick) endDate.removeAttribute("name");
            else endDate.setAttribute("name", "end_date");
            endDate.disabled = pick || locked;
        }
        if (pickStartHidden) {
            if (pick) pickStartHidden.setAttribute("name", "start_date");
            else pickStartHidden.removeAttribute("name");
        }
        if (pickEndHidden) {
            if (pick) pickEndHidden.setAttribute("name", "end_date");
            else pickEndHidden.removeAttribute("name");
        }
        if (pickedInput) {
            if (pick) pickedInput.setAttribute("name", "picked_dates");
            else pickedInput.removeAttribute("name");
        }

        if (pickFields && pick) {
            syncPickWindow();
            renderCalendar();
        }
        if (timeFields) {
            var hideTimes = isWholeDay();
            timeFields.hidden = hideTimes;
            timeFields.querySelectorAll("input, select").forEach(function (el) {
                el.disabled = hideTimes || locked || el.readOnly;
            });
        }
        if (timezoneFields) {
            var hideTimezone = isWholeDay();
            timezoneFields.hidden = hideTimezone;
            if (timezoneInput) {
                if (hideTimezone) {
                    timezoneInput.removeAttribute("name");
                    timezoneInput.disabled = true;
                } else {
                    timezoneInput.setAttribute("name", "timezone");
                    timezoneInput.disabled = locked || timezoneInput.readOnly;
                }
            }
        }
    }

    function syncPickWindow() {
        if (!pickWindowStart || !pickWindowEnd) return;
        if (pickStartHidden) pickStartHidden.value = pickWindowStart.value;
        if (pickEndHidden) pickEndHidden.value = pickWindowEnd.value;
    }

    function monthLabel(d) {
        return config.months[d.getMonth()] + " " + d.getFullYear();
    }

    function dayLabel(d) {
        return d.getDate() + " " + config.months[d.getMonth()];
    }

    function renderCalendar() {
        if (!calendar) return;
        loadSelected();
        calendar.innerHTML = "";
        var start = parseIso(pickWindowStart && pickWindowStart.value);
        var end = parseIso(pickWindowEnd && pickWindowEnd.value);
        if (!start || !end || end < start) {
            calendar.innerHTML = "<p class=\"empty-state\">" + config.invalidRange + "</p>";
            return;
        }

        var gridStart = new Date(start);
        gridStart.setDate(gridStart.getDate() - ((gridStart.getDay() + 6) % 7));
        var gridEnd = new Date(end);
        gridEnd.setDate(gridEnd.getDate() + (6 - ((gridEnd.getDay() + 6) % 7)));

        config.weekdays.forEach(function (name, index) {
            var header = document.createElement("div");
            header.className = "calendar-weekday-header" + (index >= 5 ? " weekend" : "");
            header.textContent = name;
            calendar.appendChild(header);
        });

        var day = new Date(gridStart);
        while (day <= gridEnd) {
            var iso = formatIso(day);
            var inWindow = day >= start && day <= end;
            var isWeekend = day.getDay() === 0 || day.getDay() === 6;
            if (inWindow) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "grid-cell calendar-cell date-picker-cell";
                if (isWeekend) btn.classList.add("weekend");
                if (selected.has(iso)) btn.classList.add("selected");
                btn.setAttribute("data-day", iso);
                btn.setAttribute("aria-label", dayLabel(day));
                btn.innerHTML = "<span class=\"calendar-day-label\">" + dayLabel(day) + "</span>";
                if (!locked) {
                    btn.addEventListener("click", function (event) {
                        var targetIso = event.currentTarget.getAttribute("data-day");
                        if (selected.has(targetIso)) selected.delete(targetIso);
                        else selected.add(targetIso);
                        saveSelected();
                        renderCalendar();
                    });
                } else {
                    btn.disabled = true;
                    btn.tabIndex = -1;
                }
                calendar.appendChild(btn);
            } else {
                var empty = document.createElement("div");
                empty.className = "grid-cell calendar-cell calendar-cell-outside";
                if (isWeekend) empty.classList.add("weekend");
                empty.setAttribute("aria-hidden", "true");
                calendar.appendChild(empty);
            }
            day.setDate(day.getDate() + 1);
        }
        saveSelected();
    }

    if (rangeMode) rangeMode.addEventListener("change", syncModes);
    if (pickMode) pickMode.addEventListener("change", syncModes);
    if (timesMode) timesMode.addEventListener("change", syncModes);
    if (wholeDayMode) wholeDayMode.addEventListener("change", syncModes);
    if (pickWindowStart) pickWindowStart.addEventListener("change", function () {
        syncPickWindow();
        renderCalendar();
    });
    if (pickWindowEnd) pickWindowEnd.addEventListener("change", function () {
        syncPickWindow();
        renderCalendar();
    });
    if (startDate && pickWindowStart && !pickWindowStart.value) {
        pickWindowStart.value = startDate.value;
    }
    if (endDate && pickWindowEnd && !pickWindowEnd.value) {
        pickWindowEnd.value = endDate.value;
    }

    loadSelected();
    syncModes();
})();
