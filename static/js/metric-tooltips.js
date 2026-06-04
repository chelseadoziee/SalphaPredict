(function () {
    function getTooltip() {
        var tooltip = document.getElementById("metric-help-floating");
        if (!tooltip) {
            tooltip = document.createElement("div");
            tooltip.id = "metric-help-floating";
            tooltip.className = "metric-help-floating";
            tooltip.setAttribute("role", "tooltip");
            tooltip.hidden = true;
            document.body.appendChild(tooltip);
        }
        return tooltip;
    }

    var activeTrigger = null;
    var tooltip = getTooltip();

    function position(trigger) {
        var rect = trigger.getBoundingClientRect();
        tooltip.style.left = rect.left + rect.width / 2 + "px";
        tooltip.style.top = rect.top - 8 + "px";
        tooltip.style.transform = "translate(-50%, -100%)";
    }

    function show(trigger) {
        var title = trigger.getAttribute("data-metric-title") || "";
        var text = trigger.getAttribute("data-metric-text") || "";
        var html = "";
        if (title) {
            html +=
                '<strong class="metric-help-floating-title">' +
                title +
                "</strong>";
        }
        if (text) {
            html +=
                '<span class="metric-help-floating-text">' + text + "</span>";
        }
        tooltip.innerHTML = html;
        tooltip.hidden = false;
        activeTrigger = trigger;
        position(trigger);
    }

    function hide() {
        tooltip.hidden = true;
        activeTrigger = null;
    }

    function findTrigger(target) {
        if (!target || !target.closest) {
            return null;
        }
        return target.closest(".metric-help-trigger[data-metric-text]");
    }

    if (!document.body.getAttribute("data-metric-tooltips-bound")) {
        document.body.setAttribute("data-metric-tooltips-bound", "1");

        document.body.addEventListener(
            "mouseover",
            function (event) {
                var trigger = findTrigger(event.target);
                if (trigger && trigger !== activeTrigger) {
                    show(trigger);
                }
            },
            true
        );

        document.body.addEventListener(
            "mouseout",
            function (event) {
                var trigger = findTrigger(event.target);
                if (!trigger || activeTrigger !== trigger) {
                    return;
                }
                var next = findTrigger(event.relatedTarget);
                if (next !== trigger) {
                    hide();
                }
            },
            true
        );

        document.body.addEventListener(
            "focusin",
            function (event) {
                var trigger = findTrigger(event.target);
                if (trigger) {
                    show(trigger);
                }
            },
            true
        );

        document.body.addEventListener(
            "focusout",
            function (event) {
                var trigger = findTrigger(event.target);
                if (trigger && activeTrigger === trigger) {
                    hide();
                }
            },
            true
        );

        window.addEventListener(
            "scroll",
            function () {
                if (activeTrigger) {
                    position(activeTrigger);
                }
            },
            true
        );

        window.addEventListener("resize", function () {
            if (activeTrigger) {
                position(activeTrigger);
            }
        });
    }
})();
