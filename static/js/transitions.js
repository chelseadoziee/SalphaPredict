(function () {
    function prefersReducedMotion() {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    function initPageEnter() {
        const body = document.body;
        if (!body.classList.contains("page-enter")) {
            return;
        }
        if (prefersReducedMotion()) {
            body.classList.remove("page-enter");
            return;
        }
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                body.classList.add("page-enter-active");
                body.addEventListener(
                    "transitionend",
                    (event) => {
                        if (event.target !== body || event.propertyName !== "opacity") {
                            return;
                        }
                        body.classList.remove("page-enter", "page-enter-active");
                    },
                    { once: true }
                );
            });
        });
    }

    function initRevealSections() {
        const sections = document.querySelectorAll(".reveal-section:not(.is-visible)");
        if (!sections.length) {
            return;
        }
        if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
            sections.forEach((el) => el.classList.add("is-visible"));
            return;
        }
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                });
            },
            { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
        );
        sections.forEach((el) => observer.observe(el));
    }

    document.addEventListener("DOMContentLoaded", () => {
        initPageEnter();
        initRevealSections();
    });
})();
