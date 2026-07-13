const VAPID_PUBLIC_KEY = "dummy_public_key_replace_me";

document.addEventListener("DOMContentLoaded", () => {
    checkAuth();
    
    document.getElementById("login-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;
        const errDiv = document.getElementById("login-error");
        
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({email, password})
            });
            const data = await res.json();
            if(res.ok) {
                localStorage.setItem("token", data.access_token);
                localStorage.setItem("role", data.role);
                localStorage.setItem("can_solve_captcha", data.can_solve_captcha);
                localStorage.setItem("email", email);
                checkAuth();
            } else {
                errDiv.textContent = data.detail || "Login failed";
                errDiv.classList.remove("hidden");
            }
        } catch (err) {
            errDiv.textContent = "Network error";
            errDiv.classList.remove("hidden");
        }
    });

    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js?v=2').then(function(reg) {
            console.log('Service Worker Registered!', reg);
        }).catch(function(err) {
            console.log('Service Worker registration failed: ', err);
        });
    }
});

function checkAuth() {
    const token = localStorage.getItem("token");
    const role = localStorage.getItem("role");
    const email = localStorage.getItem("email");
    
    if (token) {
        document.getElementById("login-view").classList.add("hidden");
        document.getElementById("dashboard-view").classList.remove("hidden");
        
        const userDisplay = document.getElementById("logged-in-user");
        if (userDisplay && email) {
            userDisplay.textContent = `Logged in as: ${email}`;
        }
        
        // Reset all admin UI blocks to hidden before evaluating role
        if (document.getElementById("admin-section")) document.getElementById("admin-section").classList.add("hidden");
        if (document.getElementById("super-admin-tenants-section")) document.getElementById("super-admin-tenants-section").classList.add("hidden");
        if (document.getElementById("tenant-admin-section")) document.getElementById("tenant-admin-section").classList.add("hidden");
        if (document.getElementById("terminal-section")) document.getElementById("terminal-section").classList.add("hidden");
        
        if (role === "SUPER_ADMIN") {
            document.getElementById("admin-section").classList.remove("hidden");
            document.getElementById("super-admin-tenants-section").classList.remove("hidden");
            document.getElementById("tenant-admin-section").classList.remove("hidden");
            if (document.getElementById("btn-debug")) document.getElementById("btn-debug").classList.remove("hidden");
            if (document.getElementById("terminal-section")) document.getElementById("terminal-section").classList.remove("hidden");
            loadConfig();
            loadTenants();
            loadStaff();
        } else if (role === "TENANT_ADMIN") {
            document.getElementById("tenant-admin-section").classList.remove("hidden");
            loadStaff();
            loadConfig();
        }
        if (role === "SUPER_ADMIN" || role === "TENANT_ADMIN") {
            document.getElementById("tenant-admin-section").classList.remove("hidden");
        }
        startBackgroundPolling();
    } else {
        document.getElementById("login-view").classList.remove("hidden");
        document.getElementById("dashboard-view").classList.add("hidden");
        stopBackgroundPolling();
    }
}

function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("can_solve_captcha");
    localStorage.removeItem("email");
    stopBackgroundPolling();
    checkAuth();
}

async function loadConfig() {
    const res = await fetch("/api/monitor/config", {
        headers: {"Authorization": "Bearer " + localStorage.getItem("token")}
    });
    if(res.ok) {
        const config = await res.json();
        document.getElementById("cfg-from").value = config.date_from;
        document.getElementById("cfg-to").value = config.date_to;
        document.getElementById("cfg-int").value = config.interval_minutes;
        document.getElementById("cfg-strat").value = config.captcha_strategy;
        document.getElementById("cfg-api").value = config.captcha_api_key;
        document.getElementById("cfg-active").checked = config.is_active;
        if(document.getElementById("cfg-demo")) {
            document.getElementById("cfg-demo").checked = config.is_demo || false;
        }

        updateQuickToggleUI(config.is_active);

        // Handle holiday checkboxes
        const holidaysArray = config.holidays ? config.holidays.split(',') : [];
        const checkboxes = document.querySelectorAll('#cfg-holi-container input[type="checkbox"]');
        checkboxes.forEach(cb => {
            cb.checked = holidaysArray.includes(cb.value);
        });
    }
}

