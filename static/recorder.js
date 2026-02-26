// ── DOM References ──
const recordBtn = document.getElementById("recordBtn");
const statusText = document.getElementById("status");
const transcriptBox = document.getElementById("transcript");
const translationBox = document.getElementById("translation");
const commandResult = document.getElementById("commandResult");
const resumePreview = document.getElementById("resumePreview");
const missingBadges = document.getElementById("missingBadges");
const toast = document.getElementById("toast");

let mediaRecorder;
let audioChunks = [];
let currentMode = "dictate"; // "dictate" or "command"

// ── Mode Toggle ──
function setMode(mode) {
    currentMode = mode;
    document.querySelectorAll(".mode-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.mode === mode);
    });
    commandResult.style.display = "none";
}

// ── Toast Notification ──
function showToast(msg, duration = 3000) {
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), duration);
}

// ── Recording ──
recordBtn.addEventListener("click", async () => {
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
        await startRecording();
    } else if (mediaRecorder.state === "recording") {
        stopRecording();
    }
});

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            mediaRecorder.stream.getTracks().forEach(t => t.stop());
            await processAudio();
        };

        mediaRecorder.start(100);
        statusText.textContent = "Recording...";
        statusText.className = "recording";
        recordBtn.innerHTML = "&#9209; Stop Recording";
    } catch (err) {
        statusText.textContent = "Microphone error: " + err.message;
    }
}

function stopRecording() {
    mediaRecorder.requestData();
    mediaRecorder.stop();
    recordBtn.innerHTML = "&#127908; Start Recording";
}

async function processAudio() {
    statusText.textContent = "Processing...";
    statusText.className = "processing";

    await new Promise(r => setTimeout(r, 100));
    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });

    if (audioBlob.size === 0) {
        statusText.textContent = "Error: No audio recorded.";
        statusText.className = "";
        return;
    }

    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");

    const endpoint = currentMode === "command" ? "/voice-command" : "/transcribe";

    try {
        const resp = await fetch(endpoint, { method: "POST", body: formData });
        const data = await resp.json();

        if (data.error) {
            statusText.textContent = "Error: " + data.error;
            statusText.className = "";
            return;
        }

        transcriptBox.textContent = data.transcript || "";
        translationBox.textContent = data.translation || "";

        if (currentMode === "command" && data.message) {
            commandResult.style.display = "block";
            commandResult.textContent = data.message;
            showToast(data.message);
        } else {
            commandResult.style.display = "none";
        }

        if (data.resume) renderResume(data.resume);
        if (data.missing) renderMissing(data.missing);

        statusText.textContent = "Done!";
        statusText.className = "";

    } catch (err) {
        statusText.textContent = "Network error: " + err.message;
        statusText.className = "";
    }
}


