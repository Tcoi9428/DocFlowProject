document.addEventListener("DOMContentLoaded", function () {
    const body = document.body;
    const sidebar = document.querySelector("[data-sidebar]");
    const openButton = document.querySelector("[data-sidebar-open]");
    const closeButton = document.querySelector("[data-sidebar-close]");
    const backdrop = document.querySelector("[data-sidebar-backdrop]");
    const mobileViewport = window.matchMedia("(max-width: 1024px)");

    function setSidebarOpen(isOpen, restoreFocus = false) {
        if (!sidebar || !openButton) return;

        const shouldOpen = mobileViewport.matches && isOpen;
        body.classList.toggle("mobile-menu-open", shouldOpen);
        openButton.setAttribute("aria-expanded", String(shouldOpen));
        sidebar.setAttribute("aria-hidden", String(mobileViewport.matches && !shouldOpen));
        sidebar.inert = mobileViewport.matches && !shouldOpen;

        if (shouldOpen && closeButton) {
            closeButton.focus();
        } else if (restoreFocus) {
            openButton.focus();
        }
    }

    if (sidebar && openButton) {
        openButton.addEventListener("click", function () {
            setSidebarOpen(true);
        });
        closeButton?.addEventListener("click", function () {
            setSidebarOpen(false, true);
        });
        backdrop?.addEventListener("click", function () {
            setSidebarOpen(false, true);
        });
        sidebar.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                setSidebarOpen(false);
            });
        });
        mobileViewport.addEventListener("change", function () {
            setSidebarOpen(false);
        });
        setSidebarOpen(false);
    }

    const notificationMenu = document.querySelector(".notification-menu");
    const notificationToggle = document.querySelector(".notification-toggle");

    function setNotificationsOpen(isOpen) {
        if (!notificationMenu || !notificationToggle) return;
        notificationMenu.classList.toggle("is-open", isOpen);
        notificationToggle.setAttribute("aria-expanded", String(isOpen));
    }

    notificationToggle?.setAttribute("aria-expanded", "false");
    notificationToggle?.addEventListener("click", function (event) {
        event.stopPropagation();
        setNotificationsOpen(!notificationMenu.classList.contains("is-open"));
    });

    document.addEventListener("click", function (event) {
        if (notificationMenu && !notificationMenu.contains(event.target)) {
            setNotificationsOpen(false);
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        setNotificationsOpen(false);
        if (body.classList.contains("mobile-menu-open")) {
            setSidebarOpen(false, true);
        }
    });
});
