const API_BASE = "/api";
let appBlueprints = [];

// Load blueprints on startup
async function loadBlueprints() {
    try {
        const res = await fetch(`${API_BASE}/blueprints`);
        if (res.ok) {
            const data = await res.json();
            appBlueprints = data.blueprints;
        } else {
            console.error("Failed to load blueprints");
        }
    } catch (e) {
        console.error("Error loading blueprints:", e);
    }
}
async function initDocument(reset = false) {
    const name = document.getElementById('docName').value;
    if (reset && !confirm(`Are you sure you want to RESET '${name}'? This cannot be undone.`)) return;

    const res = await fetch(`${API_BASE}/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, reset })
    });

    const data = await res.json();
    notify(data.message);
    document.getElementById('docPreview').textContent = data.content;

    await loadStructure();
    await loadVersions();
    updateDownloadLink();
}

let currentStructure = [];
let pendingMerges = {}; // Map title -> Array<Match>
let mergeCache = {}; // Map key -> Promise<MergeResult>
let mergeInProgress = false; // Track if merge workflow is active
let showVersionInfo = false; // Track annotated display mode

async function loadStructure() {
    const name = document.getElementById('docName').value;
    const res = await fetch(`${API_BASE}/structure/${name}`);
    const data = await res.json();
    currentStructure = data.structure;
    renderStructure();
}

// Helper: Check if a section is a placeholder with only template content
function isPlaceholderSection(item) {
    const title = item.title || "";
    const content = item.content || "";

    // Check if content matches any blueprint template exactly (excluding the main header)
    for (const bp of appBlueprints) {
        if (bp.type === 'numerable') {
            // We can just check if it only has header structure
            return isEmptyOrTemplate(content);
        }
    }

    return isEmptyOrTemplate(content);
}

// Helper: Check if content has child sections (nested headers at different levels)
function hasChildSections(content) {
    if (!content) return false;

    // Check if there are multiple header levels
    const lines = content.split('\n');
    const headerLevels = new Set();

    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('#')) {
            const match = trimmed.match(/^#+/);
            if (match) {
                headerLevels.add(match[0].length);
            }
        }
    }

    // If there are 2+ different header levels, it has child sections
    // e.g., ## Context, Aim & Integration with ### Context, ### Aim underneath
    return headerLevels.size >= 2;
}

// Helper: Check if content is empty or just template structure
function isEmptyOrTemplate(content) {
    if (!content || content.trim() === '') {
        return true;
    }

    // If it has child sections (nested headers), it's not truly empty - it has structure
    // e.g., ## Context, Aim & Integration\n\n### Context\n\n### Aim\n\n
    // This should NOT be treated as empty because it has a hierarchical structure
    if (hasChildSections(content)) {
        return false;
    }

    // Check if it's just headers with no content between them
    const lines = content.split('\n');
    let hasActualContent = false;

    for (const line of lines) {
        const trimmedLine = line.trim();
        // Skip empty lines and header lines
        if (!trimmedLine || trimmedLine.startsWith('#')) {
            continue;
        }
        // Found actual content
        hasActualContent = true;
        break;
    }

    return !hasActualContent;
}

// Helper: Check if content is a template with multiple subsections (e.g., feature/milestone template)
function isTemplateWithStructure(content) {
    if (!content || content.trim() === '') {
        return false;
    }

    // Count level-4 headers (####)
    const level4Headers = (content.match(/^####\s+/gm) || []).length;

    // If there are 2+ level-4 headers and no actual content, it's a template
    if (level4Headers >= 2) {
        // Check if there's actual content (non-header, non-empty lines)
        const lines = content.split('\n');
        let hasContent = false;

        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed && !trimmed.startsWith('#')) {
                hasContent = true;
                break;
            }
        }

        // Template if it has structure but no content
        return !hasContent;
    }

    return false;
}

// Helper: Parse content into subsections (for template merging)
function parseSubsections(content) {
    const sections = {};
    const lines = content.split('\n');
    let currentSection = null;
    let currentContent = [];

    for (const line of lines) {
        const trimmed = line.trim();

        // Check for level-4 header (####)
        if (trimmed.startsWith('####')) {
            // Save previous section
            if (currentSection) {
                sections[currentSection] = currentContent.join('\n');
            }

            // Start new section
            currentSection = trimmed.replace(/^####\s+/, '');
            currentContent = [line];
        } else if (currentSection) {
            currentContent.push(line);
        }
    }

    // Save last section
    if (currentSection) {
        sections[currentSection] = currentContent.join('\n');
    }

    return sections;
}

// Helper: Merge new subsections into template structure
function mergeIntoTemplate(template, newContent) {
    // Parse both into subsections
    const templateSections = parseSubsections(template);
    const newSections = parseSubsections(newContent);

    // Merge: for each section in new content, replace in template
    for (const [sectionName, sectionContent] of Object.entries(newSections)) {
        templateSections[sectionName] = sectionContent;
    }

    // Reconstruct the merged content
    const mergedParts = [];

    // Get the header line (e.g., "### Feature: World Engine")
    const headerMatch = template.match(/^###\s+.+$/m);
    if (headerMatch) {
        mergedParts.push(headerMatch[0]);
        mergedParts.push('');
    }

    // Add all subsections in order (preserve template order)
    for (const [sectionName, sectionContent] of Object.entries(templateSections)) {
        mergedParts.push(sectionContent);
        mergedParts.push('');
    }

    return mergedParts.join('\n').trim();
}

// Helper: Get section content including all child subsections
function getSectionWithChildren(sectionTitle) {
    // Find the section index
    const sectionIndex = currentStructure.findIndex(i => i.title === sectionTitle);
    if (sectionIndex === -1) {
        return null;
    }

    const section = currentStructure[sectionIndex];
    const sectionLevel = section.level;

    // Gather this section and all children
    let combinedContent = section.content;

    // Look ahead for child sections
    for (let i = sectionIndex + 1; i < currentStructure.length; i++) {
        const nextSection = currentStructure[i];

        // Stop if we hit a section at the same or lower level
        if (nextSection.level <= sectionLevel) {
            break;
        }

        // This is a child section, add it
        combinedContent += '\n' + nextSection.content;
    }

    return combinedContent;
}

function renderStructure() {
    const list = document.getElementById('structureList');
    list.innerHTML = "";

    const renderedTitles = new Set();

    currentStructure.forEach((item, index) => {
        // Skip placeholder sections (Feature 1, Milestone 1) if they only contain template structure
        if (isPlaceholderSection(item)) {
            return;
        }

        // Only show levels up to the max defined in blueprints (or fallback to 3)
        let maxVisibleLevel = 3;
        if (appBlueprints.length > 0) {
            maxVisibleLevel = Math.max(...appBlueprints.filter(bp => bp.type === 'numerable').map(bp => bp.level));
        }

        if (item.level > maxVisibleLevel) {
            return;
        }

        renderedTitles.add(item.title);
        const div = document.createElement('div');
        div.className = `structure-item level-${item.level}`;
        div.textContent = item.title || "(Untitled)";

        if (pendingMerges[item.title] && pendingMerges[item.title].length > 0) {
            div.classList.add('pending-merge');
            div.dataset.count = pendingMerges[item.title].length;
        }

        div.onclick = () => {
            document.querySelectorAll('.structure-item').forEach(el => el.classList.remove('active'));
            div.classList.add('active');

            if (pendingMerges[item.title] && pendingMerges[item.title].length > 0) {
                selectPendingMerge(item.title);
                currentViewedSection = null; // Merging mode, not reading mode
            } else {
                // Use hierarchical content gathering to show section with all children
                const content = getSectionWithChildren(item.title);
                document.getElementById('docPreview').textContent = content || item.content;
                notify(`Viewing section: ${item.title}`);
                document.getElementById('diffView').classList.add('hidden');
                document.getElementById('arbiterControls').classList.add('hidden');

                currentViewedSection = item.title;

                // Scroll preview into view
                document.getElementById('docPreview').scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            updateEditButtonState();
        };

        list.appendChild(div);
    });

    // Render "New Sections"
    Object.keys(pendingMerges).forEach(title => {
        if (!renderedTitles.has(title) && pendingMerges[title].length > 0) {
            const div = document.createElement('div');
            div.className = "structure-item level-2 pending-merge new-section";
            div.textContent = `+ ${title} (New)`;
            div.dataset.count = pendingMerges[title].length;

            div.onclick = () => {
                document.querySelectorAll('.structure-item').forEach(el => el.classList.remove('active'));
                div.classList.add('active');
                selectPendingMerge(title);
            };

            list.appendChild(div);
        }
    });
}

async function processInput() {
    const text = document.getElementById('inputArea').value;
    if (!text) { notify("Please paste some text first."); return; }

    // Block if merge is in progress
    if (mergeInProgress) {
        notify("⚠️ Cannot process new input while merges are in progress. Complete or discard pending merges first.");
        showMergeBlockingIndicator();
        return;
    }

    notify("Processing... Analyzing Protocol...");

    const name = document.getElementById('docName').value;
    const matchRes = await fetch(`${API_BASE}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, name })
    });
    const matchData = await matchRes.json();

    if (matchData.status === "error") {
        notify(`Error: ${matchData.message}`);
        return;
    }

    // Reset pending & cache
    pendingMerges = {};
    mergeCache = {};

    // Group results by section
    matchData.matches.forEach(m => {
        if (!pendingMerges[m.section]) {
            pendingMerges[m.section] = [];
        }
        pendingMerges[m.section].push(m);
    });

    // Set merge in progress flag
    mergeInProgress = true;
    showMergeBlockingIndicator();

    // Trigger background pre-merge for the FIRST item of each section
    Object.keys(pendingMerges).forEach(title => {
        const firstItem = pendingMerges[title][0];
        const currentContent = getRealOriginal(title, firstItem.original_text);
        // Just trigger it. The handle returned will start the background work.
        getMergePromise(title, currentContent, firstItem.new_text);
    });

    // Update Sidebar
    renderStructure();

    notify(`Found ${matchData.matches.length} updates. Check the warning icons in the structure.`);
}

