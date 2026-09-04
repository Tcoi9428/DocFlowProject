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

    let openSearchableSelect = null;

    document.querySelectorAll("select[data-searchable-select]").forEach(function (select) {
        const wrapper = document.createElement("div");
        wrapper.className = "searchable-select";
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        select.classList.add("searchable-select-native");

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "searchable-select-toggle";
        toggle.id = `${select.id}-control`;
        toggle.setAttribute("aria-haspopup", "listbox");
        toggle.setAttribute("aria-expanded", "false");
        wrapper.appendChild(toggle);

        const dropdown = document.createElement("div");
        dropdown.className = "searchable-select-dropdown";
        dropdown.hidden = true;
        wrapper.appendChild(dropdown);

        const search = document.createElement("input");
        search.type = "search";
        search.className = "searchable-select-search";
        search.placeholder = select.dataset.searchPlaceholder || "Поиск по списку";
        search.autocomplete = "off";
        search.setAttribute("aria-label", search.placeholder);
        dropdown.appendChild(search);

        const optionList = document.createElement("div");
        optionList.className = "searchable-select-options";
        optionList.setAttribute("role", "listbox");
        dropdown.appendChild(optionList);

        const label = document.querySelector(`label[for="${select.id}"]`);
        if (label) label.htmlFor = toggle.id;

        function selectedText() {
            return select.options[select.selectedIndex]?.text || "Выберите значение";
        }

        function updateToggle() {
            toggle.textContent = selectedText();
            toggle.classList.toggle("is-placeholder", !select.value);
        }

        function closeDropdown(restoreFocus = false) {
            dropdown.hidden = true;
            wrapper.classList.remove("is-open");
            toggle.setAttribute("aria-expanded", "false");
            if (openSearchableSelect === wrapper) openSearchableSelect = null;
            if (restoreFocus) toggle.focus();
        }

        function renderOptions() {
            const query = search.value.trim().toLocaleLowerCase("ru");
            optionList.replaceChildren();
            let visibleCount = 0;

            Array.from(select.options).forEach(function (option) {
                if (option.disabled) return;
                if (query && !option.text.toLocaleLowerCase("ru").includes(query)) return;
                visibleCount += 1;
                const optionButton = document.createElement("button");
                optionButton.type = "button";
                optionButton.className = "searchable-select-option";
                optionButton.textContent = option.text;
                optionButton.dataset.value = option.value;
                optionButton.setAttribute("role", "option");
                optionButton.setAttribute("aria-selected", String(option.value === select.value));
                if (option.value === select.value) optionButton.classList.add("is-selected");
                optionButton.addEventListener("click", function () {
                    select.value = option.value;
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                    updateToggle();
                    closeDropdown(true);
                });
                optionList.appendChild(optionButton);
            });

            if (!visibleCount) {
                const empty = document.createElement("div");
                empty.className = "searchable-select-empty";
                empty.textContent = "Ничего не найдено";
                optionList.appendChild(empty);
            }
        }

        function openDropdown() {
            if (openSearchableSelect && openSearchableSelect !== wrapper) {
                openSearchableSelect.querySelector(".searchable-select-dropdown").hidden = true;
                openSearchableSelect.classList.remove("is-open");
                openSearchableSelect.querySelector(".searchable-select-toggle").setAttribute("aria-expanded", "false");
            }
            openSearchableSelect = wrapper;
            wrapper.classList.add("is-open");
            dropdown.hidden = false;
            toggle.setAttribute("aria-expanded", "true");
            search.value = "";
            renderOptions();
            search.focus();
        }

        toggle.addEventListener("click", function () {
            if (wrapper.classList.contains("is-open")) closeDropdown();
            else openDropdown();
        });
        search.addEventListener("input", renderOptions);
        select.addEventListener("change", updateToggle);
        select.addEventListener("invalid", function () {
            wrapper.classList.add("has-error");
            toggle.focus();
        });
        wrapper.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                event.stopPropagation();
                closeDropdown(true);
            }
        });

        updateToggle();
    });

    document.addEventListener("click", function (event) {
        if (openSearchableSelect && !openSearchableSelect.contains(event.target)) {
            const dropdown = openSearchableSelect.querySelector(".searchable-select-dropdown");
            const toggle = openSearchableSelect.querySelector(".searchable-select-toggle");
            dropdown.hidden = true;
            openSearchableSelect.classList.remove("is-open");
            toggle.setAttribute("aria-expanded", "false");
            openSearchableSelect = null;
        }
    });

    document.querySelectorAll("[data-numbered-correspondence-form]").forEach(function (numberedForm) {
        const departmentSelect = numberedForm.querySelector("#id_department");
        const numberPreview = numberedForm.querySelector("[data-number-preview]");

        function updateNumberPreview() {
            if (!numberPreview) return;
            const selectedOption = departmentSelect?.options[departmentSelect.selectedIndex];
            const departmentCode = selectedOption?.text.match(/^(\d{2})\s+-/)?.[1] || "__";
            numberPreview.textContent = [
                numberPreview.dataset.kindCode,
                departmentCode,
                numberPreview.dataset.sequence,
            ].join("-");
        }

        departmentSelect?.addEventListener("change", updateNumberPreview);
        updateNumberPreview();
    });

    function setupTemplateDownload(form, requiredFields, fallbackFileName) {
        if (!form) return;
        const downloadButton = form.querySelector("[data-template-download]");
        const downloadStatus = form.querySelector("[data-template-status]");

        downloadButton?.addEventListener("click", async function () {
            const currentFormData = new FormData(form);
            const payload = new FormData();

            for (const field of requiredFields) {
                const value = String(currentFormData.get(field.name) || "").trim();
                if (!value) {
                    form.elements.namedItem(field.name)?.focus();
                    if (downloadStatus) downloadStatus.textContent = field.message;
                    return;
                }
                payload.append(field.name, value);
            }
            payload.append("csrfmiddlewaretoken", form.querySelector("[name=csrfmiddlewaretoken]").value);

            downloadButton.disabled = true;
            if (downloadStatus) downloadStatus.textContent = "Формируем бланк...";
            try {
                const response = await fetch(downloadButton.dataset.url, { method: "POST", body: payload });
                if (!response.ok) {
                    const error = await response.json().catch(function () { return {}; });
                    throw new Error(error.error || "Не удалось сформировать бланк.");
                }
                const blob = await response.blob();
                const disposition = response.headers.get("Content-Disposition") || "";
                const utfName = disposition.match(/filename\*=utf-8''([^;]+)/i);
                const plainName = disposition.match(/filename="?([^";]+)"?/i);
                const fileName = utfName ? decodeURIComponent(utfName[1]) : (plainName ? plainName[1] : fallbackFileName);
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = fileName;
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(url);
                if (downloadStatus) downloadStatus.textContent = "Бланк скачан и прикреплен в черновики.";
            } catch (error) {
                if (downloadStatus) downloadStatus.textContent = error.message;
            } finally {
                downloadButton.disabled = false;
            }
        });
    }

    setupTemplateDownload(
        document.querySelector("[data-outgoing-form]"),
        [
            { name: "department", message: "Сначала выберите подразделение." },
            { name: "subject", message: "Сначала заполните поле «Наименование»." },
            { name: "addressee", message: "Сначала заполните поле «Адресат»." },
            { name: "addressee_person", message: "Сначала заполните поле «Кому»." },
        ],
        "Исходящее письмо.docx"
    );
    setupTemplateDownload(
        document.querySelector("[data-memo-form]"),
        [
            { name: "department", message: "Сначала выберите подразделение." },
            { name: "registration_date", message: "Сначала укажите дату служебной записки." },
            { name: "subject", message: "Сначала заполните поле «Наименование»." },
            { name: "addressee_person", message: "Сначала заполните поле «Кому адресовано»." },
        ],
        "Служебная записка.docx"
    );
});
