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
let pendingMerges = {}; // Map title -> Match Data

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

        if (pendingMerges[item.title]) {
            div.classList.add('pending-merge');
        }

        div.onclick = () => {
            document.querySelectorAll('.structure-item').forEach(el => el.classList.remove('active'));
            div.classList.add('active');

            if (pendingMerges[item.title]) {
                selectPendingMerge(item.title);
            } else {
                document.getElementById('docPreview').textContent = item.content;
                notify(`Viewing section: ${item.title}`);
                document.getElementById('diffView').classList.add('hidden');
            }
        };

        list.appendChild(div);
    });

    // Render "New Sections" (Pending merges that didn't match existing structure)
    Object.keys(pendingMerges).forEach(title => {
        if (!renderedTitles.has(title)) {
            const div = document.createElement('div');
            div.className = "structure-item level-2 pending-merge new-section";
            div.textContent = `+ ${title} (New)`;

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

    // 1. Process / Match
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

    // Reset pending
    pendingMerges = {};

    // Process results
    matchData.matches.forEach(m => {
        pendingMerges[m.section] = m;
    });

    // Update Sidebar
    renderStructure();

    notify(`Found ${matchData.matches.length} updates. Check the warning icons in the structure.`);
}

async function selectPendingMerge(title) {
    const startData = pendingMerges[title];
    if (!startData) return;

    document.getElementById('diffView').classList.remove('hidden');
    document.getElementById('originalContent').textContent = startData.original_text;
    document.getElementById('mergedContent').value = "Generating...";

    notify(`Generating merge for '${title}'...`);

    const diffRes = await fetch(`${API_BASE}/diff`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            original: startData.original_text,
            new: startData.new_text
        })
    });
    const diffData = await diffRes.json();

    document.getElementById('mergedContent').value = diffData.merged;

    // Tag the view so commit knows what we are merging
    document.getElementById('diffView').dataset.targetSection = title;
    notify(`Review merge for '${title}'.`);
}

async function commitMerge() {
    const name = document.getElementById('docName').value;
    const content = document.getElementById('mergedContent').value;
    const targetTitle = document.getElementById('diffView').dataset.targetSection;

    notify("Committing... (Merging section back to doc)");

    if (!targetTitle) {
        // Fallback
        await fetch(`${API_BASE}/commit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content })
        });
    } else {
        // Update structure in memory
        const item = currentStructure.find(i => (i.title || "(Untitled)") === targetTitle);
        if (item) {
            item.content = content;
        } else {
            // New section? Or not found?
            // If it's a new section (suggested by semantic search failing), we might need to append it.
            // But currentStructure is read from file. 
            // Phase 3 simplification: We won't handle appending totally new sections perfectly yet unless they match "New Section" stub.
            console.warn("Could not find section in memory structure, appending or failing gracefully.");
        }

        // Reassemble full doc
        const fullContent = currentStructure.map(i => i.content).join('\n');

        await fetch(`${API_BASE}/commit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content: fullContent })
        });

        // Remove from pending
        delete pendingMerges[targetTitle];
    }

    notify("Merged successfully!");
    document.getElementById('diffView').classList.add('hidden');
    document.getElementById('inputArea').value = ""; // Clear input

    // Refresh Doc
    initDocument();
}

function discardMerge() {
    document.getElementById('diffView').classList.add('hidden');
    notify("Merge discarded.");
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
