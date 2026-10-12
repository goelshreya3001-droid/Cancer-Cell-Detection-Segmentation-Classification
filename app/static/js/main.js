/**
 * PathAI — Cancer Nuclei Analysis Platform
 * Main JavaScript — handles theme, navigation, and all page logic.
 */

/* ================================================================
   THEME MANAGEMENT
   ================================================================ */
(function () {
    // Read persisted preference; fall back to system preference
    var saved = localStorage.getItem("pathai-theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var theme = saved || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
})();

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("pathai-theme", theme);
}

function toggleTheme() {
    var current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "dark" ? "light" : "dark");
}

/* ================================================================
   DOM READY
   ================================================================ */
document.addEventListener("DOMContentLoaded", function () {

    // ── Theme toggle button ──────────────────────────────────────
    var themeBtn = document.getElementById("themeToggleBtn");
    if (themeBtn) {
        themeBtn.addEventListener("click", toggleTheme);
    }

    // ── Mobile hamburger ─────────────────────────────────────────
    var hamburger = document.getElementById("navHamburger");
    var mainNav   = document.getElementById("mainNav");
    if (hamburger && mainNav) {
        hamburger.addEventListener("click", function () {
            mainNav.classList.toggle("is-open");
            var expanded = mainNav.classList.contains("is-open");
            hamburger.setAttribute("aria-expanded", expanded);
        });
        // Close on outside click
        document.addEventListener("click", function (e) {
            if (!hamburger.contains(e.target) && !mainNav.contains(e.target)) {
                mainNav.classList.remove("is-open");
                hamburger.setAttribute("aria-expanded", "false");
            }
        });
    }

    // ── Active nav link ──────────────────────────────────────────
    var currentPath = window.location.pathname;
    document.querySelectorAll(".main-nav a[data-nav]").forEach(function (link) {
        var href = link.getAttribute("href");
        if (href && (currentPath === href ||
            (href !== "/" && currentPath.startsWith(href)))) {
            link.classList.add("active");
        }
    });

    // ── Logout buttons ───────────────────────────────────────────
    document.querySelectorAll(".js-logout").forEach(function (btn) {
        btn.addEventListener("click", async function (e) {
            e.preventDefault();
            try {
                await fetch("/logout", { method: "POST" });
            } catch (_) {}
            window.location.href = "/";
        });
    });

    // ── Page routing ─────────────────────────────────────────────
    if (document.getElementById("loginForm"))          initLogin();
    if (document.getElementById("signupForm"))         initSignup();
    if (document.getElementById("statTotalAnalyses"))  initDashboard();
    if (document.getElementById("uploadForm"))         initAnalyze();
    if (typeof window.ANALYSIS_ID !== "undefined")     initResults();
    if (document.getElementById("historyBody"))        initHistory();
    if (document.getElementById("profileInfo"))        initProfile();
});


/* ================================================================
   UTILITY HELPERS
   ================================================================ */
function showAlert(el, msg, type) {
    if (!el) return;
    type = type || "danger";
    var icon = type === "danger" ? "✕" : type === "success" ? "✓" : "ℹ";
    el.innerHTML =
        '<span class="alert-icon">' + icon + '</span>' +
        '<span>' + escapeHtml(msg) + '</span>';
    el.className = "alert alert-" + type;
    el.classList.remove("hidden");
}

function hideAlert(el) {
    if (el) el.classList.add("hidden");
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function setButtonLoading(btn, isLoading, originalText) {
    if (!btn) return;
    if (isLoading) {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.textContent = "Please wait…";
    } else {
        btn.disabled = false;
        btn.textContent = originalText || btn.dataset.originalText || btn.textContent;
    }
}

function validateEmail(email) {
    // RFC-5322 simplified, good enough for frontend gating
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}


/* ================================================================
   LOGIN
   ================================================================ */
function initLogin() {
    var form    = document.getElementById("loginForm");
    var errEl   = document.getElementById("loginError");
    var submitBtn = form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (e) {
        e.preventDefault();
        hideAlert(errEl);

        var username = document.getElementById("loginUsername").value.trim();
        var password = document.getElementById("loginPassword").value;

        if (!username || !password) {
            showAlert(errEl, "Please fill in all fields.");
            return;
        }

        var originalText = submitBtn.textContent;
        setButtonLoading(submitBtn, true);

        try {
            var r = await fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: username, password: password })
            });
            var data = await r.json();

            if (r.ok && data.success) {
                window.location.href = "/dashboard";
            } else {
                showAlert(errEl, data.error || "Login failed. Check your credentials.");
                setButtonLoading(submitBtn, false, originalText);
            }
        } catch (_) {
            showAlert(errEl, "Network error. Please try again.");
            setButtonLoading(submitBtn, false, originalText);
        }
    });
}