async function saveConfig() {
    const checkboxes = document.querySelectorAll('#cfg-holi-container input[type="checkbox"]:checked');
    const holidaysStr = Array.from(checkboxes).map(cb => cb.value).join(',');

    const payload = {
        date_from: document.getElementById("cfg-from").value,
        date_to: document.getElementById("cfg-to").value,
        holidays: holidaysStr,
        interval_minutes: parseInt(document.getElementById("cfg-int").value),
        captcha_strategy: document.getElementById("cfg-strat").value,
        captcha_api_key: document.getElementById("cfg-api").value,
        is_active: document.getElementById("cfg-active").checked,
        is_demo: document.getElementById("cfg-demo") ? document.getElementById("cfg-demo").checked : false
    };
    
    await fetch("/api/monitor/config", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + localStorage.getItem("token")
        },
        body: JSON.stringify(payload)
    });
    alert("Global Config Saved!");
}

function urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function subscribeToPush() {
    const statusDiv = document.getElementById("sub-status");
    statusDiv.classList.add("hidden");
    
    try {
        const registration = await navigator.serviceWorker.ready;
        
        // Fetch the real VAPID Public Key from the server (Mocked here for now)
        const vapidRes = await fetch("/api/push/vapid-public-key");
        const vapidData = await vapidRes.json();
        const convertedVapidKey = urlB64ToUint8Array(vapidData.public_key);

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedVapidKey
        });

        // Send to backend
        const subData = JSON.parse(JSON.stringify(subscription));
        const payload = {
            endpoint: subData.endpoint,
            p256dh: subData.keys.p256dh,
            auth: subData.keys.auth
        };

        const res = await fetch("/api/push/subscribe", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
            },
            body: JSON.stringify(payload)
        });

        if(res.ok) {
            statusDiv.textContent = "Subscribed successfully! You will receive phone alerts.";
            statusDiv.classList.remove("hidden");
        } else {
            alert("Failed to save subscription to server.");
        }

    } catch (e) {
        console.error("Push Sub Error:", e);
        alert("Push subscription failed. Check console or site permissions.");
    }
}

async function testPushAlert() {
    try {
        const res = await fetch("/api/push/test", {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + localStorage.getItem("token")
            }
        });
        if(res.ok) {
            alert("Test alert sent to backend!");
        } else {
            alert("Failed to send test alert.");
        }
    } catch (e) {
        alert("Error: " + e);
    }
}

async function broadcastAlert() {
    const msg = document.getElementById("broadcast-msg").value || "Important update from Admin!";
    try {
        const res = await fetch("/api/push/broadcast", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
            },
            body: JSON.stringify({ message: msg })
        });
        if(res.ok) {
            const data = await res.json();
            alert(`Broadcast sent successfully to ${data.sent} device(s)!`);
            document.getElementById("broadcast-msg").value = "";
        } else {
            const err = await res.json();
            alert("Failed to broadcast: " + (err.detail || ""));
        }
    } catch (e) {
        alert("Error: " + e);
    }
}

async function addStaff() {
    const email = document.getElementById("new-user-email").value;
    const password = document.getElementById("new-user-pass").value;
    const can_solve_captcha = document.getElementById("new-staff-captcha").checked;
    const role = "STAFF";
    
    const res = await fetch("/api/users", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + localStorage.getItem("token")
        },
        body: JSON.stringify({ email, password, role, can_solve_captcha })
    });
    const statusDiv = document.getElementById("add-user-status");
    statusDiv.classList.remove("hidden");
    if (res.ok) {
        statusDiv.className = "text-sm mt-4 font-medium p-3 rounded-lg bg-green-500/10 border border-green-500/50 text-green-400";
        statusDiv.textContent = "User created successfully!";
        loadStaff();
    } else {
        const err = await res.json();
        statusDiv.className = "text-sm mt-4 font-medium p-3 rounded-lg bg-red-500/10 border border-red-500/50 text-red-400";
        statusDiv.textContent = err.detail || "Failed to create user";
    }
}

