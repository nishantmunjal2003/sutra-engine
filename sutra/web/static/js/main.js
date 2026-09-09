/**
 * main.js — Sūtra Press Manuscripts Dashboard
 * Handles authentication, project list, drag & drop DOCX upload, and navigation.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Safe event listener helper
    function safeOn(el, event, handler) {
        if (el) el.addEventListener(event, handler);
    }

    // DOM Elements
    const loginSection          = document.getElementById("loginSection");
    const loginForm             = document.getElementById("loginForm");
    const loginUsername         = document.getElementById("loginUsername");
    const loginPassword         = document.getElementById("loginPassword");
    const loginSubmitBtn        = document.getElementById("loginSubmitBtn");

    const appContainer          = document.getElementById("appContainer");
    const headerUsername        = document.getElementById("headerUsername");
    const logoutBtn             = document.getElementById("logoutBtn");
    const navAdmin              = document.getElementById("navAdmin");

    const projectsCount         = document.getElementById("projectsCount");
    const projectsCountBadge    = document.getElementById("projectsCountBadge");
    const dashboardProjectsList = document.getElementById("dashboardProjectsList");

    const uploadForm            = document.getElementById("uploadForm");
    const dropZone              = document.getElementById("dropZone");
    const fileInput             = document.getElementById("fileInput");
    const fileInfo              = document.getElementById("fileInfo");
    const fileNameEl            = document.getElementById("fileName");
    const fileSizeEl            = document.getElementById("fileSize");
    const removeFileBtn         = document.getElementById("removeFileBtn");
    const submitBtn             = document.getElementById("submitBtn");

    const quickUpload           = document.getElementById("quickUpload");
    const quickJournal          = document.getElementById("quickJournal");
    const quickGenerate         = document.getElementById("quickGenerate");

    let selectedFile = null;

    // ----------------------------------------------------
    // Format File Size Helper
    // ----------------------------------------------------
    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    // ----------------------------------------------------
    // Drag & Drop / File Selection
    // ----------------------------------------------------
    function handleFileSelect(file) {
        if (!file.name.endsWith(".docx")) {
            alert("Only Microsoft Word (.docx) manuscripts are supported.");
            return;
        }
        selectedFile = file;
        fileNameEl.textContent = file.name;
        fileSizeEl.textContent = formatBytes(file.size);

        dropZone.classList.add("hidden");
        fileInfo.classList.remove("hidden");
        submitBtn.removeAttribute("disabled");
    }

    if (dropZone) {
        dropZone.addEventListener("click", () => fileInput.click());

        ["dragover", "dragenter"].forEach(ev => {
            dropZone.addEventListener(ev, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(ev => {
            dropZone.addEventListener(ev, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove("dragover");
            });
        });

        dropZone.addEventListener("drop", (e) => {
            const files = e.dataTransfer?.files;
            if (files && files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }

    if (removeFileBtn) {
        removeFileBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            selectedFile = null;
            if (fileInput) fileInput.value = "";
            fileInfo.classList.add("hidden");
            dropZone.classList.remove("hidden");
            submitBtn.setAttribute("disabled", "true");
        });
    }

    // ----------------------------------------------------
    // Upload Manuscript & Open in Dedicated Editor Page
    // ----------------------------------------------------
    if (uploadForm) {
        uploadForm.addEventListener("submit", (e) => {
            e.preventDefault();
            if (!selectedFile) return;

            submitBtn.setAttribute("disabled", "true");
            submitBtn.textContent = "Uploading & Parsing…";

            const formData = new FormData();
            formData.append("file", selectedFile);

            fetch("/upload", {
                method: "POST",
                body: formData
            })
            .then(res => {
                if (!res.ok) throw new Error("Manuscript parsing error.");
                return res.json();
            })
            .then(data => {
                // Navigate directly to the dedicated editor page
                window.location.href = `/editor/${data.id}`;
            })
            .catch(err => {
                alert(err.message || "Failed to establish server connection.");
                submitBtn.removeAttribute("disabled");
                submitBtn.textContent = "Upload & Parse Structure";
            });
        });
    }

    // ----------------------------------------------------
    // Quick Start Tiles
    // ----------------------------------------------------
    if (quickUpload) {
        quickUpload.addEventListener("click", () => {
            const uploadSection = document.getElementById("uploadSection");
            if (uploadSection) uploadSection.scrollIntoView({ behavior: "smooth" });
        });
    }
    if (quickJournal) {
        quickJournal.addEventListener("click", () => {
            window.location.href = "/journals";
        });
    }
    if (quickGenerate) {
        quickGenerate.addEventListener("click", () => {
            if (dashboardProjectsList) dashboardProjectsList.scrollIntoView({ behavior: "smooth" });
        });
    }

    // ----------------------------------------------------
    // Dashboard Projects List Logic
    // ----------------------------------------------------
    function loadDashboardProjects() {
        fetch("/projects")
            .then(res => res.json())
            .then(projects => {
                if (projectsCount) projectsCount.textContent = projects.length;
                if (projectsCountBadge) projectsCountBadge.textContent = `${projects.length} project${projects.length !== 1 ? 's' : ''}`;
                if (!dashboardProjectsList) return;

                dashboardProjectsList.innerHTML = "";

                if (projects.length === 0) {
                    dashboardProjectsList.innerHTML = `
                        <div style="text-align: center; padding: 3rem; background: var(--bg-subtle); border: 1px solid var(--border-color); border-radius: 12px; color: var(--text-secondary);">
                            <p style="font-weight: 600; margin-bottom: 0.25rem;">No manuscripts uploaded yet</p>
                            <p style="font-size: 0.85rem;">Upload a Word (.docx) document on the right to get started.</p>
                        </div>
                    `;
                    return;
                }

                projects.forEach(p => {
                    const card = document.createElement("div");
                    card.className = "dashboard-project-card";

                    // Status badge
                    let statusBadgeHtml = `<span class="project-card-badge draft">DRAFT</span>`;
                    let runId = null;
                    if (p.history && p.history.length > 0) {
                        const lastRun = p.history[p.history.length - 1];
                        runId = lastRun.run_id;
                        if (lastRun.xml_validation_passed && lastRun.compile_passed) {
                            statusBadgeHtml = `<span class="project-card-badge pass">PASSED</span>`;
                        } else {
                            statusBadgeHtml = `<span class="project-card-badge fail">FAILED</span>`;
                        }
                    }

                    // Format date
                    let dateStr = "";
                    try {
                        const d = new Date(p.updated_at);
                        dateStr = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
                    } catch (e) {
                        dateStr = p.updated_at;
                    }

                    // Download ZIP link if run exists
                    let downloadZipHtml = "";
                    if (runId) {
                        downloadZipHtml = `
                            <a href="/project/${p.id}/download/${runId}/zip" class="btn-icon" title="Download Outputs ZIP">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 1.1rem; height: 1.1rem;">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                            </a>
                        `;
                    }

                    card.innerHTML = `
                        <div class="project-card-left">
                            <div class="project-card-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 1.25rem; height: 1.25rem;">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                            </div>
                            <div class="project-card-info">
                                <span class="project-card-title" title="${escapeHtml(p.filename)}">${escapeHtml(p.filename)}</span>
                                <div class="project-card-meta">
                                    <span class="project-card-date">Modified: ${dateStr}</span>
                                    ${statusBadgeHtml}
                                </div>
                            </div>
                        </div>
                        <div class="project-card-actions">
                            <button type="button" class="btn-primary btn-small btn-open-proj">Open</button>
                            ${downloadZipHtml}
                            <button type="button" class="btn-icon btn-delete btn-delete-proj" title="Delete Project">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 1.1rem; height: 1.1rem;">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                            </button>
                        </div>
                    `;

                    // Wire Open button -> real navigation to dedicated editor page
                    card.querySelector(".btn-open-proj").onclick = () => {
                        window.location.href = `/editor/${p.id}`;
                    };

                    // Wire Delete button
                    card.querySelector(".btn-delete-proj").onclick = () => {
                        if (confirm(`Are you sure you want to permanently delete "${p.filename}"? All review history will be lost.`)) {
                            fetch(`/project/${p.id}`, { method: "DELETE" })
                                .then(() => loadDashboardProjects())
                                .catch(() => alert("Failed to delete project."));
                        }
                    };

                    dashboardProjectsList.appendChild(card);
                });
            })
            .catch(err => {
                console.error(err);
                if (dashboardProjectsList) {
                    dashboardProjectsList.innerHTML = `<div style="text-align: center; color: var(--state-error-text); padding: 2rem;">Failed to load projects.</div>`;
                }
            });
    }

    // ----------------------------------------------------
    // User Authentication & Initialization
    // ----------------------------------------------------
    function initAuth() {
        const isLoggedIn = sessionStorage.getItem("isLoggedIn") === "true";
        if (!isLoggedIn) {
            if (loginSection) loginSection.classList.remove("hidden");
            if (appContainer) appContainer.classList.add("hidden");
        } else {
            if (loginSection) loginSection.classList.add("hidden");
            if (appContainer) appContainer.classList.remove("hidden");

            initSharedNavbar();
            loadDashboardProjects();
        }
    }

    // Login Form Submit
    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            loginSubmitBtn.setAttribute("disabled", "true");
            loginSubmitBtn.textContent = "Signing In…";

            fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: loginUsername.value,
                    password: loginPassword.value
                })
            })
            .then(res => {
                if (!res.ok) {
                    return res.json().then(data => { throw new Error(data.detail || "Authentication failed."); });
                }
                return res.json();
            })
            .then(data => {
                sessionStorage.setItem("isLoggedIn", "true");
                sessionStorage.setItem("user", JSON.stringify(data.user));
                loginUsername.value = "";
                loginPassword.value = "";
                loginSubmitBtn.removeAttribute("disabled");
                loginSubmitBtn.textContent = "Sign In";
                initAuth();
            })
            .catch(err => {
                alert(err.message);
                loginSubmitBtn.removeAttribute("disabled");
                loginSubmitBtn.textContent = "Sign In";
            });
        });
    }

    // Boot
    initAuth();
});
