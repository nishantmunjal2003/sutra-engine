/**
 * typeset.js — Sūtra Press Output Typesetting & PDF Preview (Step 2)
 * Handles:
 * - Synchronized compilation (Journal selection, single/double column layout, generation pipeline)
 * - Live Embedded PDF Preview
 * - Package and asset downloads (ZIP, JATS XML, PDF, TeX, logs)
 * - Output Inline Corrections & live PDF regeneration
 */

document.addEventListener("DOMContentLoaded", () => {
    if (!requireAuth()) return;
    initSharedNavbar();

    // Extract projectId from URL
    const pathParts = window.location.pathname.split("/").filter(Boolean);
    let projectId = null;
    const editorIdx = pathParts.indexOf("editor");
    const typesetIdx = pathParts.indexOf("typeset");

    if (editorIdx !== -1 && pathParts.length > editorIdx + 1) {
        projectId = pathParts[editorIdx + 1];
    } else if (typesetIdx !== -1 && pathParts.length > typesetIdx + 1) {
        projectId = pathParts[typesetIdx + 1];
    } else {
        projectId = pathParts[pathParts.length - 1];
    }

    if (!projectId) {
        const titleEl = document.getElementById("editorManuscriptTitle");
        if (titleEl) titleEl.textContent = "No project ID provided";
        return;
    }

    let currentProject = null;
    let conversionResult = null;

    // DOM references
    const editorManuscriptTitle  = document.getElementById("editorManuscriptTitle");
    const breadcrumbEditorLink   = document.getElementById("breadcrumbEditorLink");
    const backToStructureBtn     = document.getElementById("backToStructureBtn");
    const step1CompletedLink     = document.getElementById("step1CompletedLink");
    const deleteProjectBtn       = document.getElementById("deleteProjectBtn");

    const journalSelect          = document.getElementById("journalSelect");
    const layoutSingleCard       = document.getElementById("layoutSingleCard");
    const layoutDoubleCard       = document.getElementById("layoutDoubleCard");
    const layoutSingleInput      = document.getElementById("layoutSingleInput");
    const layoutDoubleInput      = document.getElementById("layoutDoubleInput");
    const generateBtn            = document.getElementById("generateBtn");

    const progressCard           = document.getElementById("progressCard");
    const resultsCard            = document.getElementById("resultsCard");
    const packageFileName        = document.getElementById("packageFileName");
    const statusBadge            = document.getElementById("statusBadge");
    const triageStatus           = document.getElementById("triageStatus");
    const xmlStatus              = document.getElementById("xmlStatus");
    const pdfStatus              = document.getElementById("pdfStatus");

    const viewTriageReportBtn    = document.getElementById("viewTriageReportBtn");
    const viewXmlErrorsBtn       = document.getElementById("viewXmlErrorsBtn");
    const viewPdfErrorsBtn       = document.getElementById("viewPdfErrorsBtn");

    const downloadZipBtn         = document.getElementById("downloadZipBtn");
    const downloadXmlBtn         = document.getElementById("downloadXmlBtn");
    const downloadPdfBtn         = document.getElementById("downloadPdfBtn");
    const downloadTexBtn         = document.getElementById("downloadTexBtn");
    const downloadLogBtn         = document.getElementById("downloadLogBtn");

    const previewPlaceholder     = document.getElementById("previewPlaceholder");
    const previewIframeContainer = document.getElementById("previewIframeContainer");
    const pdfPreviewIframe       = document.getElementById("pdfPreviewIframe");
    const reloadPdfBtn           = document.getElementById("reloadPdfBtn");
    const openPdfNewTabBtn       = document.getElementById("openPdfNewTabBtn");

    const outputReviewWorkspace  = document.getElementById("outputReviewWorkspace");
    const regenerateOutputBtn    = document.getElementById("regenerateOutputBtn");
    const finalizeOutputBtn      = document.getElementById("finalizeOutputBtn");

    const modalOverlay           = document.getElementById("modalOverlay");
    const modalTitle             = document.getElementById("modalTitle");
    const modalContent           = document.getElementById("modalContent");
    const closeModalBtn          = document.getElementById("closeModalBtn");

    // Setup links back to Step 1
    const structureUrl = `/editor/${projectId}`;
    if (breadcrumbEditorLink) breadcrumbEditorLink.href = structureUrl;
    if (backToStructureBtn)   backToStructureBtn.href   = structureUrl;
    if (step1CompletedLink)   step1CompletedLink.href   = structureUrl;

    // Helper: escape HTML
    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // Radio cards toggle
    [layoutSingleCard, layoutDoubleCard].forEach(card => {
        if (!card) return;
        card.addEventListener("click", () => {
            [layoutSingleCard, layoutDoubleCard].forEach(c => c.classList.remove("active"));
            card.classList.add("active");
            const radio = card.querySelector("input[type=radio]");
            if (radio) radio.checked = true;
        });
    });

    // Modal helpers
    function openModal(title, content) {
        if (modalTitle) modalTitle.textContent = title;
        if (modalContent) modalContent.textContent = content;
        if (modalOverlay) modalOverlay.classList.remove("hidden");
    }
    if (closeModalBtn) {
        closeModalBtn.addEventListener("click", () => {
            if (modalOverlay) modalOverlay.classList.add("hidden");
        });
    }
    if (modalOverlay) {
        modalOverlay.addEventListener("click", (e) => {
            if (e.target === modalOverlay) modalOverlay.classList.add("hidden");
        });
    }

    // ---- Load Project ----
    function loadProject(id) {
        fetch(`/project/${id}`)
            .then(res => {
                if (!res.ok) throw new Error(`Project not found (${res.status}).`);
                return res.json();
            })
            .then(data => {
                currentProject = data.project || data;
                if (!currentProject || !currentProject.id) {
                    throw new Error("Invalid project structure returned by server.");
                }

                const filename = currentProject.filename || "Untitled Manuscript";
                if (editorManuscriptTitle) {
                    editorManuscriptTitle.textContent = `Output Typeset: ${filename}`;
                }
                document.title = `${filename} — Output Typesetting & PDF Preview`;

                loadJournalSelectOptions();
                renderInlineReviewBlocks();

                // Auto-load most recent compilation run if available
                if (currentProject.history && currentProject.history.length > 0) {
                    const lastRun = currentProject.history[currentProject.history.length - 1];
                    conversionResult = {
                        project_id: currentProject.id,
                        run_id:     lastRun.run_id,
                        xml_validation: { passed: lastRun.xml_validation_passed, errors: lastRun.xml_errors },
                        compile:        { passed: lastRun.compile_passed,         errors: lastRun.compile_errors }
                    };
                    showResults(conversionResult);
                }
            })
            .catch(err => {
                console.error("Failed to load project in typeset view:", err);
                if (editorManuscriptTitle) editorManuscriptTitle.textContent = "Failed to load project";
                alert(`Error loading project: ${err.message}`);
            });
    }

    // ---- Journal Options ----
    function loadJournalSelectOptions() {
        if (!journalSelect) return;
        fetch("/api/journals")
            .then(res => {
                if (!res.ok) return [];
                return res.json();
            })
            .then(data => {
                journalSelect.innerHTML = '<option value="generic">Generic Style (Default)</option>';
                if (Array.isArray(data)) {
                    data.forEach(p => {
                        const opt = document.createElement("option");
                        opt.value = p.journal_id;
                        opt.textContent = p.journal_name;
                        journalSelect.appendChild(opt);
                    });
                }
            })
            .catch(() => {
                journalSelect.innerHTML = '<option value="generic">Generic Style (Default)</option>';
            });
    }

    // ---- Pipeline Stages helper ----
    const stages = ["jats", "latex", "pdf", "package"];
    function resetStages() {
        stages.forEach(s => {
            const el = document.getElementById(`stage-${s}`);
            if (el) el.className = "stage-item pending";
        });
    }
    function setStageStatus(stage, status) {
        const el = document.getElementById(`stage-${stage}`);
        if (el) el.className = `stage-item ${status}`;
    }

    // ---- Show Results ----
    function showResults(data) {
        if (!data || !resultsCard) return;
        resultsCard.classList.remove("hidden");

        if (packageFileName && currentProject) {
            packageFileName.textContent = currentProject.filename;
        }

        const isOverallSuccess = data.xml_validation && data.xml_validation.passed && data.compile && data.compile.passed;
        if (statusBadge) {
            statusBadge.textContent = isOverallSuccess ? "PASSED" : "WARNINGS";
            statusBadge.className   = isOverallSuccess ? "status-pill pass" : "status-pill warn";
        }

        if (triageStatus) {
            triageStatus.textContent = "PASSED";
            triageStatus.className   = "report-status text-success";
        }

        if (xmlStatus) {
            if (data.xml_validation && data.xml_validation.passed) {
                xmlStatus.textContent = "PASSED";
                xmlStatus.className   = "report-status text-success";
            } else {
                xmlStatus.textContent = "ISSUES";
                xmlStatus.className   = "report-status text-warning";
            }
        }

        if (pdfStatus) {
            if (data.compile && data.compile.passed) {
                pdfStatus.textContent = "PASSED";
                pdfStatus.className   = "report-status text-success";
            } else {
                pdfStatus.textContent = "FAILED";
                pdfStatus.className   = "report-status text-danger";
            }
        }

        // Configure downloads
        if (downloadZipBtn) downloadZipBtn.href = `/project/${data.project_id}/download/${data.run_id}/zip`;
        if (downloadXmlBtn) downloadXmlBtn.href = `/project/${data.project_id}/download/${data.run_id}/xml`;
        if (downloadPdfBtn) downloadPdfBtn.href = `/project/${data.project_id}/download/${data.run_id}/pdf`;
        if (downloadTexBtn) downloadTexBtn.href = `/project/${data.project_id}/download/${data.run_id}/tex`;
        if (downloadLogBtn) downloadLogBtn.href = `/project/${data.project_id}/download/${data.run_id}/log`;

        // Configure PDF Preview
        const pdfUrl = `/project/${data.project_id}/preview/${data.run_id}/pdf`;
        if (data.compile && data.compile.passed) {
            if (pdfPreviewIframe) {
                pdfPreviewIframe.src = `${pdfUrl}?t=${Date.now()}`;
            }
            if (previewPlaceholder) previewPlaceholder.classList.add("hidden");
            if (previewIframeContainer) previewIframeContainer.classList.remove("hidden");
            if (openPdfNewTabBtn) {
                openPdfNewTabBtn.href = pdfUrl;
                openPdfNewTabBtn.classList.remove("hidden");
            }
        } else {
            if (previewPlaceholder) {
                previewPlaceholder.innerHTML = `
                    <div class="placeholder-content">
                        <svg class="placeholder-icon" style="color: var(--danger-color, #ef4444); stroke: var(--danger-color, #ef4444);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>
                        </svg>
                        <p class="placeholder-text-primary" style="color: var(--danger-color, #ef4444);">Compilation Failed</p>
                        <p class="placeholder-text-secondary">LaTeX compilation produced errors. Click "View LaTeX Compile Log" to inspect errors.</p>
                    </div>
                `;
                previewPlaceholder.classList.remove("hidden");
            }
            if (previewIframeContainer) previewIframeContainer.classList.add("hidden");
            if (openPdfNewTabBtn) openPdfNewTabBtn.classList.add("hidden");
        }
    }

    // Modal listeners
    if (viewTriageReportBtn) {
        viewTriageReportBtn.onclick = () => {
            if (currentProject && currentProject.logs) {
                openModal("Triage & Manuscript Review Log", currentProject.logs.join("\n"));
            } else {
                openModal("Triage Log", "No triage log entries available.");
            }
        };
    }
    if (viewXmlErrorsBtn) {
        viewXmlErrorsBtn.onclick = () => {
            if (conversionResult && conversionResult.xml_validation) {
                const errs = conversionResult.xml_validation.errors;
                openModal("JATS XML Schema Validation", (errs && errs.length > 0) ? errs.join("\n") : "Validation passed without errors.");
            } else {
                openModal("JATS XML Schema Validation", "Compile first to view validation logs.");
            }
        };
    }
    if (viewPdfErrorsBtn) {
        viewPdfErrorsBtn.onclick = () => {
            if (conversionResult && conversionResult.compile) {
                const errs = conversionResult.compile.errors;
                openModal("LaTeX & PDF Compile Log", (errs && errs.length > 0) ? errs.join("\n") : "LaTeX compiled successfully.");
            } else {
                openModal("LaTeX & PDF Compile Log", "Compile first to view LaTeX logs.");
            }
        };
    }

    // Reload preview button
    if (reloadPdfBtn) {
        reloadPdfBtn.addEventListener("click", () => {
            if (pdfPreviewIframe && pdfPreviewIframe.src) {
                const url = new URL(pdfPreviewIframe.src, window.location.origin);
                url.searchParams.set("t", Date.now());
                pdfPreviewIframe.src = url.toString();
            }
        });
    }

    // ---- Trigger Generation ----
    if (generateBtn) {
        generateBtn.addEventListener("click", () => {
            if (!currentProject) return;
            generateBtn.setAttribute("disabled", "true");
            generateBtn.textContent = "Compiling Outputs…";

            if (progressCard) progressCard.classList.remove("hidden");
            if (resultsCard)  resultsCard.classList.add("hidden");

            resetStages();
            setStageStatus("jats", "running");

            const selectedLayout = document.querySelector("input[name=layout]:checked")?.value || "single";
            const selectedJournal = journalSelect ? journalSelect.value : "generic";

            const formData = new FormData();
            formData.append("layout", selectedLayout);
            formData.append("journal_id", selectedJournal);

            const timer1 = setTimeout(() => { setStageStatus("jats", "pass"); setStageStatus("latex", "running"); }, 400);
            const timer2 = setTimeout(() => { setStageStatus("latex", "pass"); setStageStatus("pdf", "running"); }, 900);

            fetch(`/project/${currentProject.id}/generate`, {
                method: "POST",
                body: formData
            })
            .then(res => {
                if (!res.ok) throw new Error("Compilation request failed.");
                return res.json();
            })
            .then(data => {
                clearTimeout(timer1);
                clearTimeout(timer2);

                setStageStatus("jats", (data.xml_validation && data.xml_validation.passed) ? "pass" : "warn");
                setStageStatus("latex", "pass");
                setStageStatus("pdf", (data.compile && data.compile.passed) ? "pass" : "fail");
                setStageStatus("package", "pass");

                conversionResult = data;
                showResults(data);

                // Reload project state to update history
                fetch(`/project/${currentProject.id}`)
                    .then(r => r.json())
                    .then(pData => {
                        currentProject = pData.project || pData;
                    });
            })
            .catch(err => {
                clearTimeout(timer1);
                clearTimeout(timer2);
                setStageStatus("pdf", "fail");
                alert(`Error compiling output: ${err.message}`);
            })
            .finally(() => {
                generateBtn.removeAttribute("disabled");
                generateBtn.textContent = "Generate JATS-XML, PDF & LaTeX";
            });
        });
    }

    // ---- Output Inline Corrections Workspace ----
    function renderInlineReviewBlocks() {
        if (!outputReviewWorkspace || !currentProject) return;
        outputReviewWorkspace.innerHTML = "";

        const blocks = currentProject.blocks || [];
        const editableTypes = ["title", "abstract", "heading_l1", "heading_l2", "heading_l3", "paragraph"];
        const relevantBlocks = blocks.filter(b => editableTypes.includes(b.type));

        if (relevantBlocks.length === 0) {
            outputReviewWorkspace.innerHTML = `<div style="padding:1rem;color:var(--text-secondary);font-size:0.85rem;">No editable text blocks found in this manuscript.</div>`;
            return;
        }

        relevantBlocks.forEach(block => {
            const card = document.createElement("div");
            card.style.cssText = "background:var(--bg-card);border:1px solid var(--border-color);border-radius:var(--radius-sm);padding:0.65rem 0.85rem;display:flex;flex-direction:column;gap:0.35rem;";

            const typeLabel = document.createElement("div");
            typeLabel.style.cssText = "font-size:0.7rem;font-weight:700;color:var(--brand-primary);text-transform:uppercase;display:flex;justify-content:space-between;";
            typeLabel.innerHTML = `<span>${escapeHtml(block.type.replace(/_/g, " "))}</span><span style="color:var(--text-muted);font-family:var(--font-mono);">#${block.id}</span>`;
            card.appendChild(typeLabel);

            let initialText = "";
            if (Array.isArray(block.content)) {
                initialText = block.content.map(r => (typeof r === "object" ? (r.text || "") : String(r))).join("");
            } else if (typeof block.content === "string") {
                initialText = block.content;
            } else if (block.content && block.content.content_text) {
                initialText = block.content.content_text;
            }

            const input = document.createElement("textarea");
            input.style.cssText = "width:100%;border:1px solid var(--border-color);border-radius:4px;padding:0.35rem 0.5rem;font-size:0.85rem;line-height:1.5;font-family:inherit;color:var(--text-primary);resize:vertical;";
            input.value = initialText;
            input.rows = Math.min(6, Math.max(1, Math.ceil((initialText.length || 20) / 70)));

            input.onblur = (e) => {
                const newText = e.target.value.trim();
                if (newText !== initialText.trim()) {
                    block.content = [{ text: newText, bold: false, italic: false }];
                    block.state = "confirmed";
                    saveProjectState();
                }
            };

            card.appendChild(input);
            outputReviewWorkspace.appendChild(card);
        });
    }

    function saveProjectState() {
        if (!currentProject) return Promise.resolve();
        return fetch(`/project/${currentProject.id}/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ blocks: currentProject.blocks })
        })
        .then(res => res.json())
        .then(data => {
            currentProject = data.project || data;
        });
    }

    // Regenerate Output Button
    if (regenerateOutputBtn) {
        regenerateOutputBtn.addEventListener("click", () => {
            saveProjectState().then(() => {
                if (generateBtn) generateBtn.click();
            });
        });
    }

    // Finalize Output Button
    if (finalizeOutputBtn) {
        finalizeOutputBtn.addEventListener("click", () => {
            if (confirm("Output review completed! Would you like to lock output and download the final ZIP package?")) {
                if (downloadZipBtn && downloadZipBtn.href && !downloadZipBtn.href.endsWith("#")) {
                    window.location.href = downloadZipBtn.href;
                } else {
                    alert("Please compile the document first using 'Generate JATS-XML, PDF & LaTeX'.");
                }
            }
        });
    }

    // Delete project
    if (deleteProjectBtn) {
        deleteProjectBtn.addEventListener("click", () => {
            if (!currentProject) return;
            if (confirm(`Permanently delete manuscript "${currentProject.filename}"? This action cannot be undone.`)) {
                fetch(`/project/${currentProject.id}`, { method: "DELETE" })
                    .then(res => {
                        if (!res.ok) throw new Error("Delete failed.");
                        return res.json();
                    })
                    .then(() => { window.location.href = "/"; })
                    .catch(err => alert(err.message));
            }
        });
    }

    // Boot
    loadProject(projectId);
});
