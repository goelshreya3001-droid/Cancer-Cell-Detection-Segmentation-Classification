/**
 * CoNSeP Nuclei Analysis — Main JavaScript
 * Handles all page-specific logic for the multi-page application.
 */

document.addEventListener("DOMContentLoaded", () => {

    // ── Global: Logout buttons ──────────────────────────────────
    document.querySelectorAll("#logoutBtn, #profileLogout").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.preventDefault();
            await fetch("/logout", { method: "POST" });
            window.location.href = "/";
        });
    });

    // ── Page detection & routing ────────────────────────────────
    const path = window.location.pathname;

    if (document.getElementById("loginForm"))       initLogin();
    if (document.getElementById("signupForm"))      initSignup();
    if (document.getElementById("statTotalAnalyses")) initDashboard();
    if (document.getElementById("uploadForm"))      initAnalyze();
    if (typeof window.ANALYSIS_ID !== "undefined")  initResults();
    if (document.getElementById("historyBody"))     initHistory();
    if (document.getElementById("profileInfo"))     initProfile();
});


// ================================================================
//  LOGIN
// ================================================================
function initLogin() {
    const form  = document.getElementById("loginForm");
    const err   = document.getElementById("loginError");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        err.classList.add("hidden");

        const username = document.getElementById("loginUsername").value.trim();
        const password = document.getElementById("loginPassword").value;

        if (!username || !password) {
            showAlert(err, "Please fill in all fields.");
            return;
        }

        try {
            const r = await fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
            const data = await r.json();

            if (r.ok && data.success) {
                window.location.href = "/dashboard";
            } else {
                showAlert(err, data.error || "Login failed.");
            }
        } catch {
            showAlert(err, "Network error. Please try again.");
        }
    });
}


// ================================================================
//  SIGNUP
// ================================================================
function initSignup() {
    const form    = document.getElementById("signupForm");
    const err     = document.getElementById("signupError");
    const success = document.getElementById("signupSuccess");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        err.classList.add("hidden");
        success.classList.add("hidden");

        const username         = document.getElementById("signupUsername").value.trim();
        const email            = document.getElementById("signupEmail").value.trim();
        const password         = document.getElementById("signupPassword").value;
        const confirm_password = document.getElementById("signupConfirm").value;

        if (!username || !password || !confirm_password) {
            showAlert(err, "Please fill in all required fields.");
            return;
        }
        if (password !== confirm_password) {
            showAlert(err, "Passwords do not match.");
            return;
        }

        try {
            const r = await fetch("/signup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, email, password, confirm_password })
            });
            const data = await r.json();

            if (r.ok && data.success) {
                showAlert(success, "Account created! Redirecting to login...");
                setTimeout(() => { window.location.href = "/login"; }, 1500);
            } else {
                showAlert(err, data.error || "Signup failed.");
            }
        } catch {
            showAlert(err, "Network error. Please try again.");
        }
    });
}


// ================================================================
//  DASHBOARD
// ================================================================
function initDashboard() {
    fetch("/history")
        .then(r => {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(data => {
            if (!data || !data.success) return;

            const analyses = data.analyses || [];
            document.getElementById("statTotalAnalyses").textContent = analyses.length;

            let totalNuclei = 0, totalMalignant = 0;
            analyses.forEach(a => {
                totalNuclei   += a.total_nuclei || 0;
                totalMalignant += a.malignant_count || 0;
            });
            document.getElementById("statTotalNuclei").textContent = totalNuclei;
            document.getElementById("statMalignant").textContent = totalMalignant;

            // Recent list (latest 5)
            const container = document.getElementById("recentAnalyses");
            if (analyses.length === 0) return;

            container.innerHTML = "";
            analyses.slice(0, 5).forEach(a => {
                const div = document.createElement("div");
                div.className = "recent-item";
                const dateStr = new Date(a.created_at).toLocaleDateString();
                div.innerHTML = `
                    <span>${a.original_filename} — ${dateStr}</span>
                    <a href="/results/${a.id}" class="btn btn-outline" style="padding:.3rem .7rem;font-size:.8rem;">View</a>
                `;
                container.appendChild(div);
            });
        })
        .catch(() => {});
}


// ================================================================
//  ANALYZE (Image Upload)
// ================================================================
function initAnalyze() {
    const dropZone   = document.getElementById("dropZone");
    const fileInput  = document.getElementById("fileInput");
    const previewBox = document.getElementById("previewContainer");
    const preview    = document.getElementById("imagePreview");
    const clearBtn   = document.getElementById("clearBtn");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const form       = document.getElementById("uploadForm");
    const loading    = document.getElementById("loadingState");
    const errBox     = document.getElementById("uploadError");

    let currentFile = null;

    dropZone.addEventListener("click", () => fileInput.click());

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drop-zone--over");
    });
    ["dragleave", "dragend"].forEach(t =>
        dropZone.addEventListener(t, () => dropZone.classList.remove("drop-zone--over"))
    );
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drop-zone--over");
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });

    function handleFile(file) {
        errBox.classList.add("hidden");
        const valid = ["image/jpeg","image/png","image/tiff","image/bmp"];
        if (!valid.includes(file.type) && !file.name.match(/\.(tif|tiff)$/i)) {
            showAlert(errBox, "Please upload a valid image (PNG, JPG, TIFF, BMP).");
            return;
        }
        currentFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.src = e.target.result;
            dropZone.classList.add("hidden");
            previewBox.classList.remove("hidden");
            analyzeBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    clearBtn.addEventListener("click", () => {
        currentFile = null;
        fileInput.value = "";
        previewBox.classList.add("hidden");
        dropZone.classList.remove("hidden");
        analyzeBtn.disabled = true;
        errBox.classList.add("hidden");
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!currentFile) { showAlert(errBox, "Please select a file first."); return; }

        errBox.classList.add("hidden");
        loading.classList.remove("hidden");
        analyzeBtn.disabled = true;

        const fd = new FormData();
        fd.append("image", currentFile);

        try {
            const r = await fetch("/predict", { method: "POST", body: fd });
            if (r.status === 401) { window.location.href = "/login"; return; }
            const data = await r.json();

            if (r.ok && data.success && data.analysis_id) {
                window.location.href = "/results/" + data.analysis_id;
            } else {
                showAlert(errBox, data.error || "Analysis failed.");
                loading.classList.add("hidden");
                analyzeBtn.disabled = false;
            }
        } catch {
            showAlert(errBox, "Network error. Please try again.");
            loading.classList.add("hidden");
            analyzeBtn.disabled = false;
        }
    });
}