// Helper to get real original content from structure or new item
function getRealOriginal(title, fallback) {
    const structItem = currentStructure.find(i => (i.title || "(Untitled)") === title);
    let realOriginal = structItem ? structItem.content : "";

    if (!realOriginal) {
        // Auto-Template Logic for New Sections Using Blueprints
        const lowerTitle = title.toLowerCase();

        for (const bp of appBlueprints) {
            if (bp.type === 'numerable') {
                const prefixMatch = bp.template_prefix.replace(/^#+\s*/, '').trim().toLowerCase();
                if (lowerTitle.startsWith(prefixMatch)) {
                    // Generate template by combining title + template content
                    const hashes = '#'.repeat(bp.level);
                    return `${hashes} ${title}\n\n${bp.template_content}`;
                }
            }
        }

        realOriginal = fallback || "";
    }
    return realOriginal;
}

// Helper to get cache key
function getCacheKey(original, newText) {
    const safeO = original ? original.substring(0, 50) + original.length : "null";
    const safeN = newText ? newText.substring(0, 50) + newText.length : "null";
    return `${safeO}|||${safeN}`;
}

// Track active generation
let currentTaskId = null;

async function selectPendingMerge(title) {
    const items = pendingMerges[title];
    if (!items || items.length === 0) return;

    const currentMatch = items[0];

    // 1. Determine "Original" Content
    let realOriginal = getRealOriginal(title, currentMatch.original_text);

    // 2. Setup partial view
    document.getElementById('diffView').classList.remove('hidden');
    document.getElementById('arbiterControls').classList.remove('hidden');
    document.getElementById('originalContent').textContent = realOriginal;
    document.getElementById('newContent').textContent = currentMatch.new_text;

    // Populate Selector
    populateTargetSelector(title);

    // 3. Prepare Merge View
    const mergedArea = document.getElementById('mergedContent');
    const spinner = document.getElementById('mergeSpinner');
    const stopBtn = document.getElementById('btnStopMerge');

    mergedArea.value = "";
    document.getElementById('diffView').dataset.targetSection = title;

    // 4. Check merge strategy based on original content type

    // Case 1: Original is a template with structure (e.g., feature/milestone template)
    // and new content has subsections - merge intelligently
    // CHECK THIS FIRST before the empty check, because templates are "empty" but have structure
    if (isTemplateWithStructure(realOriginal)) {
        // Check if new content has subsections to merge
        const newSections = parseSubsections(currentMatch.new_text);

        if (Object.keys(newSections).length > 0) {
            console.log(`[UI] Smart merge: inserting ${Object.keys(newSections).length} subsection(s) into template for '${title}'`);
            const smartMerged = mergeIntoTemplate(realOriginal, currentMatch.new_text);
            mergedArea.value = smartMerged;
            notify(`Ready to merge '${title}' (${items.length} remaining) - template merged`);
            return;
        }
    }

    // Case 1.5: Original has content, but the specific subsection(s) being introduced by new_text
    // are empty slots inside it (e.g. chunk 2/3 of the same Feature block after chunk 1 was committed).
    // When ALL targeted subsections are empty in realOriginal, merge directly without LLM.
    const newSubsections = parseSubsections(currentMatch.new_text);
    if (Object.keys(newSubsections).length > 0 && realOriginal) {
        const origSubsections = parseSubsections(realOriginal);
        const allTargetsEmpty = Object.keys(newSubsections).every(subName => {
            const origSub = origSubsections[subName];
            // A subsection is "empty" if it only contains its header line and no other content
            if (!origSub) return true; // subsection doesn't exist in original → empty slot
            const bodyLines = origSub.split('\n').slice(1); // skip the header line itself
            return bodyLines.every(l => !l.trim()); // all remaining lines are blank
        });

        if (allTargetsEmpty) {
            console.log(`[UI] Case 1.5 – all targeted subsections are empty in '${title}'. Direct smart-merge.`);
            const smartMerged = mergeIntoTemplate(realOriginal, currentMatch.new_text);
            mergedArea.value = smartMerged;
            notify(`Ready to merge '${title}' (${items.length} remaining) - no conflicts`);
            return;
        }
    }

    // Case 2: Original is truly empty (no structure) - use new content directly
    if (isEmptyOrTemplate(realOriginal)) {
        console.log(`[UI] Skipping LLM merge for '${title}' - original is empty/template`);
        mergedArea.value = currentMatch.new_text;
        notify(`Ready to merge '${title}' (${items.length} remaining) - no conflicts`);
        return;
    }

    // Case 3: Original has content or merge is ambiguous - call LLM

    // Show spinner & Stop button
    // We assume it's running/pending until proven otherwise
    spinner.classList.remove('hidden');
    if (stopBtn) {
        console.log("[UI] Enabling Stop Button");
        stopBtn.disabled = false;
    } else {
        console.warn("[UI] Stop Button not found in DOM!");
    }

    notify(`Generating merge for '${title}' (${items.length} remaining)...`);

    // Cancel previous task if valid
    if (currentTaskId) {
        currentTaskId = null;
    }

    try {
        // 5. Fetch Merge (Polling) via Cache
        const cacheEntry = getMergePromise(title, realOriginal, currentMatch.new_text);

        // Wait for Task ID to be assigned (in case it's starting up)
        if (cacheEntry.idPromise) {
            currentTaskId = await cacheEntry.idPromise;
            console.log(`[UI] Attached active Task ID: ${currentTaskId}`);
        }

        // Await the result
        const result = await cacheEntry.resultPromise;
        console.log(`[UI] Result received for ${title}:`, result);

        // CHECK IF STILL ACTIVE
        if (document.getElementById('diffView').dataset.targetSection !== title) {
            console.log(`[UI] Ignoring result for ${title} as view has changed.`);
            return;
        }

        if (result === undefined || result === null) {
            mergedArea.value = "Error: Result was empty.";
        } else {
            console.log(`[UI] Updating mergedArea value for ${title}`);
            mergedArea.value = result;
        }

    } catch (e) {
        if (e.message === 'Cancelled') {
            mergedArea.value = "Generation stopped by user.";
            notify("Generation stopped.");
        } else {
            console.error(e);
            mergedArea.value = e.message || "Error generating merge.";
            notify("Error generating merge.");
        }
    } finally {
        spinner.classList.add('hidden');
        if (stopBtn) stopBtn.disabled = true;
        // Clear if we are still the active one
        if (currentTaskId === cacheEntry?.taskId) {
            currentTaskId = null;
        }
    }
}

async function stopGeneration() {
    if (currentTaskId) {
        try {
            notify(`Stopping task ${currentTaskId}...`);
            console.log(`[UI] Stopping task ${currentTaskId}`);
            await fetch(`${API_BASE}/task/${currentTaskId}/cancel`, { method: 'POST' });
        } catch (e) {
            console.error("Failed to send cancel request", e);
            notify("Failed to stop.");
        }
        // Don't null here, let the catch/finally in selectPendingMerge handle it?
        // Actually we should null it to prevent double clicks, but keep it for logic?
        // Let's keep it nulling to be safe UI-wise.
        currentTaskId = null;
    } else {
        console.warn("[UI] Stop clicked but no currentTaskId!");
    }
}

// Fetch or retrieve { taskId, idPromise, resultPromise }
function getMergePromise(sectionTitle, original, newText) {
    const key = getCacheKey(original, newText);

    if (mergeCache[key]) {
        return mergeCache[key];
    }

    // Logic to resolve ID
    let resolveId;
    const idPromise = new Promise(r => { resolveId = r; });

    // Logic to run task
    const resultPromise = (async () => {
        console.log(`[Background] Starting task for ${sectionTitle}...`);

        // 1. Start Task
        let taskId = null;
        try {
            const startRes = await fetch(`${API_BASE}/diff`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ original, new: newText })
            });
            const startData = await startRes.json();
            taskId = startData.task_id;

            // Resolve ID for UI
            resolveId(taskId);

            // Update Handle
            mergeCache[key].taskId = taskId;
            console.log(`[Background] Task started: ${taskId}`);
        } catch (err) {
            console.error("Failed to start task:", err);
            resolveId(null);
            throw err;
        }

        // 2. Poll
        while (true) {
            await new Promise(r => setTimeout(r, 500));

            const checkRes = await fetch(`${API_BASE}/task/${taskId}`);
            if (checkRes.status === 404) throw new Error("Task lost");

            const checkData = await checkRes.json();

            if (checkData.status === "completed") {
                return checkData.result;
            }
            if (checkData.status === "failed") {
                throw new Error(checkData.error);
            }
            if (checkData.status === "cancelled") {
                throw new Error("Cancelled");
            }
        }
    })();

    const handle = {
        taskId: null, // will be set later
        idPromise: idPromise,
        resultPromise: resultPromise
    };

    mergeCache[key] = handle;
    return handle;
}


