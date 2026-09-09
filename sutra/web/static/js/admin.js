/**
 * admin.js — Admin Panel Page
 * Handles: users CRUD, plans CRUD, tab switching, modals
 */

document.addEventListener("DOMContentLoaded", () => {
    if (!requireAuth()) return;

    // Admin-only guard
    let role = "";
    try {
        const rawUser = sessionStorage.getItem("user");
        if (rawUser) {
            role = (JSON.parse(rawUser).role || "").toLowerCase();
        } else {
            role = (sessionStorage.getItem("role") || "").toLowerCase();
        }
    } catch (e) {}

    if (role !== "admin") {
        window.location.href = "/";
        return;
    }

    initSharedNavbar();

    let allPlansList = [];

    // DOM refs
    const tabUsersBtn       = document.getElementById("tabUsersBtn");
    const tabPlansBtn       = document.getElementById("tabPlansBtn");
    const tabUsersContent   = document.getElementById("tabUsersContent");
    const tabPlansContent   = document.getElementById("tabPlansContent");
    const usersTableBody    = document.getElementById("usersTableBody");
    const adminPlansGrid    = document.getElementById("adminPlansGrid");
    const addUserBtn        = document.getElementById("addUserBtn");
    const addPlanBtn        = document.getElementById("addPlanBtn");

    // User modal
    const userModalOverlay  = document.getElementById("userModalOverlay");
    const userForm          = document.getElementById("userForm");
    const userFormId        = document.getElementById("userFormId");
    const userFormUsername  = document.getElementById("userFormUsername");
    const userFormEmail     = document.getElementById("userFormEmail");
    const userFormPassword  = document.getElementById("userFormPassword");
    const userFormRole      = document.getElementById("userFormRole");
    const userFormPlan      = document.getElementById("userFormPlan");
    const userFormStatus    = document.getElementById("userFormStatus");
    const closeUserModalBtn = document.getElementById("closeUserModalBtn");
    const cancelUserModalBtn= document.getElementById("cancelUserModalBtn");
    const userModalTitle    = document.getElementById("userModalTitle");

    // Plan modal
    const planModalOverlay  = document.getElementById("planModalOverlay");
    const planForm          = document.getElementById("planForm");
    const planFormId        = document.getElementById("planFormId");
    const planFormName      = document.getElementById("planFormName");
    const planFormPrice     = document.getElementById("planFormPrice");
    const planFormLimit     = document.getElementById("planFormLimit");
    const planFormFeatures  = document.getElementById("planFormFeatures");
    const closePlanModalBtn = document.getElementById("closePlanModalBtn");
    const cancelPlanModalBtn= document.getElementById("cancelPlanModalBtn");
    const planModalTitle    = document.getElementById("planModalTitle");

    // ---- Tab Switching ----
    tabUsersBtn.addEventListener("click", () => {
        tabUsersBtn.classList.add("active");
        tabPlansBtn.classList.remove("active");
        tabUsersContent.classList.remove("hidden");
        tabPlansContent.classList.add("hidden");
        loadAdminUsers();
    });
    tabPlansBtn.addEventListener("click", () => {
        tabPlansBtn.classList.add("active");
        tabUsersBtn.classList.remove("active");
        tabPlansContent.classList.remove("hidden");
        tabUsersContent.classList.add("hidden");
        loadAdminPlans();
    });

    // ---- Load Users ----
    function loadAdminUsers() {
        fetch("/admin/plans")
            .then(res => res.json())
            .then(plans => {
                allPlansList = plans;
                userFormPlan.innerHTML = plans.map(p => `<option value="${p.id}">${p.name}</option>`).join("");
                return fetch("/admin/users");
            })
            .then(res => res.json())
            .then(users => {
                usersTableBody.innerHTML = "";
                if (users.length === 0) {
                    usersTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-secondary);">No users found.</td></tr>`;
                    return;
                }
                users.forEach(u => {
                    const tr = document.createElement("tr");
                    const planName    = allPlansList.find(p => p.id === u.plan_id)?.name || u.plan_id;
                    const statusClass = u.status === "Active" ? "active" : "inactive";
                    tr.innerHTML = `
                        <td>
                            <div class="user-row-info">
                                <div class="user-avatar">${u.username.substring(0, 2)}</div>
                                <div class="user-details-text">
                                    <span class="user-name-label">${escapeHtml(u.username)}</span>
                                    <span class="user-email-label">${escapeHtml(u.email)}</span>
                                </div>
                            </div>
                        </td>
                        <td><span style="font-weight:550;">${u.role}</span></td>
                        <td><span class="projects-count" style="background:rgba(79,70,229,0.05);color:var(--brand-indigo);">${planName}</span></td>
                        <td><span class="status-indicator ${statusClass}">${u.status}</span></td>
                        <td>
                            <div style="display:flex;gap:0.5rem;">
                                <button type="button" class="btn-secondary btn-small btn-edit-user">Edit</button>
                                <button type="button" class="btn-secondary btn-small btn-delete-user" style="color:var(--state-error-text);border-color:rgba(198,40,40,0.2);">Delete</button>
                            </div>
                        </td>
                    `;
                    tr.querySelector(".btn-edit-user").onclick   = () => openUserModal(u);
                    tr.querySelector(".btn-delete-user").onclick = () => deleteUser(u.id, u.username);
                    usersTableBody.appendChild(tr);
                });
            })
            .catch(err => {
                console.error(err);
                usersTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--state-error-text);">Failed to load users.</td></tr>`;
            });
    }

    // ---- Load Plans ----
    function loadAdminPlans() {
        fetch("/admin/plans")
            .then(res => res.json())
            .then(plans => {
                allPlansList = plans;
                adminPlansGrid.innerHTML = "";
                if (plans.length === 0) {
                    adminPlansGrid.innerHTML = `<div style="text-align:center;padding:3rem;grid-column:1/-1;color:var(--text-secondary);">No subscription plans configured.</div>`;
                    return;
                }
                plans.forEach(p => {
                    const card = document.createElement("div");
                    card.className = "plan-card";
                    const featuresHtml = p.features.map(f => `<li>${escapeHtml(f)}</li>`).join("");
                    card.innerHTML = `
                        <div class="plan-header">
                            <span class="plan-title">${escapeHtml(p.name)}</span>
                            <span class="plan-price">${escapeHtml(p.price)}</span>
                            <span class="plan-limit">${escapeHtml(p.limit)}</span>
                        </div>
                        <ul class="plan-features">${featuresHtml}</ul>
                        <div class="plan-actions">
                            <button type="button" class="btn-outline btn-small btn-edit-plan" style="flex:1;">Edit Plan</button>
                            <button type="button" class="btn-outline btn-small btn-delete-plan" style="color:var(--state-error-text);border-color:rgba(198,40,40,0.2);width:2.25rem;padding:0;">✕</button>
                        </div>
                    `;
                    card.querySelector(".btn-edit-plan").onclick   = () => openPlanModal(p);
                    card.querySelector(".btn-delete-plan").onclick = () => deletePlan(p.id, p.name);
                    adminPlansGrid.appendChild(card);
                });
            })
            .catch(err => {
                console.error(err);
                adminPlansGrid.innerHTML = `<div style="text-align:center;padding:2rem;grid-column:1/-1;color:var(--state-error-text);">Failed to load plans.</div>`;
            });
    }

    // ---- User Modal ----
    function openUserModal(user = null) {
        if (user) {
            userModalTitle.textContent = "Edit User";
            userFormId.value = user.id;
            userFormUsername.value = user.username;
            userFormEmail.value = user.email;
            userFormPassword.value = user.password;
            userFormRole.value = user.role;
            userFormPlan.value = user.plan_id;
            userFormStatus.value = user.status;
            userFormUsername.setAttribute("disabled", "true");
        } else {
            userModalTitle.textContent = "Add User";
            userFormId.value = "";
            userFormUsername.value = "";
            userFormEmail.value = "";
            userFormPassword.value = "";
            userFormRole.value = "Editor";
            userFormPlan.value = allPlansList[0]?.id || "free";
            userFormStatus.value = "Active";
            userFormUsername.removeAttribute("disabled");
        }
        userModalOverlay.classList.remove("hidden");
    }

    function closeUserModal() {
        userModalOverlay.classList.add("hidden");
        userForm.reset();
    }

    addUserBtn.addEventListener("click", () => openUserModal());
    closeUserModalBtn.addEventListener("click", closeUserModal);
    cancelUserModalBtn.addEventListener("click", closeUserModal);

    userForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const id = userFormId.value;
        const payload = {
            username: userFormUsername.value,
            email:    userFormEmail.value,
            password: userFormPassword.value,
            role:     userFormRole.value,
            plan_id:  userFormPlan.value,
            status:   userFormStatus.value
        };
        fetch(id ? `/admin/users/${id}` : "/admin/users", {
            method: id ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(res => {
            if (!res.ok) return res.json().then(d => { throw new Error(d.detail || "Save failed."); });
            return res.json();
        })
        .then(() => { closeUserModal(); loadAdminUsers(); })
        .catch(err => alert(err.message));
    });

    function deleteUser(userId, username) {
        if (confirm(`Permanently delete user "${username}"?`)) {
            fetch(`/admin/users/${userId}`, { method: "DELETE" })
                .then(res => { if (!res.ok) return res.json().then(d => { throw new Error(d.detail || "Delete failed."); }); return res.json(); })
                .then(() => loadAdminUsers())
                .catch(err => alert(err.message));
        }
    }

    // ---- Plan Modal ----
    function openPlanModal(plan = null) {
        if (plan) {
            planModalTitle.textContent = "Edit Plan";
            planFormId.value       = plan.id;
            planFormName.value     = plan.name;
            planFormPrice.value    = plan.price;
            planFormLimit.value    = plan.limit;
            planFormFeatures.value = plan.features.join("\n");
        } else {
            planModalTitle.textContent = "Create Plan";
            planFormId.value = planFormName.value = planFormPrice.value = planFormLimit.value = planFormFeatures.value = "";
        }
        planModalOverlay.classList.remove("hidden");
    }

    function closePlanModal() {
        planModalOverlay.classList.add("hidden");
        planForm.reset();
    }

    addPlanBtn.addEventListener("click", () => openPlanModal());
    closePlanModalBtn.addEventListener("click", closePlanModal);
    cancelPlanModalBtn.addEventListener("click", closePlanModal);

    planForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const id       = planFormId.value;
        const features = planFormFeatures.value.split("\n").map(f => f.trim()).filter(f => f);
        const payload  = { name: planFormName.value, price: planFormPrice.value, limit: planFormLimit.value, features };

        fetch(id ? `/admin/plans/${id}` : "/admin/plans", {
            method: id ? "PUT" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(res => {
            if (!res.ok) return res.json().then(d => { throw new Error(d.detail || "Save failed."); });
            return res.json();
        })
        .then(() => { closePlanModal(); loadAdminPlans(); })
        .catch(err => alert(err.message));
    });

    function deletePlan(planId, name) {
        if (confirm(`Permanently delete plan "${name}"?`)) {
            fetch(`/admin/plans/${planId}`, { method: "DELETE" })
                .then(res => { if (!res.ok) return res.json().then(d => { throw new Error(d.detail || "Delete failed."); }); return res.json(); })
                .then(() => loadAdminPlans())
                .catch(err => alert(err.message));
        }
    }

    // ---- Boot ----
    loadAdminUsers();
});