async function loadStaff() {
    try {
        const res = await fetch("/api/users", {
            headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
        });
        if (res.ok) {
            const users = await res.json();
            const tbody = document.getElementById("staff-table-body");
            tbody.innerHTML = "";
            users.forEach(u => {
                const tr = document.createElement("tr");
                tr.className = "hover:bg-slate-700/20 transition-colors";
                tr.innerHTML = `
                    <td class="px-4 py-3 text-xs text-slate-500">${u.id}</td>
                    <td class="px-4 py-3 font-medium text-white">${u.email}</td>
                    <td class="px-4 py-3">
                        <span class="px-2 py-1 bg-slate-800 text-slate-300 text-xs rounded border border-slate-700">${u.role}</span>
                    </td>
                    <td class="px-4 py-3">
                        <span class="px-2 py-1 ${u.can_solve_captcha ? 'bg-green-500/20 text-green-400 border-green-500/50' : 'bg-red-500/20 text-red-400 border-red-500/50'} text-xs rounded border">${u.can_solve_captcha ? 'Yes' : 'No'}</span>
                    </td>
                    <td class="px-4 py-3 space-x-2">
                        <button onclick="openEditUserModal(${u.id}, '${u.email}', '${u.role}', ${u.can_solve_captcha})" class="text-indigo-400 hover:text-indigo-300 transition-colors">Edit</button>
                        <button onclick="deleteStaff(${u.id})" class="text-red-400 hover:text-red-300 transition-colors">Delete</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error("Failed to load staff:", e);
    }
}

function openEditUserModal(id, email, role, can_solve_captcha) {
    document.getElementById("edit-user-id").value = id;
    document.getElementById("edit-user-email").value = email;
    document.getElementById("edit-user-password").value = "";
    document.getElementById("edit-user-captcha").checked = can_solve_captcha === true;
    
    // Only super admins can change roles. We show it if they are logged in as super admin.
    const currentUserRole = localStorage.getItem("role");
    if (currentUserRole === "SUPER_ADMIN") {
        document.getElementById("edit-user-role-group").classList.remove("hidden");
        document.getElementById("edit-user-role").value = role;
    } else {
        document.getElementById("edit-user-role-group").classList.add("hidden");
    }
    
    document.getElementById("edit-user-modal").classList.remove("hidden");
    setTimeout(() => {
        document.getElementById("edit-user-modal").querySelector('.glass-card').classList.remove("scale-95", "opacity-0");
    }, 10);
}

function closeEditUserModal() {
    document.getElementById("edit-user-modal").querySelector('.glass-card').classList.add("scale-95", "opacity-0");
    setTimeout(() => {
        document.getElementById("edit-user-modal").classList.add("hidden");
    }, 200);
}

async function updateUser() {
    const id = document.getElementById("edit-user-id").value;
    const email = document.getElementById("edit-user-email").value;
    const password = document.getElementById("edit-user-password").value;
    const role = document.getElementById("edit-user-role").value;
    const can_solve_captcha = document.getElementById("edit-user-captcha").checked;
    
    const payload = { can_solve_captcha: can_solve_captcha };
    if (email) payload.email = email;
    if (password) payload.password = password;
    if (!document.getElementById("edit-user-role-group").classList.contains("hidden")) {
        payload.role = role;
    }

    try {
        const res = await fetch(`/api/users/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
            },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            closeEditUserModal();
            loadStaff();
            alert("User updated successfully");
        } else {
            const err = await res.json();
            alert("Error: " + err.detail);
        }
    } catch (e) {
        alert("Error: " + e);
    }
}

async function deleteStaff(id) {
    if(!confirm("Are you sure you want to delete this user?")) return;
    const res = await fetch("/api/users/" + id, {
        method: "DELETE",
        headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
    });
    if (res.ok) {
        loadStaff();
    } else {
        alert("Failed to delete user");
    }
}

// --- Super Admin Tenant CRUD ---

async function loadTenants() {
    try {
        const res = await fetch("/api/tenants", {
            headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
        });
        if (res.ok) {
            const tenants = await res.json();
            const tbody = document.getElementById("tenant-table-body");
            tbody.innerHTML = "";
            tenants.forEach(t => {
                const tr = document.createElement("tr");
                tr.className = "hover:bg-slate-700/20 transition-colors";
                tr.innerHTML = `
                    <td class="px-4 py-3 text-slate-400">#${t.id}</td>
                    <td class="px-4 py-3 font-bold text-white">${t.name}</td>
                    <td class="px-4 py-3 text-slate-300">${t.admin_email}</td>
                    <td class="px-4 py-3">
                        <button onclick="toggleTenantStatus(${t.id}, ${!t.is_active})" class="px-2 py-1 rounded text-xs font-medium ${t.is_active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}">
                            ${t.is_active ? 'ACTIVE' : 'DISABLED'}
                        </button>
                    </td>
                    <td class="px-4 py-3 text-slate-500 text-xs">${new Date(t.created_at).toLocaleDateString()}</td>
                    <td class="px-4 py-3 text-right space-x-2">
                        <button onclick="openEditTenantModal(${t.id}, '${t.name}', '${t.admin_email}')" class="text-indigo-400 hover:text-indigo-300 transition-colors">Edit</button>
                        <button onclick="deleteTenant(${t.id})" class="text-red-400 hover:text-red-300 transition-colors" ${t.id === 1 ? 'disabled style="opacity:0.5;cursor:not-allowed;"' : ''}>Delete</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error("Failed to load tenants:", e);
    }
}

function openEditTenantModal(id, name, adminEmail) {
    document.getElementById("edit-tenant-id").value = id;
    document.getElementById("edit-tenant-name").value = name;
    document.getElementById("edit-tenant-email").value = adminEmail;
    document.getElementById("edit-tenant-password").value = "";
    
    document.getElementById("edit-tenant-modal").classList.remove("hidden");
    setTimeout(() => {
        document.getElementById("edit-tenant-modal").querySelector('.glass-card').classList.remove("scale-95", "opacity-0");
    }, 10);
}

function closeEditTenantModal() {
    document.getElementById("edit-tenant-modal").querySelector('.glass-card').classList.add("scale-95", "opacity-0");
    setTimeout(() => {
        document.getElementById("edit-tenant-modal").classList.add("hidden");
    }, 200);
}

async function updateTenant() {
    const id = document.getElementById("edit-tenant-id").value;
    const name = document.getElementById("edit-tenant-name").value;
    const admin_email = document.getElementById("edit-tenant-email").value;
    const admin_password = document.getElementById("edit-tenant-password").value;
    
    const payload = {};
    if (name) payload.name = name;
    if (admin_email) payload.admin_email = admin_email;
    if (admin_password) payload.admin_password = admin_password;

    try {
        const res = await fetch(`/api/tenants/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
            },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            closeEditTenantModal();
            loadTenants();
            alert("Tenant updated successfully");
        } else {
            const err = await res.json();
            alert("Error: " + err.detail);
        }
    } catch (e) {
        alert("Error: " + e);
    }
}

async function toggleTenantStatus(id, currentStatus) {
    const newStatus = !currentStatus;
    const action = newStatus ? "Activate" : "Deactivate";
    if(!confirm(`Are you sure you want to ${action} this Tenant? This will cascade to all their staff.`)) return;
    
    const res = await fetch(`/api/tenants/${id}/status`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + localStorage.getItem("token")
        },
        body: JSON.stringify({ is_active: newStatus })
    });
    
    if (res.ok) {
        loadTenants();
    } else {
        const err = await res.json();
        alert("Failed to toggle status: " + (err.detail || ""));
    }
}