async function createNewSectionFromTemplate(newTitle, templateContent, item, oldTitle) {
    // Let's add it to currentStructure immediately so it persists as a "Draft Section".
    currentStructure.push({
        title: newTitle,
        level: 3, // Default for features/milestones
        content: templateContent
    });

    // Now reassign the merge to this new title
    reassignMerge(item, oldTitle, newTitle);
}

function reassignMerge(item, oldTitle, newTitle) {
    // 1. Remove from old
    if (pendingMerges[oldTitle]) {
        pendingMerges[oldTitle].shift();
        if (pendingMerges[oldTitle].length === 0) {
            delete pendingMerges[oldTitle];
        }
    }

    // 2. Add to new
    if (!pendingMerges[newTitle]) {
        pendingMerges[newTitle] = [];
    }
    // We put it at the FRONT if we want to deal with it now, or BACK?
    // Since we are "moving" the actively viewed item, we probably want to view it immediately under the new context.
    // So put at FRONT.
    pendingMerges[newTitle].unshift(item);

    // 3. Update Item's internal section tag (for consistency, though less used)
    item.section = newTitle;

    // 4. Refresh UI
    renderStructure();

    // 5. Select it in its new home
    selectPendingMerge(newTitle);

    notify(`Moved merge to '${newTitle}'.`);
}

function discardMerge() {
    const title = document.getElementById('diffView').dataset.targetSection;

    notify("Discarded.");

    // 1. Cleanup Queue
    if (pendingMerges[title]) {
        pendingMerges[title].shift();
        if (pendingMerges[title].length === 0) {
            delete pendingMerges[title];
        }
    }

    // 2. Auto-Advance
    handleAutoAdvance(title);
}

function handleAutoAdvance(lastTitle) {
    renderStructure();

    if (pendingMerges[lastTitle] && pendingMerges[lastTitle].length > 0) {
        selectPendingMerge(lastTitle);
        return;
    }

    const remainingTitles = Object.keys(pendingMerges);
    if (remainingTitles.length > 0) {
        selectPendingMerge(remainingTitles[0]);
    } else {
        // All merges completed - show commit modal
        document.getElementById('diffView').classList.add('hidden');
        document.getElementById('arbiterControls').classList.add('hidden');
        notify("All merges completed! Please add a commit message.");
        document.getElementById('inputArea').value = "";

        // Show commit modal
        showCommitModal();
    }
}