// ================================================================
//  RESULTS
// ================================================================
function initResults() {
    const id       = window.ANALYSIS_ID;
    const loadEl   = document.getElementById("resultsLoading");
    const errEl    = document.getElementById("resultsError");
    const content  = document.getElementById("resultsContent");

    fetch("/analysis/" + id)
        .then(r => {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(data => {
            loadEl.classList.add("hidden");
            if (!data || !data.success) {
                showAlert(errEl, data ? data.error : "Analysis not found.");
                return;
            }

            document.getElementById("resTotal").textContent        = data.total_nuclei;
            document.getElementById("resMalignant").textContent    = data.malignant_count;
            document.getElementById("resInflammatory").textContent = data.inflammatory_count;
            document.getElementById("resHealthy").textContent      = data.healthy_count;
            document.getElementById("resStromal").textContent      = data.stromal_count;
            document.getElementById("resOther").textContent        = data.other_count;
            document.getElementById("resTime").textContent         = "Processing time: " + (data.processing_time_sec || 0).toFixed(2) + "s";

            const ts = Date.now();
            document.getElementById("resOrigImg").src    = data.upload_url + "?t=" + ts;
            document.getElementById("resMaskImg").src    = data.mask_url   + "?t=" + ts;
            document.getElementById("resOverlayImg").src = data.overlay_url + "?t=" + ts;

            content.classList.remove("hidden");
        })
        .catch(() => {
            loadEl.classList.add("hidden");
            showAlert(errEl, "Failed to load analysis.");
        });
}


// ================================================================
//  HISTORY
// ================================================================
function initHistory() {
    const loadEl  = document.getElementById("historyLoading");
    const errEl   = document.getElementById("historyError");
    const emptyEl = document.getElementById("historyEmpty");
    const tableEl = document.getElementById("historyTable");
    const tbody   = document.getElementById("historyBody");

    fetch("/history")
        .then(r => {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(data => {
            loadEl.classList.add("hidden");
            if (!data || !data.success) {
                showAlert(errEl, "Failed to load history.");
                return;
            }

            const analyses = data.analyses || [];
            if (analyses.length === 0) {
                emptyEl.classList.remove("hidden");
                return;
            }

            tbody.innerHTML = "";
            analyses.forEach(a => {
                const tr = document.createElement("tr");
                const dateStr = new Date(a.created_at).toLocaleString();
                tr.innerHTML = `
                    <td>${dateStr}</td>
                    <td>${a.original_filename}</td>
                    <td>${a.total_nuclei}</td>
                    <td style="color:var(--danger);font-weight:600;">${a.malignant_count}</td>
                    <td>${(a.processing_time_sec || 0).toFixed(2)}</td>
                    <td><a href="/results/${a.id}" class="btn btn-outline" style="padding:.25rem .6rem;font-size:.8rem;">View</a></td>
                `;
                tbody.appendChild(tr);
            });
            tableEl.classList.remove("hidden");
        })
        .catch(() => {
            loadEl.classList.add("hidden");
            showAlert(errEl, "Failed to load history.");
        });
}


// ================================================================
//  PROFILE
// ================================================================
function initProfile() {
    const loadEl = document.getElementById("profileLoading");
    const infoEl = document.getElementById("profileInfo");

    fetch("/me")
        .then(r => {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(data => {
            loadEl.classList.add("hidden");
            if (!data || !data.success) return;

            document.getElementById("profileUsername").textContent = data.username || "–";
            document.getElementById("profileEmail").textContent    = data.email || "Not provided";
            document.getElementById("profileCreated").textContent  = data.created_at ? new Date(data.created_at).toLocaleDateString() : "–";
            infoEl.classList.remove("hidden");
        })
        .catch(() => { loadEl.classList.add("hidden"); });
}


// ================================================================
//  Utility
// ================================================================
function showAlert(el, msg) {
    el.textContent = msg;
    el.classList.remove("hidden");
}