async function addTenant() {
    const name = document.getElementById("new-tenant-name").value;
    const email = document.getElementById("new-tenant-email").value;
    const password = document.getElementById("new-tenant-pass").value;
    
    if(!name || !email || !password) {
        alert("Please fill in all tenant fields");
        return;
    }
    
    const res = await fetch("/api/tenants", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + localStorage.getItem("token")
        },
        body: JSON.stringify({ name: name, admin_email: email, admin_password: password })
    });
    
    const statusDiv = document.getElementById("add-tenant-status");
    statusDiv.classList.remove("hidden");
    if (res.ok) {
        statusDiv.className = "text-sm mb-4 font-medium p-3 rounded-lg bg-green-500/10 border border-green-500/50 text-green-400";
        statusDiv.textContent = "Tenant and Admin created successfully!";
        document.getElementById("new-tenant-name").value = "";
        document.getElementById("new-tenant-email").value = "";
        document.getElementById("new-tenant-pass").value = "";
        loadTenants();
    } else {
        const err = await res.json();
        statusDiv.className = "text-sm mb-4 font-medium p-3 rounded-lg bg-red-500/10 border border-red-500/50 text-red-400";
        statusDiv.textContent = err.detail || "Failed to create tenant";
    }
}

async function deleteTenant(id) {
    if(!confirm("DANGER: Are you sure you want to delete this Tenant? This will delete all their users and logs!")) return;
    const res = await fetch("/api/tenants/" + id, {
        method: "DELETE",
        headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
    });
    if (res.ok) {
        loadTenants();
    } else {
        const err = await res.json();
        alert("Failed to delete tenant: " + (err.detail || ""));
    }
}

// --- PWA Install Logic ---