function notify(msg) {
    document.getElementById('statusMessage').textContent = msg;
}

async function copyProtocol() {
    const text = document.getElementById('protocolTemplate').value;
    try {
        await navigator.clipboard.writeText(text);
        notify("Protocol copied to clipboard!");
    } catch (err) {
        console.error('Failed to copy:', err);
        notify("Failed to copy protocol.");
    }
}

// Initial Load
window.onload = async () => {
    await loadBlueprints();
    initDocument();
};

/* --- New Logic for Structure & Smart Insert --- */

let currentViewedSection = null;

async function viewFullDocument() {
    const name = document.getElementById('docName').value;
    notify("Loading full document...");

    // Clear any active section selection
    document.querySelectorAll('.structure-item').forEach(el => el.classList.remove('active'));

    // Hide diff view if visible
    document.getElementById('diffView').classList.add('hidden');
    document.getElementById('arbiterControls').classList.add('hidden');

    // Get and display full document
    const content = await fetch(`${API_BASE}/spec/${name}`)
        .then(res => res.json())
        .then(data => data.content);

    document.getElementById('docPreview').textContent = content;

    currentViewedSection = null; // We are viewing full doc
    updateEditButtonState();
    notify("Full document displayed.");
}

function updateEditButtonState() {
    const editBtn = document.getElementById('btnEditSection');
    const summaryBtn = document.getElementById('btnGenerateSummary');

    if (editBtn) {
        if (currentViewedSection) {
            editBtn.classList.remove('hidden');
            editBtn.textContent = `Edit '${currentViewedSection}'`;
        } else {
            editBtn.classList.add('hidden');
        }
    }

    if (summaryBtn) {
        // Show the Summary button only if the current active blueprint allows it
        let allowsSummary = false;

        if (currentViewedSection) {
            const lowerSection = currentViewedSection.toLowerCase();
            for (const bp of appBlueprints) {
                if (bp.type === 'numerable') {
                    const prefix = bp.template_prefix.replace(/^#+\s*/, '').trim().toLowerCase();
                    if (lowerSection.startsWith(prefix)) {
                        allowsSummary = bp.allows_summary;
                        break;
                    }
                }
            }
        }

        if (allowsSummary) {
            summaryBtn.classList.remove('hidden');
        } else {
            summaryBtn.classList.add('hidden');
        }
    }
}

function editCurrentSection() {
    if (!currentViewedSection) return;

    // Find item
    const item = currentStructure.find(i => i.title === currentViewedSection);
    if (!item) return;

    // Load into Arbiter
    // Treat it like a merge where Original = Current, and New = Current (so no diff effectively, or empty New?)
    // We want to EDIT the Proposed Merge area.

    // Setup partial view
    document.getElementById('diffView').classList.remove('hidden');
    document.getElementById('arbiterControls').classList.remove('hidden');

    document.getElementById('originalContent').textContent = item.content;
    document.getElementById('newContent').textContent = "(Manual Edit Mode)";

    // Populate Selector
    populateTargetSelector(item.title);

    // Prepare Merge View
    const mergedArea = document.getElementById('mergedContent');
    mergedArea.value = item.content; // Pre-fill with existing

    document.getElementById('diffView').dataset.targetSection = item.title;

    notify(`Editing '${item.title}'...`);

    // Scroll to arbiter
    document.getElementById('panelRight').scrollTo(0, 0);
}


/**
 * generateFeatureSummary
 *
 * Calls POST /api/summary for the currently viewed Feature section.
 * On success, delegates to insertOrReplaceSummarySubsection() to splice
 * the summary text in as the first subsection of the feature and commit.
 */
async function generateFeatureSummary() {
    if (!currentViewedSection) return;

    const name = document.getElementById('docName').value;
    const btn = document.getElementById('btnGenerateSummary');

    // Disable button during generation
    btn.disabled = true;
    btn.textContent = '⏳ Generating…';
    notify(`Generating summary for '${currentViewedSection}'…`);

    try {
        const res = await fetch(`${API_BASE}/summary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, section: currentViewedSection })
        });

        if (!res.ok) {
            const err = await res.json();
            notify(`Error: ${err.detail || 'Summary generation failed.'}`);
            return;
        }

        const data = await res.json();
        await insertOrReplaceSummarySubsection(currentViewedSection, data.summary, name);
        notify(`Summary generated for '${currentViewedSection}'.`);

    } catch (e) {
        console.error('[Summary] Unexpected error:', e);
        notify('Error generating summary. Check the console.');
    } finally {
        btn.disabled = false;
        btn.textContent = '✨ Summary';
    }
}

/**
 * insertOrReplaceSummarySubsection
 *
 * Inserts or replaces the `#### Summary` subsection at the top of a feature
 * section (immediately after the `### Feature: …` header line) in
 * currentStructure, then commits the full document to the server and
 * refreshes the structure and preview.
 *
 * @param {string} sectionTitle - Exact title of the feature section.
 * @param {string} summaryText  - Plain-prose summary produced by Ollama.
 * @param {string} docName      - Current document name.
 */
async function insertOrReplaceSummarySubsection(sectionTitle, summaryText, docName) {
    const idx = currentStructure.findIndex(i => i.title === sectionTitle);
    if (idx === -1) {
        console.error(`[Summary] Section '${sectionTitle}' not found in currentStructure.`);
        return;
    }

    const item = currentStructure[idx];
    const summaryBlock = `#### Summary\n\n${summaryText}\n`;
    const lines = item.content.split('\n');

    // Find the first line (the ### header) and split the rest
    let headerEndIdx = 0;
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].trim() === '') {
            headerEndIdx = i;
        } else if (i > 0) {
            headerEndIdx = i;
            break;
        }
    }

    // Strip any existing #### Summary subsection from the content
    const SUMMARY_HEADER = '#### Summary';
    let bodyLines = lines;
    const summaryStart = lines.findIndex(l => l.trim() === SUMMARY_HEADER);
    if (summaryStart !== -1) {
        // Remove lines from #### Summary up to (but not including) the next #### header
        let summaryEnd = summaryStart + 1;
        while (summaryEnd < lines.length && !lines[summaryEnd].trim().startsWith('####')) {
            summaryEnd++;
        }
        bodyLines = [...lines.slice(0, summaryStart), ...lines.slice(summaryEnd)];
    }

    // Find the header line (### ...) and re-insert #### Summary right after it
    const headerLineIdx = bodyLines.findIndex(l => l.trim().startsWith('#'));
    const insertAfter = headerLineIdx === -1 ? 0 : headerLineIdx + 1;
    const newLines = [
        ...bodyLines.slice(0, insertAfter),
        '',
        ...summaryBlock.split('\n'),
        ...bodyLines.slice(insertAfter)
    ];

    // Update in-memory structure
    currentStructure[idx].content = newLines.join('\n');

    // Persist full document
    const fullContent = currentStructure.map(i => i.content).join('\n');
    await fetch(`${API_BASE}/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: docName, content: fullContent })
    });

    // Refresh structure from server so the new sub-section appears correctly
    await loadStructure();

    // Re-display the section
    const content = getSectionWithChildren(sectionTitle);
    document.getElementById('docPreview').textContent = content || currentStructure[idx]?.content || '';
}

function findSmartInsertionIndex(title, level) {
    console.log(`[SmartInsert] Calculating index for '${title}'...`);
    // 1. Determine Parent Context via Blueprints
    let parentTitle = "";
    let itemLevel = level;

    // Find matching blueprint
    const lowerTitle = title.toLowerCase();
    for (const bp of appBlueprints) {
        if (bp.type === 'numerable') {
            const prefix = bp.template_prefix.replace(/^#+\s*/, '').trim().toLowerCase();
            if (lowerTitle.startsWith(prefix)) {
                parentTitle = bp.parent_section;
                itemLevel = bp.level; // Use the proper level
                break;
            }
        }
    }

    // If no specific parent logic, return -1 (append)
    if (!parentTitle) {
        console.log(`[SmartInsert] No parent context found.`);
        return -1;
    }

    // 2. Find Parent Index
    const parentIndex = currentStructure.findIndex(i => i.title === parentTitle);

    if (parentIndex === -1) {
        console.log(`[SmartInsert] Parent '${parentTitle}' not found in structure.`);
        return -1; // Parent not found, append
    }

    // 3. Find End of Parent Block
    // We assume the Block ends when we hit a section with Level <= Parent Level (2)
    // The parent is at parentIndex.
    let insertIndex = parentIndex + 1;
    for (let i = parentIndex + 1; i < currentStructure.length; i++) {
        if (currentStructure[i].level <= 2) {
            console.log(`[SmartInsert] Block end found at '${currentStructure[i].title}' (Level ${currentStructure[i].level}).`);
            break;
        }
        insertIndex = i + 1;
    }

    console.log(`[SmartInsert] Inserting at index ${insertIndex} (after '${currentStructure[insertIndex - 1]?.title}').`);
    return insertIndex;
}

// Overwrite commitMerge to include Smart Insertion
async function commitMerge() {
    const title = document.getElementById('diffView').dataset.targetSection;
    const content = document.getElementById('mergedContent').value;
    const name = document.getElementById('docName').value;

    notify("Committing...");

    // 1. Update In-Memory Structure
    let index = currentStructure.findIndex(i => (i.title || "(Untitled)") === title);

    if (index !== -1) {
        // Update existing
        currentStructure[index].content = content;
    } else {
        // Create new section
        const newItem = { title: title, level: 3, content: content }; // Default level 3

        // Smart Insertion
        const smartIndex = findSmartInsertionIndex(title, 3);
        if (smartIndex !== -1) {
            currentStructure.splice(smartIndex, 0, newItem);
        } else {
            currentStructure.push(newItem);
        }
    }

    // 2. Persist to Server
    const fullContent = currentStructure.map(i => i.content).join('\n');
    await fetch(`${API_BASE}/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, content: fullContent })
    });

    // 3. Cleanup Queue
    if (pendingMerges[title]) {
        pendingMerges[title].shift();
        if (pendingMerges[title].length === 0) {
            delete pendingMerges[title];
        }
    }

    notify("Merged successfully!");

    // 4. Auto-Advance (Refreshes Tree)
    handleAutoAdvance(title);

    // Explicitly select the just-edited section so user can see it (if queue empty)
    // If handleAutoAdvance picked something else, that's fine.
    // But if we want to "Read what we just edited", we might want to view it?
    // User flow: Commit -> Next Item usually. 
    // IF user was doing Manual Delete/Edit, maybe stay?
    // User requested: "I expect that after saving... it will redraw the tree" -> handleAutoAdvance calls renderStructure.
}

