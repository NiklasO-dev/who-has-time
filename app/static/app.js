(function () {
    var btn = document.getElementById("theme-toggle");
    var i18n = window.WHT_I18N || {};
    if (btn) {
        var html = document.documentElement;

        function updateIcon() {
            btn.textContent = html.getAttribute("data-theme") === "dark" ? "☀️" : "🌙";
        }

        updateIcon();
        btn.addEventListener("click", function () {
            var current = html.getAttribute("data-theme");
            var next = current === "dark" ? "light" : "dark";
            html.setAttribute("data-theme", next);
            localStorage.setItem("wht_theme", next);
            updateIcon();
        });
    }

    document.querySelectorAll(".copy-btn").forEach(function (button) {
        var copyLabel = i18n.copyBtn || "Copy";
        var copiedLabel = i18n.copiedBtn || "Copied!";
        button.addEventListener("click", function () {
            var targetId = button.getAttribute("data-copy-target");
            var input = document.getElementById(targetId);
            if (!input) return;
            input.select();
            input.setSelectionRange(0, input.value.length);
            navigator.clipboard.writeText(input.value).then(function () {
                button.textContent = copiedLabel;
                button.classList.add("copied");
                setTimeout(function () {
                    button.textContent = copyLabel;
                    button.classList.remove("copied");
                }, 1500);
            });
        });
    });
})();