let deferredPrompt;
const installModal = document.getElementById('pwa-install-modal');
const modalContent = document.getElementById('pwa-modal-content');
const btnInstall = document.getElementById('btn-pwa-install');
const btnDismiss = document.getElementById('btn-pwa-dismiss');

function showInstallModal() {
    installModal.classList.remove('hidden');
    // small delay for transition
    setTimeout(() => {
        modalContent.classList.remove('scale-95', 'opacity-0');
        modalContent.classList.add('scale-100', 'opacity-100');
    }, 10);
}

function hideInstallModal() {
    modalContent.classList.remove('scale-100', 'opacity-100');
    modalContent.classList.add('scale-95', 'opacity-0');
    setTimeout(() => {
        installModal.classList.add('hidden');
    }, 200);
}

window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing on mobile
    e.preventDefault();
    // Stash the event so it can be triggered later.
    deferredPrompt = e;
    
    // Check if the user has already dismissed it recently (optional)
    if (localStorage.getItem("pwa-dismissed") !== "true") {
        // Show our beautiful modal!
        showInstallModal();
    }
});

btnDismiss.addEventListener('click', () => {
    hideInstallModal();
    // Optional: remember they dismissed it
    localStorage.setItem("pwa-dismissed", "true");
});

btnInstall.addEventListener('click', async () => {
    hideInstallModal();
    if (deferredPrompt) {
        // Show the native install prompt
        deferredPrompt.prompt();
        // Wait for the user to respond to the prompt
        const { outcome } = await deferredPrompt.userChoice;
        console.log(`User response to the install prompt: ${outcome}`);
        // We've used the prompt, and can't use it again, discard it
        deferredPrompt = null;
    }
});

// --- Live Logs & Captcha Delegation Polling ---
let logPollInterval;
let captchaPollInterval;
let currentCaptchaSitekey = null;

function startBackgroundPolling() {
    stopBackgroundPolling();
    const role = localStorage.getItem("role");
    if (role === "SUPER_ADMIN" || role === "TENANT_ADMIN") {
        logPollInterval = setInterval(fetchLogs, 3000);
        fetchLogs();
    }
    
    // Only users with permission should poll for captchas
    const can_solve_captcha = localStorage.getItem("can_solve_captcha") === 'true';
    if (role === "SUPER_ADMIN" || can_solve_captcha) {
        captchaPollInterval = setInterval(checkPendingCaptcha, 3000);
        checkPendingCaptcha();
    }
}

function stopBackgroundPolling() {
    if (logPollInterval) clearInterval(logPollInterval);
    if (captchaPollInterval) clearInterval(captchaPollInterval);
}

async function fetchLogs() {
    try {
        const res = await fetch("/api/monitor/logs?limit=500", {
            headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
        });
        if (res.ok) {
            const logs = await res.json();
            const outputDiv = document.getElementById("terminal-output");
            if (!outputDiv) return;
            
            if (logs.length === 0) return;
            
            // Render logs safely
            outputDiv.innerHTML = logs.map(l => {
                const color = l.includes("ERROR") ? "text-red-400" : (l.includes("WARNING") ? "text-yellow-400" : "text-green-400");
                return `<div class="${color}">${l.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>`;
            }).join("");
            
            // Auto scroll to bottom
            outputDiv.scrollTop = outputDiv.scrollHeight;
        }
    } catch (e) {
        console.error("Log fetch error:", e);
    }
}

async function checkPendingCaptcha() {
    try {
        const res = await fetch("/api/captcha/pending", {
            headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.pending) {
                if (currentCaptchaSitekey !== data.sitekey) {
                    currentCaptchaSitekey = data.sitekey;
                    showCaptchaModal(data.sitekey);
                }
            } else {
                hideCaptchaModal();
                currentCaptchaSitekey = null;
            }
        }
    } catch (e) {
        console.error("Captcha poll error:", e);
    }
}

let captchaWidgetId = null;