function populateTargetSelector(currentTitle) {
    const select = document.getElementById('targetSectionSelect');
    select.innerHTML = "";

    // 1. Structure Options
    currentStructure.forEach(item => {
        const option = document.createElement('option');
        option.value = item.title;
        option.textContent = item.title;
        if (item.title === currentTitle) {
            option.selected = true;
        }
        select.appendChild(option);
    });

    // 2. Add current pending new sections if not already in structure
    Object.keys(pendingMerges).forEach(t => {
        if (!currentStructure.find(i => i.title === t)) {
            const option = document.createElement('option');
            option.value = t;
            option.textContent = `+ ${t} (New)`;
            if (t === currentTitle) {
                option.selected = true;
            }
            select.appendChild(option);
        }
    });

    // 3. Separator
    const sep = document.createElement('option');
    sep.disabled = true;
    sep.textContent = "─ CREATE NEW ─";
    select.appendChild(sep);

    // 4. Special Options
    const optFeature = document.createElement('option');
    optFeature.value = "__NEW_FEATURE__";
    optFeature.textContent = "Create New Feature...";
    select.appendChild(optFeature);

    const optMilestone = document.createElement('option');
    optMilestone.value = "__NEW_MILESTONE__";
    optMilestone.textContent = "Create New Milestone...";
    select.appendChild(optMilestone);

    // Bind Event
    select.onchange = (e) => handleTargetChange(e.target.value, currentTitle);
}

async function handleTargetChange(newTarget, currentTitle) {
    if (newTarget === currentTitle) return;

    // Get the item currently being viewed
    const items = pendingMerges[currentTitle];
    if (!items || items.length === 0) return;
    const itemToMove = items[0]; // We only move the head of the queue logic-wise for now

    if (newTarget === "__NEW_FEATURE__") {
        const name = prompt("Enter Feature Name:");
        if (!name) {
            populateTargetSelector(currentTitle); // Reset reset
            return;
        }
        const fullTitle = `Feature: ${name}`;
        await createNewSectionFromTemplate(fullTitle, generateFeatureTemplate(name), itemToMove, currentTitle);
        return;
    }

    if (newTarget === "__NEW_MILESTONE__") {
        const name = prompt("Enter Milestone Name:");
        if (!name) {
            populateTargetSelector(currentTitle); // Reset
            return;
        }
        const fullTitle = `Milestone: ${name}`;
        await createNewSectionFromTemplate(fullTitle, generateMilestoneTemplate(name), itemToMove, currentTitle);
        return;
    }

    // Standard Reassign
    reassignMerge(itemToMove, currentTitle, newTarget);
}

/* ========================================
   VERSION CONTROL FUNCTIONS
   ======================================== */

async function loadVersions() {
    const name = document.getElementById('docName').value;
    try {
        const res = await fetch(`${API_BASE}/versions/${name}`);
        if (!res.ok) return;

        const data = await res.json();
        const select = document.getElementById('versionSelect');
        select.innerHTML = '';

        // Add current option
        const currentOpt = document.createElement('option');
        currentOpt.value = 'current';
        currentOpt.textContent = `Current (v${data.current_version})`;
        currentOpt.selected = true;
        select.appendChild(currentOpt);

        // Add historical versions in reverse order (newest first)
        const versions = data.versions || [];
        for (let i = versions.length - 1; i >= 0; i--) {
            const v = versions[i];
            if (v.version === data.current_version) continue; // Skip current

            const opt = document.createElement('option');
            opt.value = v.version;
            opt.textContent = `v${v.version} - ${v.comment.substring(0, 30)}${v.comment.length > 30 ? '...' : ''}`;
            select.appendChild(opt);
        }
    } catch (e) {
        console.error('Failed to load versions:', e);
    }
}