// ── Render Resume Preview ──
function renderResume(resume) {
    if (!resume) return;

    const simpleFields = ["name", "email", "phone", "linkedin", "github", "summary"];
    const listFields = ["skills", "education", "experience", "projects"];

    let html = '<table class="resume-table">';

    // Simple fields
    for (const f of simpleFields) {
        const val = resume[f];
        html += `<tr>
            <th>${capitalize(f)}</th>
            <td>
                <div id="display-${f}">
                    ${val ? escHtml(String(val)) : '<span style="color:#94a3b8; font-style:italic">Not set</span>'}
                </div>
                <div id="edit-${f}" style="display:none">
                    ${f === "summary"
                        ? `<textarea class="edit-input" id="input-${f}">${val || ""}</textarea>`
                        : `<input class="edit-input" id="input-${f}" value="${escAttr(val || "")}" />`}
                    <div class="field-actions">
                        <button class="btn btn-primary btn-sm" onclick="saveField('${f}')">Save</button>
                        <button class="btn btn-outline btn-sm" onclick="cancelEdit('${f}')">Cancel</button>
                    </div>
                </div>
                <div class="field-actions" id="actions-${f}">
                    <button class="btn btn-outline btn-sm" onclick="startEdit('${f}')">Edit</button>
                    ${val ? `<button class="btn btn-danger btn-sm" onclick="deleteField('${f}')">Delete</button>` : ""}
                </div>
            </td>
        </tr>`;
    }

    // Skills
    html += `<tr><th>Skills</th><td>`;
    if (resume.skills && resume.skills.length > 0) {
        html += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px">';
        resume.skills.forEach((s, i) => {
            html += `<span style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:20px;padding:3px 12px;font-size:0.85rem;">
                ${escHtml(s)}
                <span style="cursor:pointer;color:#ef4444;margin-left:4px;" onclick="deleteListItem('skills',${i})">&times;</span>
            </span>`;
        });
        html += '</div>';
    }
    html += `<div id="edit-skills" style="display:none;">
        <input class="edit-input" id="input-skills" placeholder="Enter skill" />
        <div class="field-actions">
            <button class="btn btn-primary btn-sm" onclick="addSkill()">Add</button>
            <button class="btn btn-outline btn-sm" onclick="document.getElementById('edit-skills').style.display='none'">Cancel</button>
        </div>
    </div>
    <button class="btn btn-outline btn-sm" onclick="document.getElementById('edit-skills').style.display='block'">+ Add Skill</button>
    </td></tr>`;

    // Experience
    html += `<tr><th>Experience</th><td>`;
    if (resume.experience && resume.experience.length > 0) {
        resume.experience.forEach((exp, i) => {
            html += `<div class="list-item">
                <div>
                    <strong>${escHtml(exp.role || "")}</strong> at ${escHtml(exp.company || "")}
                    <span style="color:var(--muted);font-size:0.85rem;"> (${escHtml(exp.duration || "")})</span>
                    ${exp.bullets ? "<ul style='margin:4px 0 0 18px;font-size:0.88rem;color:#475569'>" +
                        exp.bullets.map(b => `<li>${escHtml(b)}</li>`).join("") + "</ul>" : ""}
                </div>
                <button class="btn btn-danger btn-sm" onclick="deleteListItem('experience',${i})">&times;</button>
            </div>`;
        });
    }
    html += `<button class="btn btn-outline btn-sm" onclick="addExperiencePrompt()">+ Add Experience</button></td></tr>`;

    // Education
    html += `<tr><th>Education</th><td>`;
    if (resume.education && resume.education.length > 0) {
        resume.education.forEach((edu, i) => {
            html += `<div class="list-item">
                <div><strong>${escHtml(edu.degree || "")}</strong> - ${escHtml(edu.institution || "")} <span style="color:var(--muted);font-size:0.85rem;">(${escHtml(edu.year || "")})</span></div>
                <button class="btn btn-danger btn-sm" onclick="deleteListItem('education',${i})">&times;</button>
            </div>`;
        });
    }
    html += `<button class="btn btn-outline btn-sm" onclick="addEducationPrompt()">+ Add Education</button></td></tr>`;

    // Projects
    html += `<tr><th>Projects</th><td>`;
    if (resume.projects && resume.projects.length > 0) {
        resume.projects.forEach((proj, i) => {
            html += `<div class="list-item">
                <div>
                    <strong>${escHtml(proj.name || "")}</strong>
                    <div style="font-size:0.88rem;color:#475569;">${escHtml(proj.description || "")}</div>
                    ${proj.tech_stack ? '<div style="margin-top:4px;">' +
                        proj.tech_stack.map(t => `<span style="background:#eff6ff;color:#2563eb;padding:2px 8px;border-radius:4px;font-size:0.78rem;margin-right:4px;">${escHtml(t)}</span>`).join("") +
                        "</div>" : ""}
                </div>
                <button class="btn btn-danger btn-sm" onclick="deleteListItem('projects',${i})">&times;</button>
            </div>`;
        });
    }
    html += `<button class="btn btn-outline btn-sm" onclick="addProjectPrompt()">+ Add Project</button></td></tr>`;

    html += '</table>';
    resumePreview.innerHTML = html;
}

function renderMissing(fields) {
    if (!fields || fields.length === 0) {
        missingBadges.innerHTML = '';
        return;
    }
    missingBadges.innerHTML = fields.map(f =>
        `<span class="missing-badge">${capitalize(f)}</span>`
    ).join("");
}


// ── Edit / Delete Actions ──
function startEdit(field) {
    document.getElementById("display-" + field).style.display = "none";
    document.getElementById("actions-" + field).style.display = "none";
    document.getElementById("edit-" + field).style.display = "block";
}