function showCaptchaModal(sitekey) {
    const modal = document.getElementById("captcha-modal");
    if (!modal) return;
    
    modal.classList.remove("hidden");
    setTimeout(() => {
        modal.querySelector('#captcha-modal-content').classList.remove("scale-95", "opacity-0");
    }, 10);
    
    const container = document.getElementById("recaptcha-container");
    
    if (window.grecaptcha) {
        window.grecaptcha.ready(function() {
            try {
                if (captchaWidgetId !== null) {
                    window.grecaptcha.reset(captchaWidgetId);
                } else {
                    container.innerHTML = ''; // Clear any failed render garbage
                    captchaWidgetId = window.grecaptcha.render('recaptcha-container', {
                        'sitekey': sitekey,
                        'callback': onCaptchaSolved
                    });
                }
            } catch (e) {
                console.error("Failed to render recaptcha:", e);
                container.innerHTML = `<div class="text-red-500 bg-red-500/10 border border-red-500/50 p-4 rounded text-sm text-left"><b>Widget Render Error:</b><br>${e.message}<br><br><small>If you see 'Invalid site key', double check your API configuration. Ensure the domain is whitelisted in Google reCAPTCHA v2 settings.</small></div>`;
            }
        });
    } else {
        console.error("grecaptcha API not loaded!");
        container.innerHTML = `<div class="text-red-500 bg-red-500/10 border border-red-500/50 p-4 rounded text-sm text-left"><b>grecaptcha API Not Loaded!</b><br>The Google reCAPTCHA script failed to load. This could be due to:<br>- An AdBlocker blocking the script<br>- Network issues<br>- The container domain blocking external scripts</div>`;
    }
}

function hideCaptchaModal() {
    const modal = document.getElementById("captcha-modal");
    if (!modal) return;
    modal.querySelector('#captcha-modal-content').classList.add("scale-95", "opacity-0");
    setTimeout(() => {
        modal.classList.add("hidden");
    }, 200);
}

async function onCaptchaSolved(token) {
    try {
        const res = await fetch("/api/captcha/submit", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
            },
            body: JSON.stringify({ token: token })
        });
        if (res.ok) {
            hideCaptchaModal();
            currentCaptchaSitekey = null;
        } else {
            alert("Failed to submit Captcha to backend.");
        }
    } catch (e) {
        console.error("Captcha submit error:", e);
    }
}

async function cancelCaptcha() {
    try {
        const res = await fetch("/api/captcha/submit", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
            },
            body: JSON.stringify({ token: "" })
        });
        if (res.ok) {
            hideCaptchaModal();
            currentCaptchaSitekey = null;
        }
    } catch (e) {
        console.error("Captcha cancel error:", e);
    }
}

async function triggerBot() {
    try {
        const res = await fetch("/api/monitor/trigger", {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + localStorage.getItem("token")
            }
        });
        const data = await res.json();
        if (res.ok) {
            alert("Bot Triggered! Check terminal output in a few seconds.");
        } else {
            alert("Failed to trigger bot: " + (data.detail || "Unknown error"));
        }
    } catch(e) {
        alert("Network error triggering bot: " + e);
    }
}

// --- Debug Modal ---
async function openDebugModal() {
    document.getElementById("debug-modal").classList.remove("hidden");
    const debugContent = document.getElementById("debug-content");
    debugContent.textContent = "Loading database state...";
    try {
        const res = await fetch("/api/admin/debug", {
            headers: {"Authorization": "Bearer " + localStorage.getItem("token")}
        });
        if (!res.ok) throw new Error("Failed to fetch debug state");
        const data = await res.json();
        debugContent.textContent = JSON.stringify(data, null, 4);
    } catch (e) {
        debugContent.textContent = "Error: " + e.message;
    }
}

function closeDebugModal() {
    document.getElementById("debug-modal").classList.add("hidden");
}

async function quickToggleBot() {
    try {
        const res = await fetch('/api/monitor/quick-toggle', {
            method: 'POST',
            headers: {'Authorization': 'Bearer ' + localStorage.getItem('token')}
        });
        const data = await res.json();
        if (res.ok) {
            updateQuickToggleUI(data.is_active);
            if (document.getElementById('cfg-active')) {
                document.getElementById('cfg-active').checked = data.is_active;
            }
        }
    } catch (e) {
        console.error(e);
    }
}

function updateQuickToggleUI(isActive) {
    const icon = document.getElementById('quick-toggle-icon');
    const text = document.getElementById('quick-toggle-text');
    const btn = document.getElementById('btn-quick-toggle');
    if (!icon || !text || !btn) return;
    
    if (isActive) {
        icon.textContent = '??';
        text.textContent = 'Pause Bot';
        btn.classList.remove('bg-green-600', 'hover:bg-green-500');
        btn.classList.add('bg-slate-700', 'hover:bg-slate-600');
    } else {
        icon.textContent = '??';
        text.textContent = 'Resume Bot';
        btn.classList.remove('bg-slate-700', 'hover:bg-slate-600');
        btn.classList.add('bg-green-600', 'hover:bg-green-500');
    }
}