async function switchToVersion() {
    const select = document.getElementById('versionSelect');
    const selectedValue = select.value;

    if (selectedValue === 'current') {
        // Just reload the current document
        await initDocument(false);
        return;
    }

    const version = parseInt(selectedValue);
    const name = document.getElementById('docName').value;

    if (!confirm(`Rollback to version ${version}? This will create a new version with the old content.`)) {
        select.value = 'current'; // Reset selection
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/rollback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, version })
        });

        const data = await res.json();
        notify(`Rolled back to v${version}. Now at v${data.new_version}.`);

        // Reload document and versions
        await initDocument(false);
    } catch (e) {
        console.error('Rollback failed:', e);
        notify('Rollback failed.');
        select.value = 'current';
    }
}

async function toggleVersionDisplay() {
    const checkbox = document.getElementById('showVersions');
    showVersionInfo = checkbox.checked;

    const name = document.getElementById('docName').value;

    try {
        const res = await fetch(`${API_BASE}/download/${name}?annotated=${showVersionInfo}`);
        const data = await res.json();

        document.getElementById('docPreview').textContent = data.content;
        updateDownloadLink();

        notify(showVersionInfo ? 'Showing version annotations' : 'Showing clean document');
    } catch (e) {
        console.error('Failed to toggle version display:', e);
    }
}

function updateDownloadLink() {
    const name = document.getElementById('docName').value;
    const link = document.getElementById('downloadLink');
    link.href = `${API_BASE}/download/${name}?annotated=${showVersionInfo}`;
}

function showCommitModal() {
    document.getElementById('commitModal').classList.remove('hidden');
    document.getElementById('commitMessage').value = '';
    document.getElementById('commitMessage').focus();
}

function closeCommitModal() {
    document.getElementById('commitModal').classList.add('hidden');
    hideMergeBlockingIndicator();
    mergeInProgress = false;
}

async function submitCommitMessage() {
    const message = document.getElementById('commitMessage').value.trim();
    const name = document.getElementById('docName').value;

    if (!message) {
        alert('Please enter a commit message.');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/validate-merge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, comment: message })
        });

        const data = await res.json();
        notify(`${data.message} Now at v${data.version}.`);

        // Close modal and reset state
        closeCommitModal();

        // Reload versions
        await loadVersions();

    } catch (e) {
        console.error('Validation failed:', e);
        notify('Failed to validate merge.');
    }
}

function showMergeBlockingIndicator() {
    document.getElementById('mergeBlockingIndicator').classList.remove('hidden');
}

function hideMergeBlockingIndicator() {
    document.getElementById('mergeBlockingIndicator').classList.add('hidden');
}

// Copy to clipboard function
async function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    let text = '';

    // Handle both textarea and div elements
    if (element.tagName === 'TEXTAREA') {
        text = element.value;
    } else {
        text = element.textContent;
    }

    try {
        await navigator.clipboard.writeText(text);
        notify('Copied to clipboard!');
    } catch (err) {
        console.error('Failed to copy:', err);
        notify('Failed to copy to clipboard.');
    }
}

// Add origin content to merge result
function addOriginToMerge() {
    const originalContent = document.getElementById('originalContent').textContent;
    const mergedArea = document.getElementById('mergedContent');

    // Preserve current content and append
    const currentValue = mergedArea.value.trim();

    // Skip if current value is an error message or empty
    if (!currentValue || currentValue.includes('Error:') || currentValue === 'Generation stopped by user.') {
        mergedArea.value = originalContent;
    } else {
        // Append with separator
        mergedArea.value = currentValue + '\n\n' + originalContent;
    }

    notify('Original content added to merge result.');
}

// Add new input content to merge result
function addNewInputToMerge() {
    const newContent = document.getElementById('newContent').textContent;
    const mergedArea = document.getElementById('mergedContent');

    // Preserve current content and append
    const currentValue = mergedArea.value.trim();

    // Skip if current value is an error message or empty
    if (!currentValue || currentValue.includes('Error:') || currentValue === 'Generation stopped by user.') {
        mergedArea.value = newContent;
    } else {
        // Append with separator
        mergedArea.value = currentValue + '\n\n' + newContent;
    }

    notify('New input content added to merge result.');
}

/* ========================================
   FORMAT SWITCHING FUNCTIONS
   ======================================== */

// Track format state
let sectionOriginalFormat = 'markdown';
let sectionNewFormat = 'markdown';
let mergeResultFormat = 'markdown';
let documentFormat = 'markdown';
let isEditingDocument = false;

async function toggleSectionFormat(which) {
    const name = document.getElementById('docName').value;
    const targetSection = document.getElementById('diffView').dataset.targetSection;

    if (!targetSection) {
        notify('No section selected');
        return;
    }

    if (which === 'original') {
        const btn = document.getElementById('btnToggleOriginal');
        const mdDiv = document.getElementById('originalContent');
        const htmlDiv = document.getElementById('originalContentHtml');

        if (sectionOriginalFormat === 'markdown') {
            // Switch to HTML
            notify('Rendering original as HTML...');
            try {
                const res = await fetch(`${API_BASE}/render/section/${name}/${encodeURIComponent(targetSection)}?format=html`);
                const data = await res.json();
                htmlDiv.innerHTML = data.content;
                mdDiv.classList.add('hidden');
                htmlDiv.classList.remove('hidden');
                btn.textContent = 'View as Markdown';
                sectionOriginalFormat = 'html';
            } catch (e) {
                console.error('Failed to render HTML:', e);
                notify('Failed to render HTML');
            }
        } else {
            // Switch to Markdown
            mdDiv.classList.remove('hidden');
            htmlDiv.classList.add('hidden');
            btn.textContent = 'View as HTML';
            sectionOriginalFormat = 'markdown';
        }
    } else if (which === 'new') {
        const btn = document.getElementById('btnToggleNew');
        const mdDiv = document.getElementById('newContent');
        const htmlDiv = document.getElementById('newContentHtml');

        if (sectionNewFormat === 'markdown') {
            // Switch to HTML - render the current text content
            notify('Rendering new content as HTML...');
            try {
                const markdownContent = mdDiv.textContent;
                // Use a temporary render by posting to the API
                const res = await fetch(`${API_BASE}/render/section/${name}/${encodeURIComponent(targetSection)}?format=html`);
                const data = await res.json();

                // Actually, we need to render the NEW content, not the section
                // Let's render it client-side using the document endpoint as a workaround
                // For now, just use basic markdown rendering
                htmlDiv.innerHTML = `<pre>${markdownContent}</pre>`;
                mdDiv.classList.add('hidden');
                htmlDiv.classList.remove('hidden');
                btn.textContent = 'View as Markdown';
                sectionNewFormat = 'html';
            } catch (e) {
                console.error('Failed to render HTML:', e);
                notify('Failed to render HTML');
            }
        } else {
            // Switch to Markdown
            mdDiv.classList.remove('hidden');
            htmlDiv.classList.add('hidden');
            btn.textContent = 'View as HTML';
            sectionNewFormat = 'markdown';
        }
    }
}