/* ================================================================
   SIGNUP
   ================================================================ */
function initSignup() {
    var form       = document.getElementById("signupForm");
    var errEl      = document.getElementById("signupError");
    var successEl  = document.getElementById("signupSuccess");
    var submitBtn  = form.querySelector('[type="submit"]');
    var emailInput = document.getElementById("signupEmail");

    // Live email validation feedback
    if (emailInput) {
        emailInput.addEventListener("blur", function () {
            var val = emailInput.value.trim();
            if (val && !validateEmail(val)) {
                emailInput.classList.add("is-invalid");
                var hint = emailInput.nextElementSibling;
                if (hint && hint.classList.contains("form-error")) {
                    hint.textContent = "Please enter a valid email address.";
                    hint.classList.add("visible");
                }
            } else {
                emailInput.classList.remove("is-invalid");
                var hint2 = emailInput.nextElementSibling;
                if (hint2 && hint2.classList.contains("form-error")) {
                    hint2.classList.remove("visible");
                }
            }
        });
        emailInput.addEventListener("input", function () {
            emailInput.classList.remove("is-invalid");
            var hint = emailInput.nextElementSibling;
            if (hint && hint.classList.contains("form-error")) {
                hint.classList.remove("visible");
            }
        });
    }

    form.addEventListener("submit", async function (e) {
        e.preventDefault();
        hideAlert(errEl);
        hideAlert(successEl);

        var username = document.getElementById("signupUsername").value.trim();
        var email    = emailInput ? emailInput.value.trim().toLowerCase() : "";
        var password = document.getElementById("signupPassword").value;
        var confirm  = document.getElementById("signupConfirm").value;

        // Frontend validation
        if (!username || !email || !password || !confirm) {
            showAlert(errEl, "All fields are required.");
            return;
        }
        if (username.length < 3) {
            showAlert(errEl, "Username must be at least 3 characters.");
            return;
        }
        if (!validateEmail(email)) {
            showAlert(errEl, "Please enter a valid email address.");
            if (emailInput) emailInput.classList.add("is-invalid");
            return;
        }
        if (password.length < 4) {
            showAlert(errEl, "Password must be at least 4 characters.");
            return;
        }
        if (password !== confirm) {
            showAlert(errEl, "Passwords do not match.");
            return;
        }

        var originalText = submitBtn.textContent;
        setButtonLoading(submitBtn, true);

        try {
            var r = await fetch("/signup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: username,
                    email: email,
                    password: password,
                    confirm_password: confirm
                })
            });
            var data = await r.json();

            if (r.ok && data.success) {
                showAlert(successEl, "Account created successfully! Redirecting to login…", "success");
                form.reset();
                setTimeout(function () { window.location.href = "/login"; }, 1800);
            } else {
                showAlert(errEl, data.error || "Registration failed. Please try again.");
                setButtonLoading(submitBtn, false, originalText);
            }
        } catch (_) {
            showAlert(errEl, "Network error. Please try again.");
            setButtonLoading(submitBtn, false, originalText);
        }
    });
}


/* ================================================================
   DASHBOARD
   ================================================================ */
