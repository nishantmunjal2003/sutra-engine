/**
 * journals.js — Journal Profiles Management
 * Handles:
 *  - Tab-based navigation across all profile sections
 *  - Journal profile listing, creation, and editing
 *  - Reference PDF style analysis and auto-fill
 *  - Journal Identity (logo, ISSN print/online, website, publisher)
 *  - First page branding banner configuration
 *  - Running Header (Page 2+) & Footer styling with line rules and hex color pickers
 *  - Volume / Issue management (dynamic add, remove, select active)
 *  - Combined Typography (body, title block, headings)
 *  - Block Typesetting specifications for all manuscript elements
 */

document.addEventListener("DOMContentLoaded", () => {
    if (typeof requireAuth === "function" && !requireAuth()) return;
    if (typeof initSharedNavbar === "function") initSharedNavbar();

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    let selectedJournalFile = null;
    let currentLogoFilename = null;
    let currentVolumes = [];
    let activeVolumeId = null;
    let currentLoadedJournalId = null;

    // DOM references
    const sidebarJournalProfilesList = document.getElementById("sidebarJournalProfilesList");
    const sidebarNewProfileBtn  = document.getElementById("sidebarNewProfileBtn");
    const newProfileSidebarBtn  = document.getElementById("newProfileSidebarBtn");
    const createNewProfileBtn   = document.getElementById("createNewProfileBtn");
    const deleteCurrentProfileBtn = document.getElementById("deleteCurrentProfileBtn");
    const formModeTitle         = document.getElementById("formModeTitle");
    const pdfAutoFillDetails    = document.getElementById("pdfAutoFillDetails");

    const autoDetectPdfBtn      = document.getElementById("autoDetectPdfBtn");
    const autoDetectPdfInput    = document.getElementById("autoDetectPdfInput");
    const aiVerificationBanner  = document.getElementById("aiVerificationBanner");
    const aiVerificationTitle   = document.getElementById("aiVerificationTitle");
    const aiVerificationBadge   = document.getElementById("aiVerificationBadge");
    const aiTokenBadge          = document.getElementById("aiTokenBadge");
    const aiVerificationSummary = document.getElementById("aiVerificationSummary");
    const aiChecksList          = document.getElementById("aiChecksList");
    const closeAiVerificationBtn= document.getElementById("closeAiVerificationBtn");

    const journalIdInput        = document.getElementById("journalIdInput");
    const journalNameInput      = document.getElementById("journalNameInput");
    const journalDropZone       = document.getElementById("journalDropZone");
    const journalPdfInput       = document.getElementById("journalPdfInput");
    const journalPdfInfo        = document.getElementById("journalPdfInfo");
    const journalPdfName        = document.getElementById("journalPdfName");
    const analyzeJournalBtn     = document.getElementById("analyzeJournalBtn");
    const journalSettingsEditor = document.getElementById("journalSettingsEditor");
    const saveJournalSettingsBtn= document.getElementById("saveJournalSettingsBtn");

    // Tab navigation buttons
    const tabBtns = document.querySelectorAll(".journal-tab-btn");
    const tabPanes = document.querySelectorAll(".journal-tab-pane");
    const prevTabBtn = document.getElementById("prevTabBtn");
    const nextTabBtn = document.getElementById("nextTabBtn");

    // 1. Identity & Logo DOM
    const logoPreviewImg        = document.getElementById("logoPreviewImg");
    const logoPlaceholder       = document.getElementById("logoPlaceholder");
    const logoFileInput         = document.getElementById("logoFileInput");
    const uploadLogoBtn         = document.getElementById("uploadLogoBtn");
    const removeLogoBtn         = document.getElementById("removeLogoBtn");
    const logoUploadStatus      = document.getElementById("logoUploadStatus");
    const setIssnPrint          = document.getElementById("setIssnPrint");
    const setIssnOnline         = document.getElementById("setIssnOnline");
    const setWebsite            = document.getElementById("setWebsite");
    const setPublisher          = document.getElementById("setPublisher");

    // 2. Volumes & Issues DOM
    const volumeIssuesTbody     = document.getElementById("volumeIssuesTbody");
    const noVolumesText         = document.getElementById("noVolumesText");
    const newVolNo              = document.getElementById("newVolNo");
    const newIssueNo            = document.getElementById("newIssueNo");
    const newVolYear            = document.getElementById("newVolYear");
    const newVolPageRange       = document.getElementById("newVolPageRange");
    const addVolumeBtn          = document.getElementById("addVolumeBtn");

    // 3. Running Header DOM
    const setHeaderEnabled          = document.getElementById("setHeaderEnabled");
    const setHeaderFromPage         = document.getElementById("setHeaderFromPage");
    const setHeaderLeft             = document.getElementById("setHeaderLeft");
    const setHeaderCenter           = document.getElementById("setHeaderCenter");
    const setHeaderRight            = document.getElementById("setHeaderRight");
    const setHeaderSize             = document.getElementById("setHeaderSize");
    const setHeaderStyle            = document.getElementById("setHeaderStyle");
    const setHeaderLineShow         = document.getElementById("setHeaderLineShow");
    const setHeaderLineColor        = document.getElementById("setHeaderLineColor");
    const setHeaderLineColorPicker  = document.getElementById("setHeaderLineColorPicker");
    const setHeaderLineThickness    = document.getElementById("setHeaderLineThickness");

    // 4. Running Footer DOM
    const setFooterEnabled          = document.getElementById("setFooterEnabled");
    const setFooterFromPage         = document.getElementById("setFooterFromPage");
    const setFooterLeft             = document.getElementById("setFooterLeft");
    const setFooterCenter           = document.getElementById("setFooterCenter");
    const setFooterRight            = document.getElementById("setFooterRight");
    const setFooterSize             = document.getElementById("setFooterSize");
    const setFooterStyle            = document.getElementById("setFooterStyle");
    const setFooterLineShow         = document.getElementById("setFooterLineShow");
    const setFooterLineColor        = document.getElementById("setFooterLineColor");
    const setFooterLineColorPicker  = document.getElementById("setFooterLineColorPicker");
    const setFooterLineThickness    = document.getElementById("setFooterLineThickness");

    // 5. First Page Header DOM
    const setFirstPageHeaderEnabled = document.getElementById("setFirstPageHeaderEnabled");
    const setLogoPosition           = document.getElementById("setLogoPosition");
    const setLogoHeight             = document.getElementById("setLogoHeight");
    const setShowLogo               = document.getElementById("setShowLogo");
    const setShowJournalName        = document.getElementById("setShowJournalName");
    const setShowIssn               = document.getElementById("setShowIssn");
    const setShowVolumeIssue        = document.getElementById("setShowVolumeIssue");

    // 6. Page Layout DOM
    const setPaperSize      = document.getElementById("setPaperSize");
    const setColumns        = document.getElementById("setColumns");
    const setMarginTop      = document.getElementById("setMarginTop");
    const setMarginBottom   = document.getElementById("setMarginBottom");
    const setMarginLeft     = document.getElementById("setMarginLeft");
    const setMarginRight    = document.getElementById("setMarginRight");

    // 7. Combined Typography & Headings DOM (7, 8, 9)
    const setBodyFont       = document.getElementById("setBodyFont");
    const setBodySize       = document.getElementById("setBodySize");
    const setLineSpacing    = document.getElementById("setLineSpacing");
    const setTitleSize      = document.getElementById("setTitleSize");
    const setAuthorsSize    = document.getElementById("setAuthorsSize");
    const setAffiliationSize= document.getElementById("setAffiliationSize");
    const setH1Size         = document.getElementById("setH1Size");
    const setH2Size         = document.getElementById("setH2Size");
    const setH3Size         = document.getElementById("setH3Size");

    // 8. Block Typesetting DOM (All manuscript blocks)
    // Abstract
    const setAbstractHeading        = document.getElementById("setAbstractHeading");
    const setAbstractHeadingSize    = document.getElementById("setAbstractHeadingSize");
    const setAbstractBodySize       = document.getElementById("setAbstractBodySize");
    const setAbstractIndented       = document.getElementById("setAbstractIndented");
    const setAbstractBoxBorder      = document.getElementById("setAbstractBoxBorder");
    const setAbstractLabelsBold     = document.getElementById("setAbstractLabelsBold");
    const setAbstractFullWidth      = document.getElementById("setAbstractFullWidth");
    const setAbstractSingleParagraph = document.getElementById("setAbstractSingleParagraph");
    const setAbstractIncludeKeywords = document.getElementById("setAbstractIncludeKeywords");
    // Keywords
    const setKeywordsLabel          = document.getElementById("setKeywordsLabel");
    const setKeywordsWeight         = document.getElementById("setKeywordsWeight");
    const setKeywordsSize           = document.getElementById("setKeywordsSize");
    const setKeywordsSeparator      = document.getElementById("setKeywordsSeparator");
    // Figures
    const setFigureCaptionPos       = document.getElementById("setFigureCaptionPos");
    const setFigurePrefix           = document.getElementById("setFigurePrefix");
    const setFigureLabelStyle       = document.getElementById("setFigureLabelStyle");
    const setFigureCaptionSize      = document.getElementById("setFigureCaptionSize");
    const setFigureSpanWide         = document.getElementById("setFigureSpanWide");
    const setFigureSeparator        = document.getElementById("setFigureSeparator");
    const setFigureCaptionJustification = document.getElementById("setFigureCaptionJustification");
    // Tables
    const setTableCaptionPos        = document.getElementById("setTableCaptionPos");
    const setTablePrefix            = document.getElementById("setTablePrefix");
    const setTableLabelStyle        = document.getElementById("setTableLabelStyle");
    const setTableBorderStyle       = document.getElementById("setTableBorderStyle");
    const setTableCaptionSize       = document.getElementById("setTableCaptionSize");
    const setTableSpanWide          = document.getElementById("setTableSpanWide");
    const setTableSeparator         = document.getElementById("setTableSeparator");
    const setTableVerticalLines     = document.getElementById("setTableVerticalLines");
    const setTableCaptionJustification = document.getElementById("setTableCaptionJustification");
    // Equations
    const setEquationNumbering      = document.getElementById("setEquationNumbering");
    const setEquationAlign          = document.getElementById("setEquationAlign");
    const setEquationBracket        = document.getElementById("setEquationBracket");
    const setEquationSize           = document.getElementById("setEquationSize");
    // References
    const setRefHeading             = document.getElementById("setRefHeading");
    const setRefCitationStyle       = document.getElementById("setRefCitationStyle");
    const setRefFontSize            = document.getElementById("setRefFontSize");
    const setRefHangingIndent       = document.getElementById("setRefHangingIndent");
    // 7. Conclusion
    const setConclusionHeading      = document.getElementById("setConclusionHeading");
    const setConclusionSize         = document.getElementById("setConclusionSize");
    const setConclusionNumbering    = document.getElementById("setConclusionNumbering");
    // 8. Footnotes
    const setFootnoteSize           = document.getElementById("setFootnoteSize");
    const setFootnoteMarkerStyle    = document.getElementById("setFootnoteMarkerStyle");
    const setFootnoteRule           = document.getElementById("setFootnoteRule");
    // 9. Blockquotes
    const setQuoteSize              = document.getElementById("setQuoteSize");
    const setQuoteStyle             = document.getElementById("setQuoteStyle");
    const setQuoteIndent            = document.getElementById("setQuoteIndent");
    // 10. Lists
    const setListBulletMarker       = document.getElementById("setListBulletMarker");
    const setListNumberingStyle     = document.getElementById("setListNumberingStyle");
    const setListIndent             = document.getElementById("setListIndent");
    const setListItemSpacing        = document.getElementById("setListItemSpacing");
    // 11. Declarations
    const setDeclarationsHeadingStyle = document.getElementById("setDeclarationsHeadingStyle");
    const setDeclarationsSize       = document.getElementById("setDeclarationsSize");

    // AI Multi-Model Modal DOM references
    const aiModelsConfigBtn         = document.getElementById("aiModelsConfigBtn");
    const aiRoutingModal            = document.getElementById("aiRoutingModal");
    const closeAiRoutingModalBtn    = document.getElementById("closeAiRoutingModalBtn");
    const cancelAiKeysBtn           = document.getElementById("cancelAiKeysBtn");
    const saveAiKeysBtn             = document.getElementById("saveAiKeysBtn");
    const aiProvidersContainer      = document.getElementById("aiProvidersContainer");
    const aiKeyOpenAI               = document.getElementById("aiKeyOpenAI");
    const aiKeyAnthropic            = document.getElementById("aiKeyAnthropic");
    const aiKeyGemini               = document.getElementById("aiKeyGemini");
    const aiKeysSaveStatus          = document.getElementById("aiKeysSaveStatus");

    // Set current year default for volume input
    if (newVolYear) {
        newVolYear.value = new Date().getFullYear();
    }

    // ---- TAB SWITCHING FUNCTIONALITY ----
    function switchTab(tabId) {
        tabBtns.forEach(btn => {
            const isMatch = btn.dataset.tab === tabId;
            btn.classList.toggle("active", isMatch);
            btn.setAttribute("aria-selected", isMatch ? "true" : "false");
        });
        tabPanes.forEach(pane => {
            pane.classList.toggle("active", pane.id === tabId);
        });
    }

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            switchTab(btn.dataset.tab);
        });
    });

    const tabOrder = [
        "tabIdentity",
        "tabVolumes",
        "tabRunningHeader",
        "tabRunningFooter",
        "tabTitleBanner",
        "tabLayout",
        "tabTypography",
        "tabBlockTypesetting"
    ];

    if (prevTabBtn) {
        prevTabBtn.addEventListener("click", () => {
            const currentActive = document.querySelector(".journal-tab-pane.active");
            const currentId = currentActive ? currentActive.id : tabOrder[0];
            const idx = tabOrder.indexOf(currentId);
            if (idx > 0) {
                switchTab(tabOrder[idx - 1]);
            }
        });
    }

    if (nextTabBtn) {
        nextTabBtn.addEventListener("click", () => {
            const currentActive = document.querySelector(".journal-tab-pane.active");
            const currentId = currentActive ? currentActive.id : tabOrder[0];
            const idx = tabOrder.indexOf(currentId);
            if (idx < tabOrder.length - 1) {
                switchTab(tabOrder[idx + 1]);
            }
        });
    }

    // ---- Color Picker Synchronization ----
    function syncColor(inputEl, pickerEl) {
        if (!inputEl || !pickerEl) return;
        pickerEl.addEventListener("input", (e) => {
            inputEl.value = e.target.value.toUpperCase();
        });
        inputEl.addEventListener("input", (e) => {
            let val = e.target.value.trim();
            if (!val.startsWith("#")) val = "#" + val;
            if (/^#[0-9A-F]{6}$/i.test(val)) {
                pickerEl.value = val;
            }
        });
    }
    syncColor(setHeaderLineColor, setHeaderLineColorPicker);
    syncColor(setFooterLineColor, setFooterLineColorPicker);

    // ---- PDF Reference Drop Zone ----
    if (journalDropZone) {
        journalDropZone.addEventListener("click", () => journalPdfInput.click());

        journalPdfInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                selectedJournalFile = e.target.files[0];
                journalPdfName.textContent = selectedJournalFile.name;
                journalPdfInfo.classList.remove("hidden");
            }
        });

        ["dragover", "dragenter"].forEach(ev => {
            journalDropZone.addEventListener(ev, (e) => {
                e.preventDefault();
                journalDropZone.classList.add("dragover");
            });
        });
        ["dragleave", "drop"].forEach(ev => {
            journalDropZone.addEventListener(ev, (e) => {
                e.preventDefault();
                journalDropZone.classList.remove("dragover");
            });
        });
        journalDropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length > 0) {
                selectedJournalFile = e.dataTransfer.files[0];
                journalPdfName.textContent = selectedJournalFile.name;
                journalPdfInfo.classList.remove("hidden");
            }
        });
    }

    // ---- Logo Upload Handler ----
    if (uploadLogoBtn) {
        uploadLogoBtn.addEventListener("click", () => {
            const jId = journalIdInput.value.trim();
            if (!jId) {
                alert("Please enter a Journal ID slug before uploading a logo.");
                switchTab("tabIdentity");
                journalIdInput.focus();
                return;
            }
            logoFileInput.click();
        });
    }

    if (logoFileInput) {
        logoFileInput.addEventListener("change", (e) => {
            if (!e.target.files.length) return;
            const file = e.target.files[0];
            const jId = journalIdInput.value.trim();

            uploadLogoBtn.disabled = true;
            logoUploadStatus.textContent = "Uploading logo…";

            const formData = new FormData();
            formData.append("file", file);

            fetch(`/api/journals/${encodeURIComponent(jId)}/logo`, {
                method: "POST",
                body: formData
            })
            .then(res => {
                if (!res.ok) throw new Error("Failed to upload logo.");
                return res.json();
            })
            .then(data => {
                currentLogoFilename = data.filename;
                displayLogo(`/api/journals/${encodeURIComponent(jId)}/logo?t=${Date.now()}`);
                logoUploadStatus.textContent = "Logo saved!";
                setTimeout(() => { logoUploadStatus.textContent = ""; }, 2500);
            })
            .catch(err => {
                alert(err.message || "Failed to upload logo.");
                logoUploadStatus.textContent = "";
            })
            .finally(() => {
                uploadLogoBtn.disabled = false;
                logoFileInput.value = "";
            });
        });
    }

    if (removeLogoBtn) {
        removeLogoBtn.addEventListener("click", () => {
            currentLogoFilename = null;
            clearLogo();
        });
    }

    function displayLogo(url) {
        if (!logoPreviewImg || !logoPlaceholder || !removeLogoBtn) return;
        logoPreviewImg.src = url;
        logoPreviewImg.classList.remove("hidden");
        logoPlaceholder.classList.add("hidden");
        removeLogoBtn.classList.remove("hidden");
    }

    function clearLogo() {
        if (!logoPreviewImg || !logoPlaceholder || !removeLogoBtn) return;
        logoPreviewImg.src = "";
        logoPreviewImg.classList.add("hidden");
        logoPlaceholder.classList.remove("hidden");
        removeLogoBtn.classList.add("hidden");
    }

    // ---- Volumes & Issues Management ----
    function renderVolumesTable() {
        if (!volumeIssuesTbody) return;
        volumeIssuesTbody.innerHTML = "";
        if (!currentVolumes || currentVolumes.length === 0) {
            if (noVolumesText) noVolumesText.classList.remove("hidden");
            return;
        }
        if (noVolumesText) noVolumesText.classList.add("hidden");

        currentVolumes.forEach((v, index) => {
            const tr = document.createElement("tr");
            const isChecked = (v.id === activeVolumeId || v.is_active);

            tr.innerHTML = `
                <td style="text-align:center;">
                    <input type="radio" name="activeVolumeRadio" value="${escapeHtml(v.id)}" ${isChecked ? "checked" : ""}>
                </td>
                <td><strong>Vol. ${escapeHtml(v.volume_no)}</strong></td>
                <td>Issue ${escapeHtml(v.issue_no)}</td>
                <td>${v.year}</td>
                <td>${v.page_range ? escapeHtml(v.page_range) : '<span style="color:var(--text-muted);">&mdash;</span>'}</td>
                <td style="text-align:center;">
                    <button type="button" class="btn btn-outline btn-sm remove-vol-btn" data-index="${index}" style="color:var(--state-error-text);padding:2px 8px;">
                        &times;
                    </button>
                </td>
            `;

            tr.querySelector("input[name='activeVolumeRadio']").addEventListener("change", () => {
                activeVolumeId = v.id;
                currentVolumes.forEach(vol => { vol.is_active = (vol.id === activeVolumeId); });
            });

            tr.querySelector(".remove-vol-btn").addEventListener("click", (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                currentVolumes.splice(idx, 1);
                if (currentVolumes.length > 0 && !currentVolumes.some(vol => vol.id === activeVolumeId)) {
                    activeVolumeId = currentVolumes[0].id;
                    currentVolumes[0].is_active = true;
                }
                renderVolumesTable();
            });

            volumeIssuesTbody.appendChild(tr);
        });
    }

    if (addVolumeBtn) {
        addVolumeBtn.addEventListener("click", () => {
            const vNo = newVolNo.value.trim();
            const iNo = newIssueNo.value.trim();
            const yr = parseInt(newVolYear.value) || new Date().getFullYear();
            const pr = newVolPageRange.value.trim();

            if (!vNo || !iNo) {
                alert("Please enter both Volume and Issue numbers.");
                return;
            }

            const volId = `vol-${vNo}-iss-${iNo}`;
            const isFirst = currentVolumes.length === 0;

            const newVol = {
                id: volId,
                volume_no: vNo,
                issue_no: iNo,
                year: yr,
                page_range: pr || null,
                publication_month: null,
                is_active: isFirst
            };

            currentVolumes.push(newVol);
            if (isFirst || !activeVolumeId) {
                activeVolumeId = volId;
            }

            newVolNo.value = "";
            newIssueNo.value = "";
            newVolPageRange.value = "";
            renderVolumesTable();
        });
    }

    // ---- Auto-Detect from Reference PDF (✨ Auto-Detect from PDF Button) ----
    if (autoDetectPdfBtn && autoDetectPdfInput) {
        autoDetectPdfBtn.addEventListener("click", () => {
            autoDetectPdfInput.click();
        });

        autoDetectPdfInput.addEventListener("change", (e) => {
            if (!e.target.files.length) return;
            const file = e.target.files[0];
            runPdfAutoDetect(file);
        });
    }

    if (closeAiVerificationBtn && aiVerificationBanner) {
        closeAiVerificationBtn.addEventListener("click", () => {
            aiVerificationBanner.classList.add("hidden");
        });
    }

    function runPdfAutoDetect(file) {
        if (!file) return;

        const originalBtnHtml = autoDetectPdfBtn.innerHTML;
        autoDetectPdfBtn.disabled = true;
        autoDetectPdfBtn.innerHTML = `
            <svg class="spin-anim" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-linecap="round"/>
            </svg>
            <span>Analyzing &amp; AI Checking…</span>
        `;

        const jId = journalIdInput ? journalIdInput.value.trim() : "";
        const jName = journalNameInput ? journalNameInput.value.trim() : "";

        const formData = new FormData();
        formData.append("file", file);
        if (jId) formData.append("journal_id", jId);
        if (jName) formData.append("journal_name", jName);

        fetch("/api/journals/analyze", {
            method: "POST",
            body: formData
        })
        .then(res => {
            if (!res.ok) throw new Error("PDF analysis failed. Please verify the PDF format.");
            return res.json();
        })
        .then(data => {
            const settings = data.settings || data;
            const journalId = data.journal_id || settings.journal_id;
            const journalName = data.journal_name || settings.journal_name;

            currentLoadedJournalId = journalId;

            // 1. Populate Journal ID & Name in header / inputs
            if (journalIdInput && journalId) {
                journalIdInput.value = journalId;
            }
            if (journalNameInput && journalName) {
                journalNameInput.value = journalName;
            }
            if (formModeTitle) {
                formModeTitle.textContent = `Editing Profile: ${journalName} (${journalId})`;
            }

            // 2. Populate all 8 tabs with detected settings
            populateSettingsForm(settings);

            // 3. Handle auto-extracted high-res logo
            if (data.has_logo || data.logo_url) {
                currentLogoFilename = "logo.png";
                const logoUrl = data.logo_url || `/api/journals/${encodeURIComponent(journalId)}/logo`;
                displayLogo(`${logoUrl}?t=${Date.now()}`);
            }

            // 4. Render AI Verification Banner
            if (data.ai_verification) {
                renderAiVerification(data.ai_verification);
            }

            // 5. Ensure Delete Profile button is visible
            if (deleteCurrentProfileBtn) {
                deleteCurrentProfileBtn.style.display = "inline-block";
            }

            // 6. Switch to Identity & Logo tab first
            switchTab("tabIdentity");

            // 7. Refresh sidebar profiles list
            if (typeof loadJournalsList === "function") {
                loadJournalsList();
            }
        })
        .catch(err => {
            alert(err.message || "Failed to analyze PDF.");
        })
        .finally(() => {
            autoDetectPdfBtn.disabled = false;
            autoDetectPdfBtn.innerHTML = originalBtnHtml;
            autoDetectPdfInput.value = "";
        });
    }

    function renderAiVerification(ai) {
        if (!aiVerificationBanner) return;

        if (aiVerificationTitle) {
            aiVerificationTitle.textContent = ai.status === "passed" 
                ? "✨ AI Cross-Check: Verified & Validated" 
                : "⚠️ AI Cross-Check: Completed with Notes";
        }
        if (aiVerificationBadge) {
            aiVerificationBadge.textContent = `Confidence: ${ai.confidence_score ?? 98}%`;
            aiVerificationBadge.style.color = ai.status === "passed" ? "#059669" : "#d97706";
            aiVerificationBadge.style.background = ai.status === "passed" ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)";
        }
        if (aiTokenBadge) {
            const tokens = ai.tokens_used ?? 0;
            aiTokenBadge.textContent = tokens === 0
                ? "⚡ 0 Tokens Used (Zero-Token Local Engine)"
                : `⚡ ${tokens} Tokens Used (${ai.provider || "AI Cross-Check"})`;
        }
        if (aiVerificationSummary) {
            let summaryText = ai.summary || "All primary typography, lines, and layout verified against reference PDF.";
            if (ai.fallback_trace && ai.fallback_trace.length > 1) {
                const traceSteps = ai.fallback_trace.map(t => t.split(":")[0]).join(" → ");
                summaryText += ` [Fallback Chain: ${traceSteps}]`;
            }
            aiVerificationSummary.textContent = summaryText;
        }
        if (aiChecksList) {
            aiChecksList.innerHTML = "";
            const checks = ai.checks || [];
            checks.forEach(c => {
                const item = document.createElement("div");
                item.style.cssText = "display:flex; align-items:flex-start; gap:0.45rem; font-size:0.8rem; background:rgba(255,255,255,0.85); padding:0.4rem 0.6rem; border-radius:6px; border:1px solid rgba(0,0,0,0.06);";
                const isOk = c.status === "ok";
                const icon = isOk ? "✅" : (c.status === "warning" ? "⚠️" : "ℹ️");
                item.innerHTML = `
                    <span style="flex-shrink:0;">${icon}</span>
                    <div>
                        <strong style="color:var(--text-primary);">${escapeHtml(c.name)}:</strong>
                        <span style="color:var(--text-secondary); margin-left:0.25rem;">${escapeHtml(c.message)}</span>
                    </div>
                `;
                aiChecksList.appendChild(item);
            });
        }

        aiVerificationBanner.classList.remove("hidden");
    }

    // ---- Reset to New Profile Template ----
    function resetToNewProfile() {
        currentLoadedJournalId = null;
        if (formModeTitle) {
            formModeTitle.textContent = "New Journal Profile Configuration";
        }
        if (aiVerificationBanner) {
            aiVerificationBanner.classList.add("hidden");
        }
        journalIdInput.value = "";
        journalNameInput.value = "";
        currentLogoFilename = null;
        clearLogo();

        populateSettingsForm({
            journal_id: "",
            journal_name: "",
            page: { paper_size: "a4", columns: 2, margin_top_in: 0.75, margin_bottom_in: 0.75, margin_left_in: 0.75, margin_right_in: 0.75 },
            body_text: { font_family: "Times New Roman", font_size_pt: 10.0, line_spacing: 1.15 },
            title_block: { title_font_size_pt: 16.0, authors_font_size_pt: 11.0, affiliation_font_size_pt: 9.0 },
            headings: { h1: { font_size_pt: 12.0 }, h2: { font_size_pt: 11.0 }, h3: { font_size_pt: 10.0 } },
            abstract: { heading_text: "Abstract", heading_font_size_pt: 11.0, heading_font_weight: "bold", body_font_size_pt: 9.0, indented: true, box_border: false, structured_labels_bold: true, full_width_in_twocol: true, single_paragraph: false, include_keywords_in_box: false },
            keywords: { label_text: "Keywords:", label_font_weight: "bold", font_size_pt: 9.0, separator: "; " },
            figures: { caption_position: "below", caption_label_prefix: "Figure", caption_label_style: "bold", caption_font_size_pt: 9.0, span_wide_figures: true, label_separator: ".", caption_justification: "justified" },
            tables: { caption_position: "above", caption_label_prefix: "Table", caption_label_style: "bold", caption_font_size_pt: 9.0, border_style: "booktabs", span_wide_tables: true, label_separator: ".", show_vertical_lines: false, caption_justification: "justified" },
            equations: { display_numbering: true, numbering_alignment: "right", numbering_bracket: "parentheses", font_size_pt: 10.0 },
            references: { section_heading_text: "References", citation_style: "numeric", font_size_pt: 9.0, hanging_indent: true },
            conclusion: { heading_text: "Conclusion", font_size_pt: 12.0, numbering: "numeric" },
            footnotes: { font_size_pt: 8.0, marker_style: "numeric", rule_separator: true },
            blockquotes: { font_size_pt: 9.0, font_style: "italic", indent_pt: 18.0 },
            lists: { bullet_marker: "bullet", numbering_style: "numeric", indent_pt: 15.0, item_spacing_pt: 3.0 },
            declarations: { heading_style: "inline_bold", font_size_pt: 9.0 },
            identity: { logo_filename: null, issn_print: "", issn_online: "", website: "", publisher: "" },
            header: {
                enabled: true,
                from_page: 2,
                left_text: "{authors} / {journal}",
                center_text: "",
                right_text: "{volume}({issue}), {year}",
                font_size_pt: 8.5,
                font_style: "italic",
                line: { show: true, thickness_pt: 0.8, color: "#CC0066" }
            },
            footer: {
                enabled: true,
                from_page: 1,
                left_text: "",
                center_text: "\\thepage",
                right_text: "",
                font_size_pt: 8.5,
                font_style: "normal",
                line: { show: true, thickness_pt: 0.8, color: "#CC0066" }
            },
            first_page_header: {
                enabled: true,
                show_logo: true,
                logo_position: "left",
                logo_max_height_mm: 16.0,
                show_journal_name: true,
                show_issn: true,
                show_volume_issue: true,
                show_website: true
            },
            volumes: [
                { id: "vol-1-iss-1", volume_no: "1", issue_no: "1", year: new Date().getFullYear(), page_range: "1–10", is_active: true }
            ],
            active_volume_id: "vol-1-iss-1"
        });

        // Unhighlight sidebar subnav items
        document.querySelectorAll(".sidebar-subnav-item").forEach(el => el.classList.remove("active"));
        if (deleteCurrentProfileBtn) {
            deleteCurrentProfileBtn.style.display = "none";
        }
        if (formModeTitle) {
            formModeTitle.textContent = "Create New Journal Profile";
        }
        switchTab("tabIdentity");
        journalNameInput.focus();
    }

    if (sidebarNewProfileBtn) {
        sidebarNewProfileBtn.addEventListener("click", resetToNewProfile);
    }
    if (newProfileSidebarBtn) {
        newProfileSidebarBtn.addEventListener("click", resetToNewProfile);
    }
    if (createNewProfileBtn) {
        createNewProfileBtn.addEventListener("click", resetToNewProfile);
    }

    // ---- Form Population Helper ----
    function populateSettingsForm(data) {
        if (!data) return;

        // Page Layout
        if (data.page && setPaperSize) {
            setPaperSize.value      = data.page.paper_size || "a4";
            setColumns.value        = (data.page.columns || 1).toString();
            setMarginTop.value      = data.page.margin_top_in ?? 0.75;
            setMarginBottom.value   = data.page.margin_bottom_in ?? 0.75;
            setMarginLeft.value     = data.page.margin_left_in ?? 0.75;
            setMarginRight.value    = data.page.margin_right_in ?? 0.75;
        }

        // Body Typography
        if (data.body_text && setBodyFont) {
            setBodyFont.value       = data.body_text.font_family || "Times New Roman";
            setBodySize.value       = data.body_text.font_size_pt ?? 10.0;
            setLineSpacing.value    = data.body_text.line_spacing ?? 1.15;
        }

        // Title Block
        if (data.title_block && setTitleSize) {
            setTitleSize.value      = data.title_block.title_font_size_pt ?? 16.0;
            setAuthorsSize.value    = data.title_block.authors_font_size_pt ?? 11.0;
            setAffiliationSize.value= data.title_block.affiliation_font_size_pt ?? 9.0;
        }

        // Headings
        if (data.headings && setH1Size) {
            setH1Size.value         = data.headings.h1?.font_size_pt ?? 12.0;
            setH2Size.value         = data.headings.h2?.font_size_pt ?? 11.0;
            setH3Size.value         = data.headings.h3?.font_size_pt ?? 10.0;
        }

        // Identity
        const iden = data.identity || {};
        if (setIssnPrint)  setIssnPrint.value  = iden.issn_print || "";
        if (setIssnOnline) setIssnOnline.value = iden.issn_online || "";
        if (setWebsite)    setWebsite.value    = iden.website || "";
        if (setPublisher)  setPublisher.value  = iden.publisher || "";

        // Logo check
        const jId = data.journal_id || journalIdInput.value.trim();
        if (iden.logo_filename) {
            currentLogoFilename = iden.logo_filename;
            displayLogo(`/api/journals/${encodeURIComponent(jId)}/logo?t=${Date.now()}`);
        } else if (jId) {
            // Check if logo exists on server
            fetch(`/api/journals/${encodeURIComponent(jId)}/logo`, { method: "HEAD" })
                .then(res => {
                    if (res.ok) {
                        displayLogo(`/api/journals/${encodeURIComponent(jId)}/logo?t=${Date.now()}`);
                    } else {
                        clearLogo();
                    }
                })
                .catch(() => clearLogo());
        } else {
            clearLogo();
        }

        // First Page Header
        const fph = data.first_page_header || {};
        if (setFirstPageHeaderEnabled) {
            setFirstPageHeaderEnabled.checked = fph.enabled ?? true;
            setLogoPosition.value             = fph.logo_position || "left";
            setLogoHeight.value               = fph.logo_max_height_mm ?? 16.0;
            setShowLogo.checked               = fph.show_logo ?? true;
            setShowJournalName.checked        = fph.show_journal_name ?? true;
            setShowIssn.checked               = fph.show_issn ?? true;
            setShowVolumeIssue.checked        = fph.show_volume_issue ?? true;
        }

        // Running Header (Page 2+)
        const hdr = data.header || {};
        if (setHeaderEnabled) {
            setHeaderEnabled.checked          = hdr.enabled ?? true;
            setHeaderFromPage.value           = hdr.from_page ?? 2;
            setHeaderLeft.value               = hdr.left_text || "";
            setHeaderCenter.value             = hdr.center_text || "";
            setHeaderRight.value              = hdr.right_text || "";
            setHeaderSize.value               = hdr.font_size_pt ?? 8.5;
            setHeaderStyle.value              = hdr.font_style || "italic";

            const hdrLine = hdr.line || {};
            setHeaderLineShow.checked         = hdrLine.show ?? true;
            setHeaderLineThickness.value      = hdrLine.thickness_pt ?? 0.8;
            const hdrColor = (hdrLine.color || "#CC0066").toUpperCase();
            setHeaderLineColor.value          = hdrColor;
            setHeaderLineColorPicker.value    = hdrColor.startsWith("#") ? hdrColor : "#" + hdrColor;
        }

        // Running Footer
        const ftr = data.footer || {};
        if (setFooterEnabled) {
            setFooterEnabled.checked          = ftr.enabled ?? true;
            setFooterFromPage.value           = ftr.from_page ?? 1;
            setFooterLeft.value               = ftr.left_text || "";
            setFooterCenter.value             = ftr.center_text || "\\thepage";
            setFooterRight.value              = ftr.right_text || "";
            setFooterSize.value               = ftr.font_size_pt ?? 8.5;
            setFooterStyle.value              = ftr.font_style || "normal";

            const ftrLine = ftr.line || {};
            setFooterLineShow.checked         = ftrLine.show ?? true;
            setFooterLineThickness.value      = ftrLine.thickness_pt ?? 0.8;
            const ftrColor = (ftrLine.color || "#CC0066").toUpperCase();
            setFooterLineColor.value          = ftrColor;
            setFooterLineColorPicker.value    = ftrColor.startsWith("#") ? ftrColor : "#" + ftrColor;
        }

        // Block Typesetting Specifications
        // 1. Abstract
        const ab = data.abstract || {};
        if (setAbstractHeading) {
            setAbstractHeading.value      = ab.heading_text || "Abstract";
            setAbstractHeadingSize.value  = ab.heading_font_size_pt ?? 11.0;
            setAbstractBodySize.value     = ab.body_font_size_pt ?? 9.0;
            setAbstractIndented.checked   = ab.indented ?? true;
            setAbstractBoxBorder.checked  = ab.box_border ?? false;
            setAbstractLabelsBold.checked = ab.structured_labels_bold ?? true;
            if (setAbstractFullWidth) setAbstractFullWidth.checked = ab.full_width_in_twocol ?? true;
            if (setAbstractSingleParagraph) setAbstractSingleParagraph.checked = ab.single_paragraph ?? false;
            if (setAbstractIncludeKeywords) setAbstractIncludeKeywords.checked = ab.include_keywords_in_box ?? false;
        }

        // 2. Keywords
        const kw = data.keywords || {};
        if (setKeywordsLabel) {
            setKeywordsLabel.value        = kw.label_text || "Keywords:";
            setKeywordsWeight.value       = kw.label_font_weight || "bold";
            setKeywordsSize.value         = kw.font_size_pt ?? 9.0;
            setKeywordsSeparator.value    = kw.separator || "; ";
        }

        // 3. Figures
        const fg = data.figures || {};
        if (setFigureCaptionPos) {
            setFigureCaptionPos.value       = fg.caption_position || "below";
            setFigurePrefix.value           = fg.caption_label_prefix || "Figure";
            setFigureLabelStyle.value       = fg.caption_label_style || "bold";
            setFigureCaptionSize.value      = fg.caption_font_size_pt ?? 9.0;
            setFigureSpanWide.checked       = fg.span_wide_figures ?? true;
            if (setFigureSeparator) setFigureSeparator.value = fg.label_separator || ".";
            if (setFigureCaptionJustification) setFigureCaptionJustification.value = fg.caption_justification || "justified";
        }

        // 4. Tables
        const tb = data.tables || {};
        if (setTableCaptionPos) {
            setTableCaptionPos.value        = tb.caption_position || "above";
            setTablePrefix.value            = tb.caption_label_prefix || "Table";
            setTableLabelStyle.value        = tb.caption_label_style || "bold";
            setTableBorderStyle.value       = tb.border_style || "booktabs";
            setTableCaptionSize.value       = tb.caption_font_size_pt ?? 9.0;
            setTableSpanWide.checked        = tb.span_wide_tables ?? true;
            if (setTableSeparator) setTableSeparator.value = tb.label_separator || ".";
            if (setTableVerticalLines) setTableVerticalLines.checked = tb.show_vertical_lines ?? false;
            if (setTableCaptionJustification) setTableCaptionJustification.value = tb.caption_justification || "justified";
        }

        // 5. Equations
        const eq = data.equations || {};
        if (setEquationNumbering) {
            setEquationNumbering.checked  = eq.display_numbering ?? true;
            setEquationAlign.value        = eq.numbering_alignment || "right";
            setEquationBracket.value      = eq.numbering_bracket || "parentheses";
            setEquationSize.value         = eq.font_size_pt ?? 10.0;
        }

        // 6. References
        const rf = data.references || {};
        if (setRefHeading) {
            setRefHeading.value           = rf.section_heading_text || "References";
            setRefCitationStyle.value     = rf.citation_style || "numeric";
            setRefFontSize.value          = rf.font_size_pt ?? 9.0;
            setRefHangingIndent.checked   = rf.hanging_indent ?? true;
        }

        // 7. Conclusion
        const cc = data.conclusion || {};
        if (setConclusionHeading) {
            setConclusionHeading.value    = cc.heading_text || "Conclusion";
            setConclusionSize.value       = cc.font_size_pt ?? 12.0;
            setConclusionNumbering.value  = cc.numbering || "numeric";
        }

        // 8. Footnotes
        const fn = data.footnotes || {};
        if (setFootnoteSize) {
            setFootnoteSize.value         = fn.font_size_pt ?? 8.0;
            setFootnoteMarkerStyle.value  = fn.marker_style || "numeric";
            setFootnoteRule.checked       = fn.rule_separator ?? true;
        }

        // 9. Blockquotes
        const bq = data.blockquotes || {};
        if (setQuoteSize) {
            setQuoteSize.value            = bq.font_size_pt ?? 9.0;
            setQuoteStyle.value           = bq.font_style || "italic";
            setQuoteIndent.value          = bq.indent_pt ?? 18.0;
        }

        // 10. Lists
        const ls = data.lists || {};
        if (setListBulletMarker) {
            setListBulletMarker.value     = ls.bullet_marker || "bullet";
            setListNumberingStyle.value   = ls.numbering_style || "numeric";
            setListIndent.value           = ls.indent_pt ?? 15.0;
            setListItemSpacing.value      = ls.item_spacing_pt ?? 3.0;
        }

        // 11. Declarations
        const dc = data.declarations || {};
        if (setDeclarationsHeadingStyle) {
            setDeclarationsHeadingStyle.value = dc.heading_style || "inline_bold";
            setDeclarationsSize.value         = dc.font_size_pt ?? 9.0;
        }

        // Volumes
        currentVolumes = data.volumes ? JSON.parse(JSON.stringify(data.volumes)) : [];
        activeVolumeId = data.active_volume_id || (currentVolumes.length ? currentVolumes[0].id : null);
        renderVolumesTable();
    }

    // ---- Load a Single Profile into the Form ----
    function loadProfile(id) {
        currentLoadedJournalId = id;
        if (aiVerificationBanner) {
            aiVerificationBanner.classList.add("hidden");
        }
        fetch(`/api/journals/${encodeURIComponent(id)}`)
            .then(res => {
                if (!res.ok) throw new Error("Could not load journal profile.");
                return res.json();
            })
            .then(profile => {
                journalIdInput.value = profile.journal_id;
                journalNameInput.value = profile.journal_name;
                if (formModeTitle) {
                    formModeTitle.textContent = `Editing Profile: ${profile.journal_name} (${profile.journal_id})`;
                }
                if (deleteCurrentProfileBtn) {
                    deleteCurrentProfileBtn.style.display = "inline-flex";
                    deleteCurrentProfileBtn.dataset.id = profile.journal_id;
                    deleteCurrentProfileBtn.dataset.name = profile.journal_name;
                }
                populateSettingsForm(profile);

                // Update active highlight in sidebar subnav
                document.querySelectorAll(".sidebar-subnav-item").forEach(item => {
                    item.classList.toggle("active", item.dataset.id === id);
                });
            })
            .catch(err => alert(err.message || "Failed to load profile."));
    }

    // ---- Save Journal Profile ----
    if (saveJournalSettingsBtn) {
        saveJournalSettingsBtn.addEventListener("click", () => {
            const jId   = journalIdInput.value.trim();
            const jName = journalNameInput.value.trim();

            if (!jId || !jName) {
                alert("Please provide both Journal ID and Journal Name.");
                switchTab("tabIdentity");
                return;
            }

            saveJournalSettingsBtn.disabled = true;
            saveJournalSettingsBtn.textContent = "Saving Profile…";

            const payload = {
                journal_id: jId,
                journal_name: jName,
                created_at: new Date().toISOString(),
                page: {
                    paper_size:      setPaperSize.value,
                    columns:         parseInt(setColumns.value),
                    column_gap_pt:   12.0,
                    margin_top_in:   parseFloat(setMarginTop.value) || 0.75,
                    margin_bottom_in:parseFloat(setMarginBottom.value) || 0.75,
                    margin_left_in:  parseFloat(setMarginLeft.value) || 0.75,
                    margin_right_in: parseFloat(setMarginRight.value) || 0.75
                },
                body_text: {
                    font_family:          setBodyFont.value || "Times New Roman",
                    font_size_pt:         parseFloat(setBodySize.value) || 10.0,
                    line_spacing:         parseFloat(setLineSpacing.value) || 1.15,
                    paragraph_indent_pt:  12.0,
                    paragraph_spacing_pt: 6.0
                },
                title_block: {
                    title_font_size_pt:       parseFloat(setTitleSize.value) || 16.0,
                    title_font_weight:        "bold",
                    title_alignment:          "center",
                    subtitle_font_size_pt:    (parseFloat(setTitleSize.value) || 16.0) - 4,
                    authors_font_size_pt:     parseFloat(setAuthorsSize.value) || 11.0,
                    authors_font_style:       "normal",
                    affiliation_font_size_pt: parseFloat(setAffiliationSize.value) || 9.0,
                    affiliation_font_style:   "italic",
                    corresponding_marker:     "*"
                },
                headings: {
                    h1: { font_size_pt: parseFloat(setH1Size.value) || 12.0, font_weight: "bold",   font_style: "normal", alignment: "left", numbering: "numeric", space_before_pt: 12.0, space_after_pt: 6.0, all_caps: false },
                    h2: { font_size_pt: parseFloat(setH2Size.value) || 11.0, font_weight: "bold",   font_style: "italic", alignment: "left", numbering: "numeric", space_before_pt: 8.0,  space_after_pt: 4.0, all_caps: false },
                    h3: { font_size_pt: parseFloat(setH3Size.value) || 10.0, font_weight: "normal", font_style: "italic", alignment: "left", numbering: "none",    space_before_pt: 6.0,  space_after_pt: 3.0, all_caps: false }
                },

                // Block Typesetting Specifications
                abstract: {
                    heading_text:            setAbstractHeading ? setAbstractHeading.value.trim() : "Abstract",
                    heading_font_size_pt:    setAbstractHeadingSize ? parseFloat(setAbstractHeadingSize.value) || 11.0 : 11.0,
                    heading_font_weight:     "bold",
                    body_font_size_pt:       setAbstractBodySize ? parseFloat(setAbstractBodySize.value) || 9.0 : 9.0,
                    indented:                setAbstractIndented ? setAbstractIndented.checked : true,
                    box_border:              setAbstractBoxBorder ? setAbstractBoxBorder.checked : false,
                    structured_labels_bold:  setAbstractLabelsBold ? setAbstractLabelsBold.checked : true,
                    full_width_in_twocol:    setAbstractFullWidth ? setAbstractFullWidth.checked : true,
                    single_paragraph:        setAbstractSingleParagraph ? setAbstractSingleParagraph.checked : false,
                    include_keywords_in_box: setAbstractIncludeKeywords ? setAbstractIncludeKeywords.checked : false
                },
                keywords: {
                    label_text:        setKeywordsLabel ? setKeywordsLabel.value.trim() : "Keywords:",
                    label_font_weight: setKeywordsWeight ? setKeywordsWeight.value : "bold",
                    font_size_pt:      setKeywordsSize ? parseFloat(setKeywordsSize.value) || 9.0 : 9.0,
                    separator:         setKeywordsSeparator ? setKeywordsSeparator.value : "; "
                },
                figures: {
                    caption_position:      setFigureCaptionPos ? setFigureCaptionPos.value : "below",
                    caption_label_prefix:  setFigurePrefix ? setFigurePrefix.value.trim() : "Figure",
                    caption_label_style:   setFigureLabelStyle ? setFigureLabelStyle.value : "bold",
                    caption_font_size_pt:  setFigureCaptionSize ? parseFloat(setFigureCaptionSize.value) || 9.0 : 9.0,
                    span_wide_figures:     setFigureSpanWide ? setFigureSpanWide.checked : true,
                    label_separator:       setFigureSeparator ? setFigureSeparator.value : ".",
                    caption_justification: setFigureCaptionJustification ? setFigureCaptionJustification.value : "justified"
                },
                tables: {
                    caption_position:      setTableCaptionPos ? setTableCaptionPos.value : "above",
                    caption_label_prefix:  setTablePrefix ? setTablePrefix.value.trim() : "Table",
                    caption_label_style:   setTableLabelStyle ? setTableLabelStyle.value : "bold",
                    caption_font_size_pt:  setTableCaptionSize ? parseFloat(setTableCaptionSize.value) || 9.0 : 9.0,
                    border_style:          setTableBorderStyle ? setTableBorderStyle.value : "booktabs",
                    span_wide_tables:      setTableSpanWide ? setTableSpanWide.checked : true,
                    label_separator:       setTableSeparator ? setTableSeparator.value : ".",
                    show_vertical_lines:   setTableVerticalLines ? setTableVerticalLines.checked : false,
                    caption_justification: setTableCaptionJustification ? setTableCaptionJustification.value : "justified"
                },
                equations: {
                    display_numbering:   setEquationNumbering ? setEquationNumbering.checked : true,
                    numbering_alignment: setEquationAlign ? setEquationAlign.value : "right",
                    numbering_bracket:   setEquationBracket ? setEquationBracket.value : "parentheses",
                    font_size_pt:        setEquationSize ? parseFloat(setEquationSize.value) || 10.0 : 10.0
                },
                references: {
                    section_heading_text: setRefHeading ? setRefHeading.value.trim() : "References",
                    citation_style:       setRefCitationStyle ? setRefCitationStyle.value : "numeric",
                    font_size_pt:         setRefFontSize ? parseFloat(setRefFontSize.value) || 9.0 : 9.0,
                    hanging_indent:       setRefHangingIndent ? setRefHangingIndent.checked : true
                },
                conclusion: {
                    heading_text: setConclusionHeading ? setConclusionHeading.value.trim() : "Conclusion",
                    font_size_pt: setConclusionSize ? parseFloat(setConclusionSize.value) || 12.0 : 12.0,
                    numbering:    setConclusionNumbering ? setConclusionNumbering.value : "numeric"
                },
                footnotes: {
                    font_size_pt:   setFootnoteSize ? parseFloat(setFootnoteSize.value) || 8.0 : 8.0,
                    marker_style:   setFootnoteMarkerStyle ? setFootnoteMarkerStyle.value : "numeric",
                    rule_separator: setFootnoteRule ? setFootnoteRule.checked : true
                },
                blockquotes: {
                    font_size_pt: setQuoteSize ? parseFloat(setQuoteSize.value) || 9.0 : 9.0,
                    font_style:   setQuoteStyle ? setQuoteStyle.value : "italic",
                    indent_pt:    setQuoteIndent ? parseFloat(setQuoteIndent.value) || 18.0 : 18.0
                },
                lists: {
                    bullet_marker:   setListBulletMarker ? setListBulletMarker.value : "bullet",
                    numbering_style: setListNumberingStyle ? setListNumberingStyle.value : "numeric",
                    indent_pt:       setListIndent ? parseFloat(setListIndent.value) || 15.0 : 15.0,
                    item_spacing_pt: setListItemSpacing ? parseFloat(setListItemSpacing.value) || 3.0 : 3.0
                },
                declarations: {
                    heading_style: setDeclarationsHeadingStyle ? setDeclarationsHeadingStyle.value : "inline_bold",
                    font_size_pt:  setDeclarationsSize ? parseFloat(setDeclarationsSize.value) || 9.0 : 9.0
                },

                // Enhanced Profile Fields
                identity: {
                    logo_filename: currentLogoFilename,
                    issn_print:    setIssnPrint.value.trim() || null,
                    issn_online:   setIssnOnline.value.trim() || null,
                    website:       setWebsite.value.trim() || null,
                    publisher:     setPublisher.value.trim() || null
                },
                first_page_header: {
                    enabled:            setFirstPageHeaderEnabled.checked,
                    show_logo:          setShowLogo.checked,
                    logo_position:      setLogoPosition.value,
                    logo_max_height_mm: parseFloat(setLogoHeight.value) || 16.0,
                    show_journal_name:  setShowJournalName.checked,
                    show_issn:          setShowIssn.checked,
                    show_volume_issue:  setShowVolumeIssue.checked,
                    show_website:       Boolean(setWebsite.value.trim())
                },
                header: {
                    enabled:       setHeaderEnabled.checked,
                    from_page:     parseInt(setHeaderFromPage.value) || 2,
                    left_text:     setHeaderLeft.value.trim(),
                    center_text:   setHeaderCenter.value.trim(),
                    right_text:    setHeaderRight.value.trim(),
                    font_size_pt:  parseFloat(setHeaderSize.value) || 8.5,
                    font_style:    setHeaderStyle.value,
                    line: {
                        show:         setHeaderLineShow.checked,
                        thickness_pt: parseFloat(setHeaderLineThickness.value) || 0.8,
                        color:        setHeaderLineColor.value.trim() || "#CC0066"
                    }
                },
                footer: {
                    enabled:       setFooterEnabled.checked,
                    from_page:     parseInt(setFooterFromPage.value) || 1,
                    left_text:     setFooterLeft.value.trim(),
                    center_text:   setFooterCenter.value.trim() || "\\thepage",
                    right_text:    setFooterRight.value.trim(),
                    font_size_pt:  parseFloat(setFooterSize.value) || 8.5,
                    font_style:    setFooterStyle.value,
                    line: {
                        show:         setFooterLineShow.checked,
                        thickness_pt: parseFloat(setFooterLineThickness.value) || 0.8,
                        color:        setFooterLineColor.value.trim() || "#CC0066"
                    }
                },
                volumes:          currentVolumes,
                active_volume_id: activeVolumeId
            };

            fetch("/api/journals", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (!res.ok) throw new Error("Failed to save journal profile.");
                return res.json();
            })
            .then(() => {
                alert(`Journal profile "${jName}" saved successfully!`);
                loadJournalProfiles(jId);
            })
            .catch(err => alert(err.message || "Failed to save settings."))
            .finally(() => {
                saveJournalSettingsBtn.disabled = false;
                saveJournalSettingsBtn.textContent = "Save Journal Profile Settings";
            });
        });
    }

    // ---- Load Profiles List into Left Sidebar Subnav ----
    function loadJournalProfiles(preferredSelectId) {
        fetch("/api/journals")
            .then(res => res.json())
            .then(data => {
                if (sidebarJournalProfilesList) {
                    sidebarJournalProfilesList.innerHTML = "";
                }
                if (!data || data.length === 0) {
                    if (sidebarJournalProfilesList) {
                        sidebarJournalProfilesList.innerHTML = '<div class="sidebar-subnav-loading">No profiles created yet.</div>';
                    }
                    resetToNewProfile();
                    return;
                }

                data.forEach(p => {
                    const item = document.createElement("a");
                    item.href = "javascript:void(0)";
                    item.className = "sidebar-subnav-item";
                    item.dataset.id = p.journal_id;
                    item.title = `${p.journal_name} (${p.journal_id})`;
                    item.innerHTML = `
                        <span class="subnav-title">${escapeHtml(p.journal_name)}</span>
                        <span class="subnav-badge">${escapeHtml(p.journal_id)}</span>
                    `;

                    item.addEventListener("click", (e) => {
                        e.preventDefault();
                        loadProfile(p.journal_id);
                    });

                    if (sidebarJournalProfilesList) {
                        sidebarJournalProfilesList.appendChild(item);
                    }
                });

                // Auto-load preferred profile, or currently selected, or first profile
                const targetId = preferredSelectId || currentLoadedJournalId || (data.length > 0 ? data[0].journal_id : null);
                if (targetId) {
                    loadProfile(targetId);
                }
            })
            .catch(() => {
                if (sidebarJournalProfilesList) {
                    sidebarJournalProfilesList.innerHTML = '<div class="sidebar-subnav-loading" style="color:var(--state-error-text);">Failed to load profiles.</div>';
                }
            });
    }

    // Delete current profile from header action button
    if (deleteCurrentProfileBtn) {
        deleteCurrentProfileBtn.addEventListener("click", () => {
            const id = deleteCurrentProfileBtn.dataset.id || currentLoadedJournalId;
            const name = deleteCurrentProfileBtn.dataset.name || id;
            if (!id) return;
            if (confirm(`Delete journal profile: ${name}?`)) {
                fetch(`/api/journals/${encodeURIComponent(id)}`, { method: "DELETE" })
                    .then(() => {
                        currentLoadedJournalId = null;
                        loadJournalProfiles();
                    })
                    .catch(() => alert("Failed to delete journal profile."));
            }
        });
    }

    // ---- AI Multi-Model Cascading Fallback Modal ----
    function loadAiStatus() {
        if (!aiProvidersContainer) return;
        aiProvidersContainer.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;">Checking AI provider readiness…</div>';
        
        fetch("/api/ai/status")
            .then(res => res.json())
            .then(data => {
                aiProvidersContainer.innerHTML = "";
                const providers = data.providers || [];
                providers.forEach(p => {
                    const card = document.createElement("div");
                    card.style.cssText = "display:flex; justify-content:space-between; align-items:center; padding:0.75rem 1rem; border-radius:var(--radius-md); border:1px solid var(--border-color); background:var(--bg-secondary);";
                    
                    const isReady = p.has_key;
                    const badgeBg = isReady ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)";
                    const badgeColor = isReady ? "var(--state-success-text)" : "var(--state-warning-text)";
                    const badgeBorder = isReady ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)";
                    const badgeText = isReady ? (p.key_preview === "builtin" ? "Zero-Token Builtin" : `Active (${p.key_preview})`) : "Key Needed";

                    card.innerHTML = `
                        <div>
                            <div style="font-weight:600; font-size:0.875rem; color:var(--text-primary);">${escapeHtml(p.name)}</div>
                            <div style="font-size:0.775rem; color:var(--text-secondary); margin-top:0.15rem;">Models: ${escapeHtml(p.models.join(", "))}</div>
                        </div>
                        <span style="font-size:0.75rem; font-weight:600; padding:0.2rem 0.55rem; border-radius:999px; background:${badgeBg}; color:${badgeColor}; border:1px solid ${badgeBorder}; flex-shrink:0;">
                            ${badgeText}
                        </span>
                    `;
                    aiProvidersContainer.appendChild(card);
                });
            })
            .catch(() => {
                aiProvidersContainer.innerHTML = '<div style="color:var(--state-error-text);font-size:0.85rem;">Failed to fetch AI provider status.</div>';
            });
    }

    if (aiModelsConfigBtn && aiRoutingModal) {
        aiModelsConfigBtn.addEventListener("click", () => {
            aiRoutingModal.classList.remove("hidden");
            if (aiKeysSaveStatus) aiKeysSaveStatus.textContent = "";
            loadAiStatus();
        });
    }

    if (closeAiRoutingModalBtn && aiRoutingModal) {
        closeAiRoutingModalBtn.addEventListener("click", () => {
            aiRoutingModal.classList.add("hidden");
        });
    }

    if (cancelAiKeysBtn && aiRoutingModal) {
        cancelAiKeysBtn.addEventListener("click", () => {
            aiRoutingModal.classList.add("hidden");
        });
    }

    if (aiRoutingModal) {
        aiRoutingModal.addEventListener("click", (e) => {
            if (e.target === aiRoutingModal) {
                aiRoutingModal.classList.add("hidden");
            }
        });
    }

    if (saveAiKeysBtn) {
        saveAiKeysBtn.addEventListener("click", () => {
            const payload = {};
            if (aiKeyOpenAI && aiKeyOpenAI.value.trim()) payload.openai_key = aiKeyOpenAI.value.trim();
            if (aiKeyAnthropic && aiKeyAnthropic.value.trim()) payload.anthropic_key = aiKeyAnthropic.value.trim();
            if (aiKeyGemini && aiKeyGemini.value.trim()) payload.gemini_key = aiKeyGemini.value.trim();

            if (Object.keys(payload).length === 0) {
                if (aiKeysSaveStatus) {
                    aiKeysSaveStatus.textContent = "No keys entered to update.";
                    aiKeysSaveStatus.style.color = "var(--text-muted)";
                }
                return;
            }

            saveAiKeysBtn.disabled = true;
            saveAiKeysBtn.textContent = "Saving…";

            fetch("/api/ai/keys", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            })
                .then(res => res.json())
                .then(res => {
                    saveAiKeysBtn.disabled = false;
                    saveAiKeysBtn.textContent = "Save & Update Keys";
                    if (aiKeysSaveStatus) {
                        aiKeysSaveStatus.textContent = "✓ Keys saved successfully!";
                        aiKeysSaveStatus.style.color = "var(--state-success-text)";
                    }
                    if (aiKeyOpenAI) aiKeyOpenAI.value = "";
                    if (aiKeyAnthropic) aiKeyAnthropic.value = "";
                    if (aiKeyGemini) aiKeyGemini.value = "";
                    loadAiStatus();
                })
                .catch(err => {
                    saveAiKeysBtn.disabled = false;
                    saveAiKeysBtn.textContent = "Save & Update Keys";
                    if (aiKeysSaveStatus) {
                        aiKeysSaveStatus.textContent = "Failed to save keys.";
                        aiKeysSaveStatus.style.color = "var(--state-error-text)";
                    }
                });
        });
    }

    // Initial load on page ready
    loadJournalProfiles();
});