async function toggleMergeFormat() {
    const btn = document.getElementById('btnToggleMerge');
    const textarea = document.getElementById('mergedContent');
    const htmlDiv = document.getElementById('mergedContentHtml');
    const name = document.getElementById('docName').value;

    if (mergeResultFormat === 'markdown') {
        // Switch to HTML - render current textarea content
        notify('Rendering merge result as HTML...');
        const markdownContent = textarea.value;

        if (!markdownContent) {
            notify('No content to render');
            return;
        }

        try {
            // Use the preview endpoint to render arbitrary markdown
            const res = await fetch(`${API_BASE}/render/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, text: markdownContent })
            });
            const data = await res.json();

            htmlDiv.innerHTML = data.content;
            textarea.classList.add('hidden');
            htmlDiv.classList.remove('hidden');
            btn.textContent = 'Edit as Markdown';
            mergeResultFormat = 'html';
            notify('HTML preview (editing disabled)');
        } catch (e) {
            console.error('Failed to render HTML:', e);
            notify('Failed to render HTML');
        }
    } else {
        // Switch to Markdown
        textarea.classList.remove('hidden');
        htmlDiv.classList.add('hidden');
        btn.textContent = 'View as HTML';
        mergeResultFormat = 'markdown';
        notify('Markdown editing enabled');
    }
}

async function toggleDocumentFormat() {
    const name = document.getElementById('docName').value;
    const btn = document.getElementById('btnToggleDocument');
    const mdPre = document.getElementById('docPreview');
    const htmlDiv = document.getElementById('docPreviewHtml');
    const editBtn = document.getElementById('btnEditDocument');

    if (documentFormat === 'markdown') {
        // Switch to HTML
        notify('Rendering document as HTML...');
        try {
            const res = await fetch(`${API_BASE}/render/document/${name}?format=html`);
            const data = await res.json();
            htmlDiv.innerHTML = data.content;
            mdPre.classList.add('hidden');
            htmlDiv.classList.remove('hidden');
            btn.textContent = 'View as Markdown';
            editBtn.classList.add('hidden'); // Can't edit in HTML mode
            documentFormat = 'html';
        } catch (e) {
            console.error('Failed to render HTML:', e);
            notify('Failed to render HTML');
        }
    } else {
        // Switch to Markdown
        mdPre.classList.remove('hidden');
        htmlDiv.classList.add('hidden');
        btn.textContent = 'View as HTML';
        // Show edit button only if not viewing a section
        if (!currentViewedSection) {
            editBtn.classList.remove('hidden');
        }
        documentFormat = 'markdown';
    }
}

async function editFullDocument() {
    const name = document.getElementById('docName').value;

    // Get current document
    const content = await fetch(`${API_BASE}/spec/${name}`)
        .then(res => res.json())
        .then(data => data.content);

    // Show edit mode
    document.getElementById('documentEditArea').value = content;
    document.getElementById('documentEditMode').classList.remove('hidden');
    document.getElementById('docPreview').classList.add('hidden');
    document.getElementById('docPreviewHtml').classList.add('hidden');
    document.getElementById('btnToggleDocument').classList.add('hidden');
    document.getElementById('btnEditDocument').classList.add('hidden');

    isEditingDocument = true;
    notify('Editing full document...');
}

function cancelDocumentEdit() {
    document.getElementById('documentEditMode').classList.add('hidden');
    document.getElementById('docPreview').classList.remove('hidden');
    document.getElementById('btnToggleDocument').classList.remove('hidden');
    document.getElementById('btnEditDocument').classList.remove('hidden');

    isEditingDocument = false;
    notify('Edit cancelled');
}

async function saveDocumentEdit() {
    const name = document.getElementById('docName').value;
    const content = document.getElementById('documentEditArea').value;

    // Prompt for commit message
    const message = prompt('Enter a commit message for this edit:');

    if (!message) {
        notify('Save cancelled - commit message required');
        return;
    }

    try {
        // Save the document
        await fetch(`${API_BASE}/commit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content })
        });

        // Validate merge to bump version
        await fetch(`${API_BASE}/validate-merge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, comment: message })
        });

        // Exit edit mode
        cancelDocumentEdit();

        // Reload document and structure
        await initDocument(false);

        notify(`Document saved: ${message}`);
    } catch (e) {
        console.error('Failed to save document:', e);
        notify('Failed to save document');
    }
}

// Update viewFullDocument to show edit button
async function viewFullDocument() {
    const name = document.getElementById('docName').value;
    notify("Loading full document...");

    // Clear any active section selection
    document.querySelectorAll('.structure-item').forEach(el => el.classList.remove('active'));

    // Hide diff view if visible
    document.getElementById('diffView').classList.add('hidden');
    document.getElementById('arbiterControls').classList.add('hidden');

    // Get and display full document
    const content = await fetch(`${API_BASE}/spec/${name}`)
        .then(res => res.json())
        .then(data => data.content);

    document.getElementById('docPreview').textContent = content;

    currentViewedSection = null; // We are viewing full doc

    // Show edit document button
    document.getElementById('btnEditDocument').classList.remove('hidden');
    updateEditButtonState();
    notify("Full document displayed.");
}

// =============================================================================
// GEMINI AI MODE
// =============================================================================

let currentGeminiSessionId = null;  // active session UUID, or null
let geminiModelsLoaded = false;      // load model list only once
let linkedSections = [];             // sections to prepend in next message (cleared after send)

// ---------------------------------------------------------------------------
// Mode toggle
// ---------------------------------------------------------------------------

function switchMode(mode) {
    const manualPanel = document.getElementById('manualPanel');
    const geminiPanel = document.getElementById('geminiPanel');
    const btnManual = document.getElementById('btnModeManual');
    const btnGemini = document.getElementById('btnModeGemini');

    if (mode === 'gemini') {
        manualPanel.classList.add('hidden');
        geminiPanel.classList.remove('hidden');
        btnManual.classList.remove('active');
        btnGemini.classList.add('active');
        if (!geminiModelsLoaded) {
            _loadGeminiModels();
            _populateScopeSelect();
            geminiModelsLoaded = true;
        }
    } else {
        geminiPanel.classList.add('hidden');
        manualPanel.classList.remove('hidden');
        btnGemini.classList.remove('active');
        btnManual.classList.add('active');
    }
}

async function _loadGeminiModels() {
    try {
        const res = await fetch(`${API_BASE}/gemini/models`);
        const data = await res.json();
        const sel = document.getElementById('geminiModel');
        sel.innerHTML = '';
        data.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === data.default) opt.selected = true;
            sel.appendChild(opt);
        });
    } catch (e) {
        console.warn('[Gemini] Could not load models:', e);
    }
}

function _populateScopeSelect() {
    const sel = document.getElementById('geminiScope');
    sel.innerHTML = '<option value="document">Document level</option>';
    currentStructure
        .filter(s => s.level <= 3)
        .forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.title;
            opt.textContent = '\u00a0'.repeat((s.level - 1) * 2) + s.title;
            sel.appendChild(opt);
        });
}

// ---------------------------------------------------------------------------
// Session lifecycle
// ---------------------------------------------------------------------------

async function startGeminiSession() {
    const model = document.getElementById('geminiModel').value;
    const scope = document.getElementById('geminiScope').value;
    const sendCtx = document.getElementById('geminiSendContext').checked;
    const docName = document.getElementById('docName').value;

    if (currentGeminiSessionId) {
        await _destroySession(currentGeminiSessionId);
    }

    notify('Starting Gemini chat session...');
    try {
        const res = await fetch(`${API_BASE}/gemini/session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_name: docName,
                scope: scope,
                model: model,
                include_global_context: sendCtx,
            }),
        });
        if (!res.ok) {
            const err = await res.json();
            notify(`Error: ${err.detail}`);
            return;
        }
        const data = await res.json();
        currentGeminiSessionId = data.session_id;

        // Reset chat UI
        document.getElementById('geminiHistory').innerHTML = '';
        document.getElementById('geminiContextChips').innerHTML = '';
        linkedSections = [];
        _updateExchangeCounter(0);
        document.getElementById('geminiWarning').classList.add('hidden');

        // Enable controls
        document.getElementById('geminiInput').disabled = false;
        document.getElementById('btnGeminiSend').disabled = false;
        document.getElementById('btnLinkSection').disabled = false;
        document.getElementById('btnGeminiEndSession').disabled = false;
        document.getElementById('btnGeminiNewSession').textContent = '\u21ba New Chat';

        _appendChatBubble('system', `Session started \u2014 scope: ${data.scope} \u2014 model: ${data.model}`);
        notify('Gemini session started.');
    } catch (e) {
        notify(`Failed to start session: ${e}`);
        console.error('[Gemini] startSession error:', e);
    }
}