function initDashboard() {
    fetch("/history")
        .then(function (r) {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(function (data) {
            if (!data || !data.success) return;

            var analyses = data.analyses || [];
            var el = document.getElementById("statTotalAnalyses");
            if (el) el.textContent = analyses.length;

            var totalNuclei = 0, totalMalignant = 0;
            analyses.forEach(function (a) {
                totalNuclei    += a.total_nuclei || 0;
                totalMalignant += a.malignant_count || 0;
            });

            var elN = document.getElementById("statTotalNuclei");
            if (elN) elN.textContent = totalNuclei.toLocaleString();
            var elM = document.getElementById("statMalignant");
            if (elM) elM.textContent = totalMalignant.toLocaleString();

            var container = document.getElementById("recentAnalyses");
            if (!container) return;

            if (analyses.length === 0) {
                container.innerHTML =
                    '<div class="empty-state">' +
                    '<div class="empty-state-icon">🔬</div>' +
                    '<div class="empty-state-title">No analyses yet</div>' +
                    '<div class="empty-state-desc">Upload a histopathology image to get started.</div>' +
                    '<a href="/analyze" class="btn btn-primary btn-sm">New Analysis</a>' +
                    '</div>';
                return;
            }

            container.innerHTML = "";
            analyses.slice(0, 5).forEach(function (a) {
                var div = document.createElement("div");
                div.className = "recent-item";
                var date = a.created_at
                    ? new Date(a.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
                    : "Unknown date";
                var pct = a.total_nuclei > 0
                    ? Math.round((a.malignant_count / a.total_nuclei) * 100)
                    : 0;
                div.innerHTML =
                    '<div class="recent-item-info">' +
                    '<div class="recent-item-name">' + escapeHtml(a.original_filename) + '</div>' +
                    '<div class="recent-item-meta">' + date + ' &nbsp;·&nbsp; ' +
                    a.total_nuclei + ' nuclei &nbsp;·&nbsp; ' +
                    '<span style="color:var(--clr-danger);">' + a.malignant_count + ' malignant (' + pct + '%)</span>' +
                    '</div>' +
                    '</div>' +
                    '<div class="recent-item-actions">' +
                    '<a href="/results/' + a.id + '" class="btn btn-ghost btn-sm">View</a>' +
                    '</div>';
                container.appendChild(div);
            });
        })
        .catch(function () {});
}


/* ================================================================
   ANALYZE (Image Upload)
   ================================================================ */
function initAnalyze() {
    var dropZone   = document.getElementById("dropZone");
    var fileInput  = document.getElementById("fileInput");
    var previewBox = document.getElementById("previewContainer");
    var preview    = document.getElementById("imagePreview");
    var clearBtn   = document.getElementById("clearBtn");
    var analyzeBtn = document.getElementById("analyzeBtn");
    var form       = document.getElementById("uploadForm");
    var loading    = document.getElementById("loadingState");
    var errBox     = document.getElementById("uploadError");

    var currentFile = null;

    // Click to open file picker
    dropZone.addEventListener("click", function () { fileInput.click(); });
    dropZone.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
    });

    // Drag & drop
    dropZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        dropZone.classList.add("drop-zone--over");
    });
    ["dragleave", "dragend"].forEach(function (t) {
        dropZone.addEventListener(t, function () { dropZone.classList.remove("drop-zone--over"); });
    });
    dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropZone.classList.remove("drop-zone--over");
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener("change", function (e) {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });

    function handleFile(file) {
        hideAlert(errBox);
        var allowedTypes = ["image/jpeg", "image/png", "image/tiff", "image/bmp"];
        var allowedExt   = /\.(png|jpg|jpeg|tif|tiff|bmp)$/i;
        if (!allowedTypes.includes(file.type) && !allowedExt.test(file.name)) {
            showAlert(errBox, "Please upload a valid image file (PNG, JPG, TIFF, or BMP).");
            return;
        }
        currentFile = file;
        var reader = new FileReader();
        reader.onload = function (e) {
            preview.src = e.target.result;
            dropZone.classList.add("hidden");
            previewBox.classList.remove("hidden");
            analyzeBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    clearBtn.addEventListener("click", function () {
        currentFile = null;
        fileInput.value = "";
        previewBox.classList.add("hidden");
        dropZone.classList.remove("hidden");
        analyzeBtn.disabled = true;
        hideAlert(errBox);
    });

    form.addEventListener("submit", async function (e) {
        e.preventDefault();
        if (!currentFile) { showAlert(errBox, "Please select a file first."); return; }

        hideAlert(errBox);
        loading.classList.remove("hidden");
        analyzeBtn.disabled = true;

        var fd = new FormData();
        fd.append("image", currentFile);

        try {
            var r = await fetch("/predict", { method: "POST", body: fd });
            if (r.status === 401) { window.location.href = "/login"; return; }
            var data = await r.json();

            if (r.ok && data.success && data.analysis_id) {
                window.location.href = "/results/" + data.analysis_id;
            } else {
                showAlert(errBox, data.error || "Analysis failed. Please try again.");
                loading.classList.add("hidden");
                analyzeBtn.disabled = false;
            }
        } catch (_) {
            showAlert(errBox, "Network error. Please try again.");
            loading.classList.add("hidden");
            analyzeBtn.disabled = false;
        }
    });
}


/* ================================================================
   RESULTS
   ================================================================ */
function initResults() {
    var id       = window.ANALYSIS_ID;
    var loadEl   = document.getElementById("resultsLoading");
    var errEl    = document.getElementById("resultsError");
    var content  = document.getElementById("resultsContent");

    fetch("/analysis/" + id)
        .then(function (r) {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(function (data) {
            if (loadEl) loadEl.classList.add("hidden");
            if (!data || !data.success) {
                showAlert(errEl, data ? data.error : "Analysis not found or access denied.");
                return;
            }

            setText("resTotal",        (data.total_nuclei || 0).toLocaleString());
            setText("resMalignant",    (data.malignant_count || 0).toLocaleString());
            setText("resInflammatory", (data.inflammatory_count || 0).toLocaleString());
            setText("resHealthy",      (data.healthy_count || 0).toLocaleString());
            setText("resStromal",      (data.stromal_count || 0).toLocaleString());
            setText("resOther",        (data.other_count || 0).toLocaleString());

            var timeEl = document.getElementById("resTime");
            if (timeEl) {
                timeEl.textContent = "⏱ Processed in " + ((data.processing_time_sec || 0).toFixed(2)) + " seconds";
            }

            var ts = Date.now();
            setImg("resOrigImg",    data.upload_url  + "?t=" + ts);
            setImg("resMaskImg",    data.mask_url    + "?t=" + ts);
            setImg("resOverlayImg", data.overlay_url + "?t=" + ts);

            if (content) content.classList.remove("hidden");
        })
        .catch(function () {
            if (loadEl) loadEl.classList.add("hidden");
            showAlert(errEl, "Failed to load analysis results.");
        });
}

function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setImg(id, src) {
    var el = document.getElementById(id);
    if (el) el.src = src;
}


/* ================================================================
   HISTORY
   ================================================================ */
function initHistory() {
    var loadEl  = document.getElementById("historyLoading");
    var errEl   = document.getElementById("historyError");
    var emptyEl = document.getElementById("historyEmpty");
    var tableEl = document.getElementById("historyTable");
    var tbody   = document.getElementById("historyBody");

    fetch("/history")
        .then(function (r) {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(function (data) {
            if (loadEl) loadEl.classList.add("hidden");
            if (!data || !data.success) {
                showAlert(errEl, "Failed to load analysis history.");
                return;
            }

            var analyses = data.analyses || [];
            if (analyses.length === 0) {
                if (emptyEl) emptyEl.classList.remove("hidden");
                return;
            }

            tbody.innerHTML = "";
            analyses.forEach(function (a) {
                var tr = document.createElement("tr");
                var date = a.created_at
                    ? new Date(a.created_at).toLocaleString(undefined, {
                        month: "short", day: "numeric", year: "numeric",
                        hour: "2-digit", minute: "2-digit"
                      })
                    : "–";
                tr.innerHTML =
                    '<td>' + date + '</td>' +
                    '<td class="filename-cell" title="' + escapeHtml(a.original_filename) + '">' +
                        escapeHtml(a.original_filename) + '</td>' +
                    '<td>' + (a.total_nuclei || 0).toLocaleString() + '</td>' +
                    '<td class="malignant-count">' + (a.malignant_count || 0).toLocaleString() + '</td>' +
                    '<td>' + ((a.processing_time_sec || 0).toFixed(2)) + 's</td>' +
                    '<td><a href="/results/' + a.id + '" class="btn btn-ghost btn-sm">View</a></td>';
                tbody.appendChild(tr);
            });
            if (tableEl) tableEl.classList.remove("hidden");
        })
        .catch(function () {
            if (loadEl) loadEl.classList.add("hidden");
            showAlert(errEl, "Failed to load history.");
        });
}


/* ================================================================
   PROFILE
   ================================================================ */
function initProfile() {
    var loadEl  = document.getElementById("profileLoading");
    var infoEl  = document.getElementById("profileInfo");

    fetch("/me")
        .then(function (r) {
            if (r.status === 401) { window.location.href = "/login"; return null; }
            return r.json();
        })
        .then(function (data) {
            if (loadEl) loadEl.classList.add("hidden");
            if (!data || !data.success) return;

            setText("profileUsername", data.username || "–");
            setText("profileEmail",    data.email || "Not provided");
            setText("profileCreated",  data.created_at
                ? new Date(data.created_at).toLocaleDateString(undefined,
                    { month: "long", day: "numeric", year: "numeric" })
                : "–");
            if (infoEl) infoEl.classList.remove("hidden");
        })
        .catch(function () {
            if (loadEl) loadEl.classList.add("hidden");
        });
}
