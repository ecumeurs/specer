const API_BASE = "/api";

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
    document.getElementById('downloadLink').href = `${API_BASE}/spec/${name}`;

    await loadStructure();
}

let currentStructure = [];
let pendingMerges = {}; // Map title -> Array<Match>
let mergeCache = {}; // Map key -> Promise<MergeResult>

async function loadStructure() {
    const name = document.getElementById('docName').value;
    const res = await fetch(`${API_BASE}/structure/${name}`);
    const data = await res.json();
    currentStructure = data.structure;
    renderStructure();
}

function renderStructure() {
    const list = document.getElementById('structureList');
    list.innerHTML = "";

    const renderedTitles = new Set();

    currentStructure.forEach((item, index) => {
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
                document.getElementById('docPreview').textContent = item.content;
                notify(`Viewing section: ${item.title}`);
                document.getElementById('diffView').classList.add('hidden');
                document.getElementById('arbiterControls').classList.add('hidden');

                currentViewedSection = item.title;
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

    // Trigger background pre-merge for the FIRST item of each section
    Object.keys(pendingMerges).forEach(title => {
        const firstItem = pendingMerges[title][0];
        const currentContent = getRealOriginal(title, firstItem.original_text);
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
        // Auto-Template Logic for New Sections
        const lowerTitle = title.toLowerCase();
        if (lowerTitle.startsWith("feature:") || lowerTitle.startsWith("feature ")) {
            const name = title.replace(/feature[:\s]*/i, "").trim();
            return generateFeatureTemplate(name);
        }
        if (lowerTitle.startsWith("milestone:") || lowerTitle.startsWith("milestone ")) {
            const name = title.replace(/milestone[:\s]*/i, "").trim();
            return generateMilestoneTemplate(name);
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

// Fetch or retrieve promise
function getMergePromise(sectionTitle, original, newText) {
    const key = getCacheKey(original, newText);

    if (mergeCache[key]) {
        return mergeCache[key];
    }

    const promise = (async () => {
        console.log(`[Background] Fetching merge for ${sectionTitle}...`);
        const res = await fetch(`${API_BASE}/diff`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ original, new: newText })
        });
        const data = await res.json();
        return data.merged;
    })();

    mergeCache[key] = promise;
    return promise;
}

async function selectPendingMerge(title) {
    const items = pendingMerges[title];
    if (!items || items.length === 0) return;

    const currentMatch = items[0]; // Get the first one

    // 1. Determine "Original" Content
    let realOriginal = getRealOriginal(title, currentMatch.original_text);

    // 2. Setup partial view
    document.getElementById('diffView').classList.remove('hidden');
    document.getElementById('arbiterControls').classList.remove('hidden'); // Show drop down
    document.getElementById('originalContent').textContent = realOriginal;
    document.getElementById('newContent').textContent = currentMatch.new_text;

    // Populate Selector
    populateTargetSelector(title);

    // 3. Prepare Merge View
    const mergedArea = document.getElementById('mergedContent');
    const spinner = document.getElementById('mergeSpinner');

    mergedArea.value = "";
    document.getElementById('diffView').dataset.targetSection = title;

    // Show spinner
    spinner.classList.remove('hidden');
    notify(`Generating merge for '${title}' (${items.length} remaining)...`);

    try {
        // 4. Fetch Merge (Cache-aware)
        const result = await getMergePromise(title, realOriginal, currentMatch.new_text);
        mergedArea.value = result;
    } catch (e) {
        console.error(e);
        mergedArea.value = "Error generating merge.";
        notify("Error generating merge.");
    } finally {
        spinner.classList.add('hidden');
    }

    notify(`Review merge for '${title}'.`);
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

function generateFeatureTemplate(name) {
    return `### Feature: ${name}

#### Context, Aim & Integration

#### Constraints

#### User Stories

#### Technical Requirements

#### API

#### Data Layer

#### Validation

#### Dependencies

#### Other Notes
`;
}

function generateMilestoneTemplate(name) {
    return `### Milestone: ${name}

#### Content

#### Validation
`;
}

async function createNewSectionFromTemplate(newTitle, templateContent, item, oldTitle) {
    // 1. Add this "New Section" to pendingMerges if not exists, but we want it to be backed by something.
    // Actually, we can just treat it like a "New Section" discovered by process.
    // BUT, we want the "Original" to be the Template, not empty.

    // We can simulate this by pushing a fake item to currentStructure temporarily? 
    // Or simpler: We insert it into currentStructure NOW as a placeholder, 
    // so getRealOriginal finds it.

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


async function commitMerge() {
    const title = document.getElementById('diffView').dataset.targetSection;
    const content = document.getElementById('mergedContent').value;
    const name = document.getElementById('docName').value;

    notify("Committing...");

    // 1. Update In-Memory Structure
    let item = currentStructure.find(i => (i.title || "(Untitled)") === title);
    if (!item) {
        // Create new section stub if it doesn't exist
        item = { title: title, level: 2, content: "" };
        currentStructure.push(item);
    }
    item.content = content;

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

    // 4. Auto-Advance
    handleAutoAdvance(title);
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
        document.getElementById('diffView').classList.add('hidden');
        document.getElementById('arbiterControls').classList.add('hidden');
        notify("All merges completed!");
        document.getElementById('inputArea').value = "";
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
window.onload = () => initDocument();

/* --- New Logic for Structure & Smart Insert --- */

let currentViewedSection = null;

async function viewFullDocument() {
    const name = document.getElementById('docName').value;
    notify("Fetching full document...");
    const res = await fetch(`${API_BASE}/structure/${name}`);
    // Actually structure endpoint returns structure, we want raw text?
    // We can use initDocument(false) which loads it? 
    // Or just a specific endpoint. 
    // Let's use get_document logic (which is what init does roughly but init parses).
    // Let's rely on re-fetching the doc via a simple GET if possible, or just Init.
    // initDocument(false) does: fetch /init -> msg, content.
    // content IS the full doc.
    await initDocument(false);
    notify("Full document loaded.");
    currentViewedSection = null; // We are viewing full doc
    updateEditButtonState();
}

function updateEditButtonState() {
    const btn = document.getElementById('btnEditSection');
    if (btn) {
        if (currentViewedSection) {
            btn.classList.remove('hidden');
            btn.textContent = `Edit '${currentViewedSection}'`;
        } else {
            btn.classList.add('hidden');
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

function findSmartInsertionIndex(title, level) {
    // 1. Determine Parent Context
    let parentTitle = "";
    if (title.toLowerCase().startsWith("feature")) parentTitle = "Features";
    if (title.toLowerCase().startsWith("milestone")) parentTitle = "Roadmap";

    // If no specific parent logic, return -1 (append)
    if (!parentTitle) return -1;

    // 2. Find Parent Index
    const parentIndex = currentStructure.findIndex(i => i.title === parentTitle);
    if (parentIndex === -1) return -1; // Parent not found, append

    // 3. Find End of Parent Block
    // We assume the Block ends when we hit a section with Level <= Parent Level (2)
    // The parent is at parentIndex.
    let insertIndex = parentIndex + 1;
    for (let i = parentIndex + 1; i < currentStructure.length; i++) {
        if (currentStructure[i].level <= 2) {
            break;
        }
        insertIndex = i + 1;
    }

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
    // Reconstruct full doc
    // We need to be careful: currentStructure items usually contain headers inside 'content' or separate?
    // looking at backend: `current_section = {"title": title, "level": level, "content": [line]}` includes header.
    // So `content` is the full string including `### Title`.
    // Wait, if `content` includes Header, then `process_text` regex logic might be duplicating it if we merge purely content?
    // Server `get_structure` includes the header line in `content`.
    // UI `generateFeatureTemplate` includes `### Feature: ...`.
    // So 'content' is full block. Safe.

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