async function endGeminiSession() {
    if (!currentGeminiSessionId) return;
    await _destroySession(currentGeminiSessionId);
    currentGeminiSessionId = null;

    document.getElementById('geminiInput').disabled = true;
    document.getElementById('btnGeminiSend').disabled = true;
    document.getElementById('btnLinkSection').disabled = true;
    document.getElementById('btnGeminiEndSession').disabled = true;
    document.getElementById('btnGeminiNewSession').textContent = '\u25b6 Start Chat';
    document.getElementById('geminiExchangeCount').classList.add('hidden');

    _appendChatBubble('system', 'Session ended.');
    notify('Gemini session ended.');
}

async function _destroySession(sessionId) {
    try {
        await fetch(`${API_BASE}/gemini/session/${sessionId}`, { method: 'DELETE' });
    } catch (e) {
        console.warn('[Gemini] destroy session error (ignoring):', e);
    }
}

// ---------------------------------------------------------------------------
// Sending messages
// ---------------------------------------------------------------------------

async function sendGeminiMessage() {
    const input = document.getElementById('geminiInput');
    const message = input.value.trim();
    if (!message) { notify('Please type a message first.'); return; }
    if (!currentGeminiSessionId) { notify('No active session.'); return; }

    // Snapshot & clear chips immediately
    const sectionsToSend = [...linkedSections];
    linkedSections = [];
    document.getElementById('geminiContextChips').innerHTML = '';

    document.getElementById('btnGeminiSend').disabled = true;
    input.value = '';

    const label = message + (sectionsToSend.length ? `\n\n\ud83d\udcce ${sectionsToSend.join(', ')}` : '');
    _appendChatBubble('user', label);

    try {
        const res = await fetch(`${API_BASE}/gemini/chat/${currentGeminiSessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, linked_sections: sectionsToSend }),
        });

        if (!res.ok) {
            const err = await res.json();
            _appendChatBubble('system', `Error: ${err.detail}`);
            notify(`Gemini error: ${err.detail}`);
            return;
        }

        const data = await res.json();
        _appendChatBubble('model', data.discussion);
        _updateExchangeCounter(data.exchange_count);

        if (data.warn) {
            document.getElementById('geminiWarning').classList.remove('hidden');
        }

        if (data.updates && data.updates.length > 0) {
            geminiUpdatesToPendingMerges(data.updates, data.commit_summary || 'Gemini AI update');
            _appendChatBubble('system',
                `\ud83d\udcdd ${data.updates.length} spec update(s) queued \u2014 review in sidebar.`);
        }

    } catch (e) {
        _appendChatBubble('system', `Network error: ${e}`);
        notify('Network error sending message.');
        console.error('[Gemini] sendMessage error:', e);
    } finally {
        document.getElementById('btnGeminiSend').disabled = false;
        input.focus();
    }
}

// ---------------------------------------------------------------------------
// Convert Gemini updates into pendingMerges (same shape as processInput)
// ---------------------------------------------------------------------------

function geminiUpdatesToPendingMerges(updates, commitSummary) {
    window._geminiCommitSummary = commitSummary;  // used when validate-merge fires
    mergeInProgress = true;
    showMergeBlockingIndicator();

    updates.forEach(u => {
        const section = u.target_section;
        const newText = u.content;
        const summary = u.change_summary;

        if (!pendingMerges[section]) pendingMerges[section] = [];
        pendingMerges[section].push({
            section,
            original_text: getRealOriginal(section, ''),
            new_text: newText,
            summary,
        });

        // Pre-warm merge cache for first item
        getMergePromise(section, getRealOriginal(section, ''), newText);
    });

    renderStructure();
    notify(`Gemini proposed ${updates.length} update(s). Review them in the sidebar.`);
}

// ---------------------------------------------------------------------------
// Link section dialog
// ---------------------------------------------------------------------------

function openLinkSectionDialog() {
    const sel = document.getElementById('linkSectionSelect');
    sel.innerHTML = '';
    currentStructure.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.title;
        opt.textContent = '\u00a0'.repeat((s.level - 1) * 2) + s.title;
        sel.appendChild(opt);
    });
    document.getElementById('linkSectionDialog').showModal();
}

function confirmLinkSection() {
    const sel = document.getElementById('linkSectionSelect');
    const title = sel.value;
    if (!title || linkedSections.includes(title)) {
        document.getElementById('linkSectionDialog').close();
        return;
    }
    linkedSections.push(title);
    _addContextChip(title);
    document.getElementById('linkSectionDialog').close();
}

function _addContextChip(title) {
    const container = document.getElementById('geminiContextChips');
    const chip = document.createElement('span');
    chip.className = 'context-chip';

    const label = document.createTextNode(title + ' ');
    chip.appendChild(label);

    const remove = document.createElement('button');
    remove.textContent = '\u00d7';
    remove.title = 'Remove';
    remove.onclick = () => {
        linkedSections = linkedSections.filter(s => s !== title);
        chip.remove();
    };
    chip.appendChild(remove);
    container.appendChild(chip);
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

function _appendChatBubble(role, text) {
    const history = document.getElementById('geminiHistory');
    const div = document.createElement('div');
    div.className = `chat-bubble ${role}`;
    div.textContent = text;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}

function _updateExchangeCounter(count) {
    const badge = document.getElementById('geminiExchangeCount');
    badge.textContent = `${count} / 15 turns`;
    badge.classList.remove('hidden');
    badge.classList.toggle('warn', count >= 15);
}


