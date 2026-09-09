/**
 * editor.js — Sūtra Press Manuscript Structure Review (Step 1)
 *
 * In-Page Manuscript Document & Visual Block Identification
 *
 * Features:
 * 1. Renders the uploaded manuscript as an authentic academic document sheet.
 * 2. Visually marks every element with its Block Identification tag ([TITLE], [AUTHORS],
 *    [ABSTRACT], [HEADING 1], [PARAGRAPH], [FIGURE], [TABLE], etc.) and verification state.
 * 3. Synchronized Split View: clicking any block highlights it in the manuscript and
 *    opens its controls in the right-hand Inspector pane.
 * 4. Document Structure Outline (Mini-Map) with click-to-scroll navigation.
 * 5. Instant retagging, splitting, merging, inline text editing, and tag confirmation.
 * 6. View Mode Switcher: Split View, Full Manuscript, and Outline Only.
 */

document.addEventListener("DOMContentLoaded", () => {
    if (!requireAuth()) return;
    initSharedNavbar();

    // ---- Extract project_id from URL /editor/{project_id} ----
    const pathParts = window.location.pathname.split("/").filter(Boolean);
    let projectId = null;
    const editorIdx = pathParts.indexOf("editor");
    if (editorIdx !== -1 && pathParts.length > editorIdx + 1) {
        projectId = pathParts[editorIdx + 1];
    } else {
        projectId = pathParts[pathParts.length - 1];
    }

    if (!projectId) {
        const titleEl = document.getElementById("editorManuscriptTitle");
        if (titleEl) titleEl.textContent = "No project ID provided";
        return;
    }

    let currentProject = null;
    let selectedBlockId = null;
    let selectedBlockIds = new Set();  // Multi-select mode
    let activeFilter = "all";
    let currentViewMode = "split";

    // DOM references
    const editorManuscriptTitle    = document.getElementById("editorManuscriptTitle");
    const triageSummaryBanner      = document.getElementById("triageSummaryBanner");
    const manuscriptDocumentCanvas = document.getElementById("manuscriptDocumentCanvas");
    const manuscriptScrollArea     = document.getElementById("manuscriptScrollArea");
    const step1SplitGrid           = document.getElementById("step1SplitGrid");
    const filterChipsGroup         = document.getElementById("filterChipsGroup");
    const aiIdentifyBtn            = document.getElementById("aiIdentifyBtn");
    const confirmAllBtn            = document.getElementById("confirmAllBtn");
    const addNewBlockBtn           = document.getElementById("addNewBlockBtn");
    const deleteProjectBtn         = document.getElementById("deleteProjectBtn");
    const proceedToTypesetBtn      = document.getElementById("proceedToTypesetBtn");
    const reIdentifyBtn             = document.getElementById("reIdentifyBtn");
    const footerProceedBtn         = document.getElementById("footerProceedBtn");
    const step2Link                = document.getElementById("step2Link");
    const footerStatusText         = document.getElementById("footerStatusText");
    const downloadDocxBtn          = document.getElementById("downloadDocxBtn");

    // Inspector references
    const inspectorBlockId     = document.getElementById("inspectorBlockId");
    const inspectorStateBadge  = document.getElementById("inspectorStateBadge");
    const inspectorWarningBox  = document.getElementById("inspectorWarningBox");
    const inspectorWarningText = document.getElementById("inspectorWarningText");
    const inspectorRetagSelect = document.getElementById("inspectorRetagSelect");
    const inspectorTextInput   = document.getElementById("inspectorTextInput");
    const inspectorConfirmBtn  = document.getElementById("inspectorConfirmBtn");
    const inspectorSplitBtn    = document.getElementById("inspectorSplitBtn");
    const inspectorMergeBtn    = document.getElementById("inspectorMergeBtn");
    const inspectorDeleteBtn   = document.getElementById("inspectorDeleteBtn");
    const structureOutlineList = document.getElementById("structureOutlineList");
    const outlineBlockCount    = document.getElementById("outlineBlockCount");

    // View Mode buttons
    const viewModeGroup = document.getElementById("viewModeGroup");

    // Counters
    const countAll         = document.getElementById("countAll");
    const countAbstract    = document.getElementById("countAbstract");
    const countHeadings    = document.getElementById("countHeadings");
    const countParagraphs  = document.getElementById("countParagraphs");
    const countFigsTables  = document.getElementById("countFigsTables");
    const countNeedsReview = document.getElementById("countNeedsReview");
    const countUnapproved  = document.getElementById("countUnapproved");
    const filterAiChangesBtn = document.getElementById("filterAiChangesBtn");
    const countAiChanges   = document.getElementById("countAiChanges");
    const uploadReferencePdfBtn = document.getElementById("uploadReferencePdfBtn");
    const uploadReferencePdfInput = document.getElementById("uploadReferencePdfInput");

    // Update navigation links for this project
    const typesetUrl = `/editor/${projectId}/typeset`;
    if (proceedToTypesetBtn) proceedToTypesetBtn.href = typesetUrl;
    if (footerProceedBtn)    footerProceedBtn.href    = typesetUrl;
    if (step2Link)           step2Link.href           = typesetUrl;
    if (downloadDocxBtn)     downloadDocxBtn.href     = `/project/${projectId}/docx`;

    // Helper: escape HTML
    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // Helper: format tag label
    function formatBlockType(type) {
        if (!type) return "BLOCK";
        const map = {
            "title": "TITLE",
            "authors": "AUTHORS",
            "affiliations": "AFFILIATIONS",
            "abstract": "ABSTRACT",
            "heading_l1": "HEADING 1",
            "heading_l2": "HEADING 2",
            "heading_l3": "HEADING 3",
            "paragraph": "PARAGRAPH",
            "figure": "FIGURE",
            "table": "TABLE",
            "equation": "EQUATION",
            "footnote": "FOOTNOTE",
            "blockquote": "QUOTE",
            "list": "LIST",
            "reference_list": "REFERENCES",
            "unrecognized": "UNRECOGNIZED"
        };
        return map[type] || type.replace(/_/g, " ").toUpperCase();
    }

    function getTagCategory(type) {
        if (!type) return "paragraph";
        if (type.startsWith("heading")) return "heading";
        if (type === "reference_list") return "reference";
        return type;
    }

    function formatStateLabel(block) {
        if (block.is_flagged_manual) return "FLAGGED";
        if (block.state === "needs_review") return "⚠ NEEDS REVIEW";
        if (block.state === "unrecognized") return "❓ UNRECOGNIZED";
        return "✓ CONFIRMED";
    }

    // Helper: extract plain text from diverse block content schemas
    function getBlockPlainText(block) {
        if (!block || block.content === undefined || block.content === null) return "";
        const c = block.content;
        if (typeof c === "string") return c;
        if (typeof c === "number" || typeof c === "boolean") return String(c);
        if (Array.isArray(c)) {
            return c.map(item => {
                if (typeof item === "string") return item;
                if (Array.isArray(item)) {
                    return item.map(run => (run && typeof run === "object" ? (run.text || "") : String(run || ""))).join("");
                }
                if (item && typeof item === "object") {
                    return item.text || item.content_text || (item.given_name ? `${item.given_name} ${item.family_name || ''}`.trim() : "") || (item.institution || "");
                }
                return "";
            }).filter(Boolean).join("\n\n");
        }
        if (typeof c === "object") {
            if (c.content_text) return c.content_text;
            if (c.text) return c.text;
            if (c.paragraphs && Array.isArray(c.paragraphs)) {
                return c.paragraphs.map(p => {
                    if (Array.isArray(p.content)) return p.content.map(r => r.text || "").join("");
                    return typeof p === "string" ? p : "";
                }).join("\n\n");
            }
            if (c.caption) {
                if (Array.isArray(c.caption)) return c.caption.map(r => r.text || "").join("");
                return String(c.caption);
            }
            if (c.latex_source) return c.latex_source;
        }
        return "";
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
                    editorManuscriptTitle.textContent = `Structure Review: ${filename}`;
                }
                document.title = `${filename} — Manuscript Structure Review`;

                // Select first block by default if available
                const blocks = currentProject.blocks || [];
                if (blocks.length > 0 && !selectedBlockId) {
                    selectedBlockId = blocks[0].id;
                }

                renderBlocks();
            })
            .catch(err => {
                console.error("Failed to load project:", err);
                if (editorManuscriptTitle) editorManuscriptTitle.textContent = "Failed to load project";
                if (manuscriptDocumentCanvas) {
                    manuscriptDocumentCanvas.innerHTML = `
                        <div style="padding: 2.5rem; text-align: center; color: var(--state-error-text);">
                            <h3 style="margin-bottom: 0.5rem;">Could not load manuscript</h3>
                            <p style="color: var(--text-secondary);">${escapeHtml(err.message)}</p>
                            <a href="/" class="btn btn-outline btn-sm" style="margin-top: 1rem;">Back to Dashboard</a>
                        </div>
                    `;
                }
                if (triageSummaryBanner) {
                    triageSummaryBanner.className = "triage-summary-box error";
                    triageSummaryBanner.textContent = `Error: ${err.message}`;
                }
            });
    }

    // ---- View Mode Switcher ----
    if (viewModeGroup) {
        viewModeGroup.addEventListener("click", (e) => {
            const btn = e.target.closest(".view-mode-btn");
            if (!btn) return;
            viewModeGroup.querySelectorAll(".view-mode-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentViewMode = btn.dataset.view;

            if (step1SplitGrid) {
                step1SplitGrid.classList.remove("view-manuscript-only", "view-outline-only");
                if (currentViewMode === "manuscript") {
                    step1SplitGrid.classList.add("view-manuscript-only");
                } else if (currentViewMode === "outline") {
                    step1SplitGrid.classList.add("view-outline-only");
                }
            }
        });
    }

    // ---- Filter Chips Handling ----
    if (filterChipsGroup) {
        filterChipsGroup.addEventListener("click", (e) => {
            const chip = e.target.closest(".filter-chip");
            if (!chip) return;
            filterChipsGroup.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            activeFilter = chip.dataset.filter || "all";
            renderBlocks();
        });
    }

    // ---- Main Render Function ----
    function renderBlocks() {
        if (!currentProject || !manuscriptDocumentCanvas) return;

        const blocks = currentProject.blocks || [];
        let unrecognizedCount = 0;
        let needsReviewCount  = 0;
        let abstractCount     = 0;
        let headingCount      = 0;
        let paragraphCount    = 0;
        let figTableCount     = 0;
        let unapprovedCount   = 0;
        let aiChangesCount    = 0;

        // Count categories
        blocks.forEach(b => {
            if (b.type === "abstract") abstractCount++;
            if (b.type && b.type.startsWith("heading_")) headingCount++;
            if (b.type === "paragraph") paragraphCount++;
            if (b.type === "figure" || b.type === "table") figTableCount++;

            if (b.ai_change && !b.ai_change.reviewed) aiChangesCount++;

            if (b.type === "unrecognized" && !b.is_flagged_manual) unrecognizedCount++;
            else if (b.state === "needs_review") needsReviewCount++;
            if (!b.is_user_confirmed) unapprovedCount++;
        });

        // Update counts in filter chips
        if (countAll)         countAll.textContent         = blocks.length;
        if (countAbstract)    countAbstract.textContent    = abstractCount;
        if (countHeadings)    countHeadings.textContent    = headingCount;
        if (countParagraphs)  countParagraphs.textContent  = paragraphCount;
        if (countFigsTables)  countFigsTables.textContent  = figTableCount;
        if (countNeedsReview) countNeedsReview.textContent = (unrecognizedCount + needsReviewCount);
        if (countUnapproved)  countUnapproved.textContent  = unapprovedCount;
        if (countAiChanges)   countAiChanges.textContent   = aiChangesCount;
        if (filterAiChangesBtn) {
            filterAiChangesBtn.style.display = aiChangesCount > 0 ? "inline-flex" : "none";
        }
        if (outlineBlockCount) outlineBlockCount.textContent = `${blocks.length} blocks`;

        // 1. Render In-Page Manuscript Document Canvas
        renderManuscriptCanvas(blocks);

        // 2. Render Structure Outline
        renderStructureOutline(blocks);

        // 3. Update Active Block Inspector
        updateInspectorDetails();

        // 4. Update Triage Summary Banner
        if (triageSummaryBanner) {
            if (unrecognizedCount > 0) {
                triageSummaryBanner.className = "triage-summary-box error";
                triageSummaryBanner.style.cssText = "background:var(--state-error-bg);color:var(--state-error-text);border-color:var(--state-error-border);";
                triageSummaryBanner.textContent = `Structure Alert: ${unrecognizedCount} Unrecognized block(s) detected. Please assign tags before typesetting.`;
            } else if (needsReviewCount > 0) {
                triageSummaryBanner.className = "triage-summary-box warn";
                triageSummaryBanner.style.cssText = "background:var(--state-warn-bg);color:var(--state-warn-text);border-color:var(--state-warn-border);";
                triageSummaryBanner.textContent = `Attention Needed: ${needsReviewCount} block(s) flagged for review. Verify markings below.`;
            } else {
                triageSummaryBanner.className = "triage-summary-box clean";
                triageSummaryBanner.style.cssText = "background:var(--state-confirmed-bg);color:var(--state-confirmed-text);border-color:var(--state-confirmed-border);";
                triageSummaryBanner.textContent = "✓ All block tags are verified. Structure review is complete and ready for typesetting.";
            }
        }

        if (footerStatusText) {
            if (unrecognizedCount > 0 || needsReviewCount > 0) {
                footerStatusText.textContent = `${unrecognizedCount + needsReviewCount} block(s) pending verification`;
            } else {
                footerStatusText.textContent = `All ${blocks.length} blocks verified & confirmed`;
            }
        }
    }

    // ---- Render Manuscript Canvas ----
    function renderManuscriptCanvas(blocks) {
        // Preserve scroll position across re-renders
        const scrollContainer = manuscriptScrollArea || manuscriptDocumentCanvas.parentElement;
        const savedScroll = scrollContainer ? scrollContainer.scrollTop : 0;

        manuscriptDocumentCanvas.innerHTML = "";

        // Filter blocks
        const visibleBlocks = blocks.filter(b => {
            if (activeFilter === "all") return true;
            if (activeFilter === "ai_changes") return b.ai_change && !b.ai_change.reviewed;
            if (activeFilter === "abstract") return b.type === "abstract";
            if (activeFilter === "heading") return b.type && b.type.startsWith("heading_");
            if (activeFilter === "paragraph") return b.type === "paragraph";
            if (activeFilter === "figure_table") return b.type === "figure" || b.type === "table";
            if (activeFilter === "needs_review") return b.state === "needs_review" || (b.type === "unrecognized" && !b.is_flagged_manual);
            if (activeFilter === "unapproved") return !b.is_user_confirmed;
            return true;
        });

        if (visibleBlocks.length === 0) {
            const emptyEl = document.createElement("div");
            emptyEl.style.cssText = "padding: 3rem; text-align: center; color: var(--text-secondary);";
            emptyEl.innerHTML = `<p style="font-weight:600;">No blocks match the "${escapeHtml(activeFilter)}" filter.</p><p style="font-size:0.85rem;color:var(--text-muted);">Select "All" to view the full manuscript.</p>`;
            manuscriptDocumentCanvas.appendChild(emptyEl);
            return;
        }

        visibleBlocks.forEach((block) => {
            const blockEl = document.createElement("div");
            blockEl.className = `manuscript-block block-${block.type} state-${block.state || "confirmed"}`;
            if (block.id === selectedBlockId || selectedBlockIds.has(block.id)) {
                blockEl.classList.add("selected");
            }
            blockEl.dataset.blockId = block.id;

            // Block Identification Badge
            const tagBadge = document.createElement("div");
            tagBadge.className = `manuscript-tag-badge tag-badge-${getTagCategory(block.type)}`;
            tagBadge.innerHTML = `
                <span>${formatBlockType(block.type)}</span>
                <span class="manuscript-status-badge status-${block.state || 'confirmed'}">${formatStateLabel(block)}</span>
            `;
            blockEl.appendChild(tagBadge);

            // If block has an unreviewed AI change, render the AI Change Badge
            if (block.ai_change && !block.ai_change.reviewed) {
                blockEl.classList.add("ai-changed-block");
                const aiBadge = document.createElement("div");
                aiBadge.className = "ai-change-badge";
                aiBadge.innerHTML = `
                    <span class="ai-badge-icon">🤖</span>
                    <span class="ai-badge-text">
                        AI Changed: <strong style="text-decoration:line-through;color:var(--text-muted);">${escapeHtml(formatBlockType(block.ai_change.old_type))}</strong> → <strong style="color:var(--brand-indigo);">${escapeHtml(formatBlockType(block.ai_change.new_type))}</strong>
                    </span>
                    <span class="ai-badge-reason">${escapeHtml(block.ai_change.reason || "")}</span>
                    <div class="ai-badge-actions">
                        <button type="button" class="btn-accept-ai" data-block-id="${block.id}" title="Accept AI classification change">✓ Accept</button>
                        <button type="button" class="btn-reject-ai" data-block-id="${block.id}" title="Revert to original type (${block.ai_change.old_type})">✗ Revert</button>
                    </div>
                `;
                const acceptBtn = aiBadge.querySelector(".btn-accept-ai");
                const rejectBtn = aiBadge.querySelector(".btn-reject-ai");
                if (acceptBtn) {
                    acceptBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        handleAcceptAi(block);
                    });
                }
                if (rejectBtn) {
                    rejectBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        handleRejectAi(block);
                    });
                }
                blockEl.appendChild(aiBadge);
            }

            // Render Content by Type
            const plainText = getBlockPlainText(block);

            if (block.type === "title") {
                const titleEl = document.createElement("h1");
                titleEl.className = "manuscript-title-text";
                titleEl.contentEditable = "true";
                titleEl.textContent = plainText || "Untitled Manuscript";
                titleEl.onblur = (e) => handleTextUpdate(block, e.target.textContent.trim());
                blockEl.appendChild(titleEl);

            } else if (block.type === "authors") {
                const authEl = document.createElement("div");
                authEl.className = "manuscript-authors-text";
                const authorsList = Array.isArray(block.content) ? block.content : [];
                if (authorsList.length > 0) {
                    authEl.innerHTML = authorsList.map(a => {
                        if (typeof a === "string") return escapeHtml(a);
                        const name = `${a.given_name || ''} ${a.family_name || ''}`.trim() || a.text || 'Author';
                        const affStr = a.affiliations && a.affiliations.length ? `<sup>${a.affiliations.join(',')}</sup>` : '';
                        return `${escapeHtml(name)}${affStr}`;
                    }).join(", ");
                } else {
                    authEl.innerHTML = `<span style="color:var(--text-muted);font-style:italic;">${escapeHtml(plainText || "(No authors parsed)")}</span>`;
                }
                blockEl.appendChild(authEl);

            } else if (block.type === "affiliations") {
                const affEl = document.createElement("div");
                affEl.className = "manuscript-affiliations-text";
                const affList = Array.isArray(block.content) ? block.content : [];
                if (affList.length > 0) {
                    affEl.innerHTML = affList.map(a => {
                        if (typeof a === "string") return escapeHtml(a);
                        return `<sup>${a.id || ''}</sup> ${escapeHtml(a.institution || a.department || a.text || '')}`;
                    }).join("<br>");
                } else {
                    affEl.innerHTML = `<span style="color:var(--text-muted);font-style:italic;">${escapeHtml(plainText || "(No affiliations parsed)")}</span>`;
                }
                blockEl.appendChild(affEl);

            } else if (block.type === "abstract") {
                const abstractBox = document.createElement("div");
                abstractBox.className = "manuscript-abstract-container";
                abstractBox.innerHTML = `<div class="manuscript-abstract-title">Abstract</div>`;
                const abstractText = document.createElement("div");
                abstractText.contentEditable = "true";
                abstractText.style.outline = "none";
                abstractText.textContent = plainText || "(Empty Abstract)";
                abstractText.onblur = (e) => handleTextUpdate(block, e.target.textContent.trim());
                abstractBox.appendChild(abstractText);
                blockEl.appendChild(abstractBox);

            } else if (block.type === "heading_l1") {
                const h1El = document.createElement("h2");
                h1El.className = "manuscript-heading-l1-text";
                h1El.contentEditable = "true";
                h1El.textContent = plainText || "Heading 1";
                h1El.onblur = (e) => handleTextUpdate(block, e.target.textContent.trim());
                blockEl.appendChild(h1El);

            } else if (block.type === "heading_l2") {
                const h2El = document.createElement("h3");
                h2El.className = "manuscript-heading-l2-text";
                h2El.contentEditable = "true";
                h2El.textContent = plainText || "Heading 2";
                h2El.onblur = (e) => handleTextUpdate(block, e.target.textContent.trim());
                blockEl.appendChild(h2El);

            } else if (block.type === "heading_l3") {
                const h3El = document.createElement("h4");
                h3El.className = "manuscript-heading-l3-text";
                h3El.contentEditable = "true";
                h3El.textContent = plainText || "Heading 3";
                h3El.onblur = (e) => handleTextUpdate(block, e.target.textContent.trim());
                blockEl.appendChild(h3El);

            } else if (block.type === "paragraph") {
                const pEl = document.createElement("p");
                pEl.className = "manuscript-p-text";
                pEl.contentEditable = "true";
                if (plainText && plainText !== "(Empty paragraph)") {
                    pEl.textContent = plainText;
                } else {
                    pEl.textContent = "";
                    pEl.setAttribute("data-placeholder", "(Empty paragraph)");
                    pEl.classList.add("is-empty-placeholder");
                }
                pEl.onblur = (e) => handleTextUpdate(block, e.target.textContent.trim());
                pEl.oninput = (e) => {
                    if (e.target.textContent.trim()) {
                        e.target.classList.remove("is-empty-placeholder");
                    } else {
                        e.target.classList.add("is-empty-placeholder");
                    }
                };
                blockEl.appendChild(pEl);

            } else if (block.type === "figure") {
                const figBox = document.createElement("div");
                figBox.className = "manuscript-figure-box";
                const fig = block.content || {};
                const captionText = Array.isArray(fig.caption) ? fig.caption.map(c => c.text || "").join("") : (fig.caption || "");
                const imageRef = fig.image_ref || "";
                const imgSrc = imageRef ? `/project/${currentProject.id}/media/${imageRef}` : "";
                figBox.innerHTML = `
                    ${imgSrc ? `<img src="${escapeHtml(imgSrc)}" alt="${escapeHtml(fig.alt_text || captionText || 'Figure')}" class="manuscript-figure-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-flex';">` : ''}
                    <div class="manuscript-figure-placeholder" style="${imgSrc ? 'display:none;' : ''} padding: 1.5rem; background: #EEF2FF; border-radius: 6px; display: inline-flex; align-items: center; gap: 0.5rem; color: var(--brand-indigo); font-size: 0.85rem; font-weight: 600;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                        <span>[Figure: ${escapeHtml(imageRef || 'Embedded Image')}]</span>
                    </div>
                    <figcaption class="manuscript-figure-caption" contenteditable="true">
                        ${escapeHtml(captionText || 'Figure Caption (Click to edit)')}
                    </figcaption>
                `;
                const figCaption = figBox.querySelector("figcaption");
                if (figCaption) {
                    figCaption.onblur = (e) => {
                        const newCap = e.target.textContent.trim();
                        fig.caption = [{ text: newCap, bold: false, italic: false }];
                        block.state = "confirmed";
                        saveProjectUpdates();
                    };
                }
                blockEl.appendChild(figBox);

            } else if (block.type === "table") {
                const tblBox = document.createElement("div");
                tblBox.className = "manuscript-table-box";
                const tbl = block.content || {};
                const captionText = Array.isArray(tbl.caption) ? tbl.caption.map(c => c.text || "").join("") : (tbl.caption || "Table");
                const headerRowCount = tbl.header_rows || 0;
                let rowsHtml = "";
                const rows = tbl.rows || [];
                if (rows.length > 0) {
                    rows.forEach((r, rIdx) => {
                        // Each row is an array of cell objects (TableCell)
                        const rowCells = Array.isArray(r) ? r : (r.cells || []);
                        let cellsHtml = "";
                        rowCells.forEach(cell => {
                            const isHdr = cell.is_header || rIdx < headerRowCount;
                            const cellTag = isHdr ? "th" : "td";
                            // Extract text from cell.content (array of InlineRun) or cell.text
                            let cellText = "";
                            if (Array.isArray(cell.content)) {
                                cellText = cell.content.map(run => (run && typeof run === 'object') ? (run.text || '') : String(run || '')).join("");
                            } else if (cell.text !== undefined) {
                                cellText = cell.text;
                            }
                            const cs = cell.colspan && cell.colspan > 1 ? ` colspan="${cell.colspan}"` : "";
                            const rs = cell.rowspan && cell.rowspan > 1 ? ` rowspan="${cell.rowspan}"` : "";
                            cellsHtml += `<${cellTag}${cs}${rs}>${escapeHtml(cellText.trim())}</${cellTag}>`;
                        });
                        rowsHtml += `<tr>${cellsHtml}</tr>`;
                    });
                } else {
                    rowsHtml = `<tr><td style="color:var(--text-muted);font-style:italic;">No table data parsed</td></tr>`;
                }
                let footnotesHtml = "";
                if (tbl.footnotes && tbl.footnotes.length > 0) {
                    footnotesHtml = `<div class="manuscript-table-footnotes" style="font-size:0.8rem;color:var(--text-secondary);margin-top:0.4rem;font-style:italic;">${tbl.footnotes.map(fn => escapeHtml(fn)).join("<br>")}</div>`;
                }
                tblBox.innerHTML = `
                    <div style="font-weight: 600; font-size: 0.9rem; margin-bottom: 0.4rem;">${escapeHtml(captionText)}</div>
                    <table class="manuscript-table">${rowsHtml}</table>
                    ${footnotesHtml}
                `;
                blockEl.appendChild(tblBox);

            } else if (block.type === "reference_list") {
                const refBox = document.createElement("div");
                refBox.className = "manuscript-references-box";
                const refs = Array.isArray(block.content) ? block.content : [];
                let refItems = "";
                if (refs.length > 0) {
                    refItems = refs.map((r, i) => `<li>${escapeHtml(typeof r === 'string' ? r : (r.title || JSON.stringify(r)))}</li>`).join("");
                } else {
                    refItems = `<li>${escapeHtml(plainText || "Bibliography item")}</li>`;
                }
                refBox.innerHTML = `
                    <h3 class="manuscript-references-title">References</h3>
                    <ol class="manuscript-references-list">${refItems}</ol>
                `;
                blockEl.appendChild(refBox);

            } else {
                // Fallback / Unrecognized
                const rawBox = document.createElement("div");
                rawBox.style.cssText = "padding: 1rem; border-radius: 6px; background: #FEF2F2; border: 1px dashed #EF4444; font-size: 0.9rem;";
                rawBox.innerHTML = `
                    <div style="color: #991B1B; font-weight: 600; font-size: 0.8rem; margin-bottom: 0.35rem;">
                        ⚠ Unrecognized Content Block — Select to assign valid tag
                    </div>
                    <div contenteditable="true" style="outline:none;color:#1E293B;">${escapeHtml(plainText || "(Raw unclassified content)")}</div>
                `;
                const editDiv = rawBox.querySelector("[contenteditable]");
                if (editDiv) {
                    editDiv.onblur = (e) => handleTextUpdate(block, e.target.textContent.trim());
                }
                blockEl.appendChild(rawBox);
            }

            // Click to Select Block (with Ctrl+Click multi-select)
            blockEl.addEventListener("click", (e) => {
                if (document.activeElement === e.target && e.target.isContentEditable) {
                    selectBlock(block.id, false);
                    return;
                }
                if (e.ctrlKey || e.metaKey) {
                    // Multi-select toggle
                    if (selectedBlockIds.has(block.id)) {
                        selectedBlockIds.delete(block.id);
                        if (selectedBlockId === block.id) {
                            selectedBlockId = selectedBlockIds.size > 0 ? [...selectedBlockIds][0] : null;
                        }
                    } else {
                        selectedBlockIds.add(block.id);
                        if (selectedBlockId) selectedBlockIds.add(selectedBlockId);
                        selectedBlockId = block.id;
                    }
                    renderBlocks();
                } else {
                    selectedBlockIds.clear();
                    selectBlock(block.id, false);
                }
            });

            manuscriptDocumentCanvas.appendChild(blockEl);
        });

        // Restore scroll position after re-render
        if (scrollContainer) {
            requestAnimationFrame(() => { scrollContainer.scrollTop = savedScroll; });
        }
    }

    function handleTextUpdate(block, newText) {
        // Don't save the placeholder text as real content
        if (newText === "(Empty paragraph)") newText = "";
        const oldText = getBlockPlainText(block);
        const normalizedOld = oldText === "(Empty paragraph)" ? "" : oldText;
        if (newText !== normalizedOld) {
            block.content = [{ text: newText, bold: false, italic: false }];
            block.state = "confirmed";
            block.is_user_confirmed = true;
            saveProjectUpdates();
        }
    }

    // ---- Render Structure Outline ----
    function renderStructureOutline(blocks) {
        if (!structureOutlineList) return;
        structureOutlineList.innerHTML = "";

        blocks.forEach(b => {
            const item = document.createElement("div");
            item.className = "outline-item";
            if (b.id === selectedBlockId) item.classList.add("active");

            const snippet = getBlockPlainText(b).substring(0, 45).replace(/\n/g, " ") || `[${formatBlockType(b.type)}]`;
            item.innerHTML = `
                <span class="outline-item-tag tag-badge-${getTagCategory(b.type)}">${formatBlockType(b.type)}</span>
                <span class="outline-item-snippet" title="${escapeHtml(snippet)}">${escapeHtml(snippet)}</span>
            `;

            item.addEventListener("click", () => {
                selectBlock(b.id, true);
            });

            structureOutlineList.appendChild(item);
        });
    }

    // ---- Select Block (Synchronized) ----
    function selectBlock(blockId, scrollIntoView) {
        selectedBlockId = blockId;
        selectedBlockIds.clear();  // Clear multi-select when single-clicking

        // 1. Highlight in manuscript canvas
        if (manuscriptDocumentCanvas) {
            manuscriptDocumentCanvas.querySelectorAll(".manuscript-block").forEach(el => {
                if (el.dataset.blockId === blockId) {
                    el.classList.add("selected");
                    if (scrollIntoView) {
                        el.scrollIntoView({ behavior: "smooth", block: "center" });
                    }
                } else {
                    el.classList.remove("selected");
                }
            });
        }

        // 2. Highlight in outline list
        if (structureOutlineList) {
            const blocks = currentProject.blocks || [];
            const idx = blocks.findIndex(b => b.id === blockId);
            const items = structureOutlineList.querySelectorAll(".outline-item");
            items.forEach((item, i) => {
                if (i === idx) item.classList.add("active");
                else item.classList.remove("active");
            });
        }

        // 3. Update Inspector Pane
        updateInspectorDetails();
    }

    // ---- Update Inspector Details ----
    function updateInspectorDetails() {
        if (!currentProject || !currentProject.blocks) return;

        // ---- Multi-Select Mode ----
        if (selectedBlockIds.size > 1) {
            const count = selectedBlockIds.size;
            if (inspectorBlockId) {
                inspectorBlockId.textContent = `${count} BLOCKS SELECTED`;
            }
            if (inspectorStateBadge) {
                inspectorStateBadge.className = 'badge badge-info';
                inspectorStateBadge.textContent = 'MULTI-SELECT';
            }
            if (inspectorWarningBox) inspectorWarningBox.style.display = "none";

            // Show bulk retag dropdown
            if (inspectorRetagSelect) {
                inspectorRetagSelect.value = "paragraph";
                inspectorRetagSelect.onchange = (e) => {
                    bulkRetagBlocks(e.target.value);
                };
            }

            // Show selected block types summary in text area
            if (inspectorTextInput) {
                const selectedBlocks = currentProject.blocks.filter(b => selectedBlockIds.has(b.id));
                const summary = selectedBlocks.map(b => {
                    const txt = getBlockPlainText(b).substring(0, 60);
                    return `[${formatBlockType(b.type)}] ${txt}`;
                }).join("\n");
                inspectorTextInput.value = summary;
                inspectorTextInput.readOnly = true;
            }

            // Multi-select action buttons
            if (inspectorConfirmBtn) {
                inspectorConfirmBtn.onclick = () => {
                    selectedBlockIds.forEach(id => confirmBlock(id));
                };
            }
            if (inspectorSplitBtn) {
                inspectorSplitBtn.onclick = () => mergeSelectedToReferenceList();
                inspectorSplitBtn.textContent = "📚 Merge → References";
            }
            if (inspectorMergeBtn) {
                inspectorMergeBtn.onclick = () => bulkRetagBlocks("reference_list");
                inspectorMergeBtn.textContent = "🔄 All → Ref Entries";
            }
            if (inspectorDeleteBtn) {
                inspectorDeleteBtn.onclick = () => {
                    if (!confirm(`Delete ${count} selected blocks?`)) return;
                    currentProject.blocks = currentProject.blocks.filter(b => !selectedBlockIds.has(b.id));
                    selectedBlockIds.clear();
                    selectedBlockId = currentProject.blocks.length > 0 ? currentProject.blocks[0].id : null;
                    saveProjectUpdates();
                };
            }
            return;
        }

        // ---- Single-Select Mode (restore button labels) ----
        if (inspectorSplitBtn) inspectorSplitBtn.textContent = "✂ Split Block";
        if (inspectorMergeBtn) inspectorMergeBtn.textContent = "⬇ Merge Down";
        if (inspectorTextInput) inspectorTextInput.readOnly = false;

        const block = currentProject.blocks.find(b => b.id === selectedBlockId);
        if (!block) return;

        if (inspectorBlockId) {
            inspectorBlockId.textContent = `${formatBlockType(block.type)} (#${block.id})`;
        }

        if (inspectorStateBadge) {
            inspectorStateBadge.className = `badge badge-${block.state === 'confirmed' ? 'success' : (block.state === 'needs_review' ? 'warning' : 'danger')}`;
            inspectorStateBadge.textContent = block.is_flagged_manual ? 'FLAGGED' : (block.state || 'confirmed').toUpperCase();
        }

        if (inspectorWarningBox && inspectorWarningText) {
            if (block.warnings && block.warnings.length > 0) {
                inspectorWarningBox.style.display = "flex";
                inspectorWarningText.textContent = block.warnings.join(" | ");
            } else {
                inspectorWarningBox.style.display = "none";
            }
        }

        if (inspectorRetagSelect) {
            inspectorRetagSelect.value = block.type || "paragraph";
            inspectorRetagSelect.onchange = (e) => {
                retagBlock(block.id, e.target.value);
            };
        }

        if (inspectorTextInput) {
            inspectorTextInput.value = getBlockPlainText(block);
            inspectorTextInput.onblur = (e) => {
                handleTextUpdate(block, e.target.value.trim());
            };
        }

        // Inspector Buttons
        if (inspectorConfirmBtn) {
            inspectorConfirmBtn.onclick = () => confirmBlock(block.id);
        }
        if (inspectorSplitBtn) {
            inspectorSplitBtn.onclick = () => splitBlock(block.id);
        }
        if (inspectorMergeBtn) {
            const index = currentProject.blocks.findIndex(b => b.id === block.id);
            inspectorMergeBtn.onclick = () => mergeBlock(block.id, index);
        }
        if (inspectorDeleteBtn) {
            inspectorDeleteBtn.onclick = () => deleteBlock(block.id);
        }
    }

    // ---- Block Operations ----
    function confirmBlock(blockId) {
        const block = currentProject.blocks.find(b => b.id === blockId);
        if (block) {
            block.state = "confirmed";
            block.warnings = [];
            block.is_user_confirmed = true;
            saveProjectUpdates();
        }
    }

    function retagBlock(blockId, newType) {
        const block = currentProject.blocks.find(b => b.id === blockId);
        if (!block || block.type === newType) return;

        const currentText = getBlockPlainText(block);
        block.type = newType;
        block.state = "confirmed";
        block.warnings = [];
        block.is_user_confirmed = true;

        if (newType === "unrecognized") {
            block.state = "unrecognized";
            block.is_user_confirmed = false;
            block.content = { raw_type: "manually_demoted", content_text: currentText };
        } else if (["paragraph", "title", "heading_l1", "heading_l2", "heading_l3", "footnote"].includes(newType)) {
            block.content = [{ text: currentText || `New ${newType.replace(/_/g, ' ')} content`, bold: false, italic: false }];
        } else if (newType === "abstract") {
            block.content = [[{ text: currentText || "Abstract content", bold: false, italic: false }]];
        } else if (newType === "reference_list") {
            // Convert paragraph text to a single reference entry
            block.content = [{
                id: `ref-${Math.random().toString(36).substring(2, 7)}`,
                type: "journal-article",
                title: currentText || "Reference entry",
                source_title: "",
                authors: [],
                year: "",
                volume: "",
                issue: "",
                pages: "",
                doi: ""
            }];
        } else if (newType === "figure") {
            block.content = { id: `fig-${Math.random().toString(36).substring(2, 7)}`, image_ref: "", caption: [{ text: currentText, bold: false, italic: false }], alt_text: "" };
        } else if (newType === "table") {
            block.content = { id: `tbl-${Math.random().toString(36).substring(2, 7)}`, caption: [{ text: currentText, bold: false, italic: false }], rows: [] };
        } else if (newType === "equation") {
            block.content = { id: `eq-${Math.random().toString(36).substring(2, 7)}`, latex_source: currentText, display: "block" };
        }

        saveProjectUpdates();
    }

    // ---- Bulk Operations for Multi-Select ----
    function bulkRetagBlocks(newType) {
        if (selectedBlockIds.size === 0) return;
        const count = selectedBlockIds.size;
        if (!confirm(`Retag ${count} selected block(s) to "${formatBlockType(newType)}"?`)) return;

        selectedBlockIds.forEach(id => {
            retagBlock(id, newType);
        });
        // Don't call saveProjectUpdates here — retagBlock already calls it per block
        // But we do need to save once at the end after all retags
    }

    function mergeSelectedToReferenceList() {
        if (selectedBlockIds.size < 2) {
            alert("Select at least 2 blocks to merge into a reference list.");
            return;
        }

        if (!confirm(`Merge ${selectedBlockIds.size} selected blocks into a single REFERENCE LIST block?\n\nEach block will become one reference entry.`)) return;

        const blocks = currentProject.blocks;
        const selectedIds = [...selectedBlockIds];

        // Build reference entries from each selected block's text
        const refEntries = [];
        selectedIds.forEach((id, i) => {
            const block = blocks.find(b => b.id === id);
            if (!block) return;
            const text = getBlockPlainText(block).trim();
            if (text) {
                refEntries.push({
                    id: `ref-${i + 1}`,
                    type: "journal-article",
                    title: text,
                    source_title: "",
                    authors: [],
                    year: "",
                    volume: "",
                    issue: "",
                    pages: "",
                    doi: ""
                });
            }
        });

        if (refEntries.length === 0) {
            alert("No text content found in selected blocks.");
            return;
        }

        // Find the position of the first selected block
        const firstIdx = Math.min(...selectedIds.map(id => blocks.findIndex(b => b.id === id)).filter(i => i >= 0));

        // Remove all selected blocks
        currentProject.blocks = blocks.filter(b => !selectedBlockIds.has(b.id));

        // Insert a single reference_list block at the first position
        const refBlockId = `references-${Math.random().toString(36).substring(2, 8)}`;
        const refBlock = {
            id: refBlockId,
            type: "reference_list",
            content: refEntries,
            state: "confirmed",
            warnings: [],
            is_flagged_manual: false,
            is_user_confirmed: true
        };

        const insertIdx = Math.min(firstIdx, currentProject.blocks.length);
        currentProject.blocks.splice(insertIdx, 0, refBlock);

        selectedBlockIds.clear();
        selectedBlockId = refBlockId;
        saveProjectUpdates();
    }

    function splitBlock(blockId) {
        const block = currentProject.blocks.find(b => b.id === blockId);
        if (!block) return;
        const plainText = getBlockPlainText(block);
        const splitText = prompt(`Enter the exact text snippet where you want to split this block:\n\nSnippet preview: "${plainText.substring(0, 120)}…"`, "");
        if (!splitText) return;

        const splitIndex = plainText.indexOf(splitText);
        if (splitIndex === -1) {
            alert("The entered text snippet was not found in this block.");
            return;
        }

        const textA = plainText.substring(0, splitIndex).trim();
        const textB = plainText.substring(splitIndex).trim();

        const index = currentProject.blocks.findIndex(b => b.id === blockId);
        const newBlockId = `block-${Math.random().toString(36).substring(2, 8)}`;

        block.content = [{ text: textA, bold: false, italic: false }];
        block.is_user_confirmed = true;

        currentProject.blocks.splice(index + 1, 0, {
            id: newBlockId,
            type: block.type || "paragraph",
            content: [{ text: textB, bold: false, italic: false }],
            state: "confirmed",
            warnings: [],
            is_flagged_manual: false,
            is_user_confirmed: true
        });

        selectedBlockId = newBlockId;
        saveProjectUpdates();
    }

    function mergeBlock(blockId, index) {
        const blockA = currentProject.blocks[index];
        const blockB = currentProject.blocks[index + 1];
        if (!blockA || !blockB) {
            alert("There is no following block to merge with.");
            return;
        }

        if (!confirm("Are you sure you want to merge this block with the following block?")) return;

        const textA = getBlockPlainText(blockA);
        const textB = getBlockPlainText(blockB);
        const mergedText = `${textA}\n\n${textB}`.trim();

        blockA.content = [{ text: mergedText, bold: false, italic: false }];
        blockA.state = "confirmed";
        blockA.warnings = [];
        blockA.is_user_confirmed = true;

        currentProject.blocks.splice(index + 1, 1);
        selectedBlockId = blockA.id;
        saveProjectUpdates();
    }

    function deleteBlock(blockId) {
        const index = currentProject.blocks.findIndex(b => b.id === blockId);
        if (index === -1) return;

        // Check if the block is empty — skip confirmation for empty blocks
        const block = currentProject.blocks[index];
        const blockText = getBlockPlainText(block).trim();
        const isEmpty = !blockText || blockText === "(Empty paragraph)";

        if (!isEmpty) {
            if (!confirm("Are you sure you want to remove this block from the manuscript?")) return;
        }

        currentProject.blocks.splice(index, 1);
        if (currentProject.blocks.length > 0) {
            selectedBlockId = currentProject.blocks[Math.max(0, index - 1)].id;
        } else {
            selectedBlockId = null;
        }
        saveProjectUpdates();
    }

    function handleAcceptAi(block) {
        if (!block.ai_change) return;
        block.ai_change.reviewed = true;
        block.is_user_confirmed = true;
        renderBlocks();
        showToast(`✓ Accepted AI change: ${formatBlockType(block.type)}`);

        fetch(`/project/${projectId}/block/${block.id}/accept-ai`, {
            method: "POST"
        })
        .then(res => res.json())
        .then(data => {
            if (data.project) currentProject = data.project;
            renderBlocks();
        })
        .catch(err => {
            console.error("Failed to accept AI change:", err);
        });
    }

    function handleRejectAi(block) {
        if (!block.ai_change) return;
        const oldType = block.ai_change.old_type;
        block.type = oldType;
        block.ai_change.reviewed = true;
        block.is_ai_assisted = false;
        block.is_user_confirmed = true;
        renderBlocks();
        showToast(`Reverted block to ${formatBlockType(oldType)}`);

        fetch(`/project/${projectId}/block/${block.id}/revert-ai`, {
            method: "POST"
        })
        .then(res => res.json())
        .then(data => {
            if (data.project) currentProject = data.project;
            renderBlocks();
        })
        .catch(err => {
            console.error("Failed to revert AI change:", err);
        });
    }

    function showAiAnalysisBanner(changes, message) {
        let existingBanner = document.getElementById("aiAnalysisBannerContainer");
        if (!existingBanner) {
            existingBanner = document.createElement("div");
            existingBanner.id = "aiAnalysisBannerContainer";
            existingBanner.className = "ai-analysis-banner";
            const canvas = document.getElementById("manuscriptDocumentCanvas");
            if (canvas && canvas.parentElement) {
                canvas.parentElement.insertBefore(existingBanner, canvas);
            }
        }
        existingBanner.innerHTML = `
            <div class="ai-analysis-banner-text">
                <strong>🤖 AI Layout Analysis:</strong> ${escapeHtml(message || "")} 
                <span style="font-size:0.8rem;color:var(--text-secondary);display:block;margin-top:2px;">Showing <strong>${changes.length}</strong> block corrections. Review the badges below.</span>
            </div>
            <div style="display:flex;gap:0.5rem;flex-shrink:0;">
                <button type="button" class="btn btn-sm btn-primary" id="acceptAllAiBtn" style="font-size:0.75rem;">✓ Accept All (${changes.length})</button>
                <button type="button" class="btn btn-sm btn-outline" id="dismissAiBannerBtn" style="font-size:0.75rem;">Dismiss</button>
            </div>
        `;
        const acceptAllBtn = existingBanner.querySelector("#acceptAllAiBtn");
        const dismissBtn = existingBanner.querySelector("#dismissAiBannerBtn");
        if (acceptAllBtn) {
            acceptAllBtn.addEventListener("click", () => {
                const blocks = currentProject.blocks || [];
                blocks.forEach(b => {
                    if (b.ai_change && !b.ai_change.reviewed) {
                        b.ai_change.reviewed = true;
                        b.is_user_confirmed = true;
                    }
                });
                saveProjectUpdates();
                existingBanner.remove();
                activeFilter = "all";
                document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
                const allChip = document.querySelector('[data-filter="all"]');
                if (allChip) allChip.classList.add("active");
                renderBlocks();
                showToast(`✓ All ${changes.length} AI changes accepted.`);
            });
        }
        if (dismissBtn) {
            dismissBtn.addEventListener("click", () => {
                existingBanner.remove();
            });
        }
    }

    // Auto-Identify with AI action
    if (aiIdentifyBtn) {
        aiIdentifyBtn.addEventListener("click", () => {
            if (!currentProject || !currentProject.id) return;

            // AI Consent: Require explicit author consent before AI processing
            const consent = confirm(
                "🤖 AI-Assisted Manuscript Analysis\n\n" +
                "This feature cross-checks your manuscript against the raw PDF layout to auto-detect " +
                "and correct misclassified blocks (headings, figures, tables, abstract, etc.).\n\n" +
                "By proceeding, you consent to:\n" +
                "• Your manuscript text and PDF layout being cross-checked by AI\n" +
                "• All AI-corrected blocks will show an explicit AI Change Badge for your review\n" +
                "• You can Accept or Revert any AI changes individually\n\n" +
                "Do you want to proceed with AI analysis?"
            );
            if (!consent) return;

            const originalHtml = aiIdentifyBtn.innerHTML;
            aiIdentifyBtn.classList.add("loading");
            aiIdentifyBtn.innerHTML = `<span>✨ Analyzing PDF & structure…</span>`;

            fetch(`/project/${currentProject.id}/ai-identify`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            })
            .then(res => {
                if (!res.ok) throw new Error("AI identification request failed.");
                return res.json();
            })
            .then(data => {
                currentProject = data.project || currentProject;
                renderBlocks();
                const totalUpdated = data.updated_count || 0;
                if (totalUpdated > 0 && data.changes && data.changes.length > 0) {
                    activeFilter = "ai_changes";
                    document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
                    if (filterAiChangesBtn) filterAiChangesBtn.classList.add("active");
                    renderBlocks();
                    showAiAnalysisBanner(data.changes, data.message);
                } else {
                    showToast(data.message || "✓ All blocks verified against PDF layout.");
                }
            })
            .catch(err => {
                console.error("AI identification error:", err);
                alert("AI identification failed: " + err.message);
            })
            .finally(() => {
                aiIdentifyBtn.classList.remove("loading");
                aiIdentifyBtn.innerHTML = originalHtml;
            });
        });
    }

    // Reference PDF Upload
    if (uploadReferencePdfBtn && uploadReferencePdfInput) {
        uploadReferencePdfBtn.addEventListener("click", () => {
            uploadReferencePdfInput.click();
        });
        uploadReferencePdfInput.addEventListener("change", (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;
            if (!file.name.toLowerCase().endsWith(".pdf")) {
                alert("Please select a valid PDF file.");
                return;
            }
            const formData = new FormData();
            formData.append("file", file);
            showToast("Uploading reference PDF...");
            fetch(`/project/${currentProject.id}/upload-reference-pdf`, {
                method: "POST",
                body: formData
            })
            .then(res => {
                if (!res.ok) throw new Error("Failed to upload reference PDF.");
                return res.json();
            })
            .then(data => {
                showToast(data.message || "Reference PDF uploaded!");
                uploadReferencePdfBtn.textContent = `✓ Ref PDF: ${file.name.slice(0, 12)}...`;
            })
            .catch(err => {
                alert("Failed to upload reference PDF: " + err.message);
            });
        });
    }

    // Re-Identify Blocks (rule-based, groups references)
    if (reIdentifyBtn) {
        reIdentifyBtn.addEventListener("click", () => {
            console.log("[Re-Identify] Button clicked, currentProject:", currentProject?.id);
            if (!currentProject || !currentProject.id) {
                console.error("[Re-Identify] No project loaded");
                alert("No project loaded. Please reload the page.");
                return;
            }
            const originalHtml = reIdentifyBtn.innerHTML;
            reIdentifyBtn.disabled = true;
            reIdentifyBtn.innerHTML = `<span>🔄 Re-identifying…</span>`;

            fetch(`/project/${currentProject.id}/re-identify`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            })
            .then(res => {
                console.log("[Re-Identify] Response status:", res.status);
                if (!res.ok) throw new Error("Re-identification request failed.");
                return res.json();
            })
            .then(data => {
                console.log("[Re-Identify] Success:", data.message);
                currentProject = data.project || currentProject;
                renderBlocks();
                if (data.message) {
                    alert(data.message);
                }
            })
            .catch(err => {
                console.error("Re-identification error:", err);
                alert("Re-identification failed: " + err.message);
            })
            .finally(() => {
                reIdentifyBtn.disabled = false;
                reIdentifyBtn.innerHTML = originalHtml;
            });
        });
    } else {
        console.warn("[Re-Identify] reIdentifyBtn not found in DOM");
    }

    // Confirm all blocks action
    if (confirmAllBtn) {
        confirmAllBtn.addEventListener("click", () => {
            if (!currentProject || !currentProject.blocks) return;
            currentProject.blocks.forEach(b => {
                b.state = "confirmed";
                b.warnings = [];
                b.is_user_confirmed = true;
            });
            saveProjectUpdates();
        });
    }

    // Add new block action
    if (addNewBlockBtn) {
        addNewBlockBtn.addEventListener("click", () => {
            if (!currentProject || !currentProject.blocks) return;
            const newBlockId = `block-${Math.random().toString(36).substring(2, 8)}`;
            const newBlock = {
                id: newBlockId,
                type: "paragraph",
                content: [{ text: "New paragraph content...", bold: false, italic: false }],
                state: "confirmed",
                warnings: [],
                is_flagged_manual: false,
                is_user_confirmed: true
            };
            currentProject.blocks.push(newBlock);
            selectedBlockId = newBlockId;
            saveProjectUpdates();
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

    // Save project updates to server
    function saveProjectUpdates() {
        if (!currentProject) return;
        fetch(`/project/${currentProject.id}/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ blocks: currentProject.blocks })
        })
        .then(res => {
            if (!res.ok) throw new Error("Update request failed.");
            return res.json();
        })
        .then(data => {
            currentProject = data.project || data;
            renderBlocks();
        })
        .catch(err => {
            console.error("Save error:", err);
            alert("Failed to save changes to the server.");
        });
    }

    // Boot
    loadProject(projectId);
});
