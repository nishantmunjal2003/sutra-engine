/**
 * shared.js — Sūtra Press shared utilities
 * Included on every page. Handles auth guard, navbar init, logout, helpers.
 */

// ----------------------------------------------------------------
// Auth Guard — redirect to login if not authenticated
// Call at the top of every page's DOMContentLoaded
// ----------------------------------------------------------------
function requireAuth() {
    if (!sessionStorage.getItem("isLoggedIn")) {
        window.location.href = "/";
        return false;
    }
    return true;
}

// ----------------------------------------------------------------
// Shared Navbar Initialiser
// Sets username, shows/hides admin link, wires logout button
// ----------------------------------------------------------------
function initSharedNavbar() {
    let username = "User";
    let role = "editor";
    try {
        const rawUser = sessionStorage.getItem("user");
        if (rawUser) {
            const parsed = JSON.parse(rawUser);
            username = parsed.username || username;
            role = (parsed.role || role).toLowerCase();
        } else {
            username = sessionStorage.getItem("username") || username;
            role = (sessionStorage.getItem("role") || role).toLowerCase();
        }
    } catch (e) {}

    const headerUsername = document.getElementById("headerUsername");
    const navAdmin       = document.getElementById("navAdmin");
    const logoutBtn      = document.getElementById("logoutBtn");

    if (headerUsername) headerUsername.textContent = username;

    if (navAdmin) {
        if (role === "admin") {
            navAdmin.classList.remove("hidden");
        } else {
            navAdmin.classList.add("hidden");
        }
    }

    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            sessionStorage.clear();
            window.location.href = "/";
        });
    }
}

// ----------------------------------------------------------------
// Active sidebar item highlighter
// Pass the current page key: "manuscripts" | "journals" | "admin"
// ----------------------------------------------------------------
function setActiveSidebarItem(pageKey) {
    const map = {
        manuscripts: "navManuscripts",
        journals:    "navJournals",
        admin:       "navAdmin"
    };
    Object.entries(map).forEach(([key, id]) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (key === pageKey) {
            el.classList.add("active");
        } else {
            el.classList.remove("active");
        }
    });
}

// ----------------------------------------------------------------
// Escape HTML utility
// ----------------------------------------------------------------
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ----------------------------------------------------------------
// Shared page skeleton HTML (navbar + sidebar) rendered by each page
// ----------------------------------------------------------------
function buildSharedNav({ activePage = "manuscripts", username = "", role = "editor" } = {}) {
    return ``;  // Nav is in each HTML template; this is just a no-op placeholder
}