function cancelEdit(field) {
    document.getElementById("display-" + field).style.display = "block";
    document.getElementById("actions-" + field).style.display = "flex";
    document.getElementById("edit-" + field).style.display = "none";
}

async function saveField(field) {
    const input = document.getElementById("input-" + field);
    const value = input.value.trim();

    const resp = await fetch("/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field, value: value || null }),
    });
    const data = await resp.json();
    if (data.resume) renderResume(data.resume);
    showToast(`Updated "${field}"`);
}

async function deleteField(field) {
    if (!confirm(`Delete "${field}"?`)) return;
    const resp = await fetch("/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field }),
    });
    const data = await resp.json();
    if (data.resume) renderResume(data.resume);
    showToast(`Deleted "${field}"`);
}

async function deleteListItem(field, index) {
    const resp = await fetch("/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field, index }),
    });
    const data = await resp.json();
    if (data.resume) renderResume(data.resume);
    showToast(`Removed item from "${field}"`);
}

async function addSkill() {
    const input = document.getElementById("input-skills");
    const skill = input.value.trim();
    if (!skill) return;

    const resp = await fetch("/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field: "skills", value: [...(currentResumeSkills || []), skill] }),
    });
    const data = await resp.json();
    if (data.resume) {
        renderResume(data.resume);
        currentResumeSkills = data.resume.skills;
    }
    input.value = "";
    showToast(`Added skill "${skill}"`);
}
let currentResumeSkills = [];

function addExperiencePrompt() {
    const role = prompt("Role/Title:");
    if (!role) return;
    const company = prompt("Company:");
    const duration = prompt("Duration (e.g. 2023-2024):");
    const bulletsStr = prompt("Key achievements (comma-separated):");
    const bullets = bulletsStr ? bulletsStr.split(",").map(b => b.trim()) : [];

    addListItem("experience", { role, company, duration, bullets });
}

function addEducationPrompt() {
    const degree = prompt("Degree:");
    if (!degree) return;
    const institution = prompt("Institution:");
    const year = prompt("Year:");

    addListItem("education", { degree, institution, year });
}

function addProjectPrompt() {
    const name = prompt("Project name:");
    if (!name) return;
    const description = prompt("Description:");
    const techStr = prompt("Technologies (comma-separated):");
    const tech_stack = techStr ? techStr.split(",").map(t => t.trim()) : [];

    addListItem("projects", { name, description, tech_stack });
}

async function addListItem(field, item) {
    // Get current state first
    const stateResp = await fetch("/state");
    const stateData = await stateResp.json();
    const current = stateData.resume[field] || [];
    current.push(item);

    const resp = await fetch("/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field, value: current }),
    });
    const data = await resp.json();
    if (data.resume) renderResume(data.resume);
    showToast(`Added to "${field}"`);
}


// ── Professionalize ──
async function doProfessionalize() {
    showToast("Professionalizing resume content...", 5000);
    try {
        const resp = await fetch("/professionalize", { method: "POST" });
        const data = await resp.json();
        if (data.error) {
            showToast("Error: " + data.error, 4000);
            return;
        }
        if (data.resume) renderResume(data.resume);
        showToast(data.message || "Done!");
    } catch (err) {
        showToast("Network error: " + err.message);
    }
}


// ── Reset ──
async function resetResume() {
    // Reset all fields to null/[]
    const fields = ["name", "email", "phone", "linkedin", "github", "summary"];
    for (const f of fields) {
        await fetch("/edit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ field: f, value: null }),
        });
    }
    const listFields = ["skills", "education", "experience", "projects"];
    for (const f of listFields) {
        await fetch("/edit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ field: f, value: [] }),
        });
    }
    // Refresh
    const resp = await fetch("/state");
    const data = await resp.json();
    renderResume(data.resume);
    renderMissing(data.missing);
    showToast("Resume reset!");
}


// ── Helpers ──
function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
function escHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return s.replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }


// ── Load initial state ──
(async function loadState() {
    try {
        const resp = await fetch("/state");
        const data = await resp.json();
        if (data.resume) {
            renderResume(data.resume);
            currentResumeSkills = data.resume.skills || [];
        }
        if (data.missing) renderMissing(data.missing);
    } catch (e) {
        console.error("Could not load initial state", e);
    }
})();
