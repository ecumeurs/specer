# 📑 SPECIFICATION: ATOMIC TRACEABLE DOCUMENTATION (ATD)

**Version:** 1.0

**Status:** Implementation Ready

**Core Philosophy:** Documentation is code. Logic must be traceable, secable, and verifiable without constant LLM overhead.

---

## 1. THE ATOM STRUCTURE (The Template)

Every "Atom" is a Markdown file. To minimize LLM search costs, we use a **Strict Header** that allows for deterministic (regex/string) searching.

### 📄 `template.atom.md`

```markdown
---
id: [UNIQUE_SLUG]
human_name: [Human Readable Name]
type: [MECHANIC | API | UI | DATA | LORE | RULE]
version: [1.0]
status: [DRAFT | REVIEW | STABLE]
priority: [CORE | SECONDARY | FLAVOR]
tags: [tag1, tag2]
parents: 
  - [[parent_atom_id]]
dependents:
  - [[dependency_atom_id]]
---

# NAME OF THE ATOM

## 🎯 INTENT
[One sentence: Why does this exist?]

## ⚙️ THE RULE / LOGIC
[The "Meat". Use pseudo-code, formulas, or strict bullet points.]
- Formula: Value = X * Y
- Condition: If A then B

## 🔌 TECHNICAL INTERFACE (The Bridge)
- **API Endpoint:** `POST /v1/example`
- **Code Tag:** `@spec-link [[UNIQUE_SLUG]]`
- **Related Issue:** `#123`

## 🧪 EXPECTATION (For Testing)
[What must be true for this to be "Passed"?]
- Input 10 -> Output 20.

```

---

## 2. THE TOOLKIT (Deterministic Logic)

To save tokens, the Agent uses these **local CLI tools** before ever calling the LLM.

### 🔍 Tool 1: The Crawler (`atd-crawl`)

* **Action:** Scans the `/docs` and `/src` folders.
* **Logic:** Uses Regex to find `[[id]]` and `@spec-link [[id]]`.
* **Output:** A JSON Dependency Graph.
* **LLM Usage:** 0%.

### 🏗️ Tool 2: The Assembler (`atd-assemble`)

* **Action:** Stitches atoms together based on a "Path."
* **Logic:** Starting at a Parent Atom, it follows all `links` recursively.
* **Output:** A single, temporary Markdown file for the human/LLM to read.
* **LLM Usage:** 0% (Assembly) | 10% (Optional "Polish" for humans).

### ⚖️ Tool 3: The Auditor (`atd-audit`)

* **Action:** Compares a tagged code block to its linked Atom.
* **Logic:** Feeds the LLM *only* the specific Code Function and the specific Atom Logic.
* **Output:** Pass/Fail + Reason.
* **LLM Usage:** Surgical (High value, low volume).

---

## 3. USER WORKFLOWS

### A. The Architect (High/Low Level)

1. **Creation:** The Architect prompts the Agent: "Set Caravan Taxes to 21%."
2. **Linking:** The Agent creates the file and asks: "Should I link this to the `Global_Tax_Law` atom?"
3. **Validation:** The Agent runs `atd-crawl` to ensure no circular dependencies were created.

### B. The Developer

1. **Implementation:** The Dev writes code and adds `// @spec-link [[Caravan_Taxes]]`.
2. **Verify:** The Dev runs `atd-audit`. The Agent confirms: "Code logic matches the formula in the Atom."
3. **Pivot:** If the Dev changes the code logic, the Agent flags the Atom as `STATUS: OUTDATED`.

### C. The Test Engineer

1. **Generation:** The Agent reads the `## 🧪 EXPECTATION` section of an Atom.
2. **Automation:** The Agent generates a Unit Test boilerplate based on that expectation.

---

## 4. IMPACT ANALYSIS (The "Overwatch" Logic)

When a user modifies an Atom, the Agent follows this "Ripple" logic:

1. **Identify Change:** Atom `X` was modified.
2. **Trace:** `atd-crawl` finds all linked Atoms and Code files.
3. **Notify:** "Warning: Changing `X` affects `Y` (Atom) and `Z.ts` (Code). These are now 'Unverified'."
4. **Resolve:** The user must either update `Y` and `Z` or tell the Agent to re-audit them.

---

## 5. MINIMIZING LLM USAGE (Cost Control)

| Task | Method | LLM Cost |
| --- | --- | --- |
| **Searching for "Caravan"** | Local Index / Grep | **$0.00** |
| **Mapping Dependencies** | Regex Crawling | **$0.00** |
| **Generating an Investor Doc** | Assembly + LLM Polish | **Low** |
| **Verifying Code vs. Spec** | Surgical Prompting | **Medium** |
| **Writing the Doc from Scratch** | Creative Generation | **High** |


---

This is the pivot that turns a documentation tool into a **Development Governance System**.

By separating the **Architect** and **Developer** modes, you ensure the agent doesn't suffer from "identity confusion." The Architect creates the "Contract," and the Developer fulfills it. If the Developer finds the contract impossible to fulfill, they don't just change it—they flag it for the Architect.

Here are the drafts for your `SKILL.md` and `AGENT.md` to be placed alongside your repo.

---

# 📜 SKILL.md: Atomic Traceable Documentation (ATD)

**Skill Name:** `atd_management`

**Description:** Manages the lifecycle, traceability, and verification of atomic documentation fragments and their relationship to source code.

## 🛠️ Toolset

1. **`atd_query(search_term)`**: Deterministic search through `@id` and `@links` headers. No LLM used.
2. **`atd_map_impact(atom_id)`**: Crawls the repo for `@spec-link [[atom_id]]` in code and `[[atom_id]]` in other atoms.
3. **`atd_validate_logic(atom_logic, code_snippet)`**: **LLM-Powered.** Compares doc rules against implementation.
4. **`atd_stitch(atom_ids[])`**: Combines fragments into a temporary cohesive document for context.

To support this new mode, we add a few analytical tools to the agent's belt:

1. **`atd_report_gaps()`**: Scans the repo to find any Atom in `STABLE` status that has 0 links in the codebase.
2. **`atd_generate_snapshot(theme)`**: Uses the **Assembler** to pull atoms and applies an LLM persona to write a flowing document (e.g., a "Product Roadmap" for an investor).

---

# 🤖 AGENT.md: Behavior & Personas

**Identity:** Upsilon System Architect & Dev Assistant.

**Instruction:** You must always operate in one of the two following modes. Never mix them without explicit user overwatch.

## 🏛️ MODE: ARCHITECT

**Trigger:** User discusses specs, GDD, blueprints, or "High-level" changes.

* **Goal:** Maintain the integrity of the "Universe Rules."
* **Behavior:**
* Announce mode change to user. Can only change mode again with explicit user request.
* When a new idea is discussed, identify if it should be a **New Atom** or an **Update** to an existing one.
* **Pro-active Warning:** Before committing a change, run `atd_map_impact`. If a change to Atom A affects Atom B, you MUST report: *"Warning: This alteration spreads to [List of Atoms]. Should I proceed with a bulk update or flag them as 'Outdated'?"*

### **Sub-Mode: Deconstructor**

* **Action:** When provided with a bulk text input or a file to process, the Agent must identify **Independent Logical Units**.
* **Constraint:** Every extracted Atom must be able to stand alone. If Atom A requires information from Atom B to make sense, the Agent must automatically generate the `[[links]]` between them during the dissection. Some may already be existing atoms and should be updated instead of recreated.
* Merging process may require to update the linked atoms to ensure they are still relevant, run `atd_map_impact` to check for impact. Ensure inter sub-atoms coherence. (For example, we can't have one atom stating value > 5 when the other states value < 5, unless there is a specific reason for it, which should be documented in the atom)
* Merging process requires user approval before committing.
* **Refinement:** The Architect can say *"This is too granular"* or *"Split the formula from the description."* The Agent must re-propose the Atoms based on this feedback.


## 💻 MODE: DEVELOPER

**Trigger:** User discusses implementation, bug fixing, or "Coding."

* **Goal:** Ensure code is a perfect reflection of the ATD.
* **Behavior:**
* Announce mode change to user. Can only change mode again with explicit user request.
* **Constraint-First:** Before writing a single line of code, search for `@spec-link` tags relevant to the file.
* **Inconsistency Reporting:** If the user asks for code that violates an Atom (e.g., "Make Caravans instant" when the doc says "Caravans have a return leg"), **DO NOT IMPLEMENT.** * **Response:** *"The current specification (Atom: Commerce_Caravan) requires a return leg. Implementing this change would create a Logic Mismatch. Should we switch to Architect Mode to update the spec, or stay in Dev Mode and follow the current rules?"*

## 🔎 MODE: ANALYST

**Trigger:** User asks for reports, summaries, status checks, or "human-readable" documentation (Pitch decks, UI briefs, etc.).

* **Goal:** Audit the ecosystem, detect "unwritten" gaps, and export the "Atoms" into "Narratives."
* **Behavior:**
* Announce mode change to user. Can only change mode again with explicit user request.
* **Read-Only:** The Analyst never modifies an Atom or a Line of Code. It only reads and reports.
* **Gap Detection:** It identifies "Ghost Atoms" (Atoms with no linked code) or "Orphaned Code" (Code with no `@spec-link`).
* **Impact Visualization:** It generates "Narrative Flows"—showing how a single change ripples through the entire Project universe.
* **Translation:** It synthesizes the fragmented Atomic Docs into specific formats for different audiences (e.g., "Simplified GDD for Artists").

---

## 🧩 The Three-Persona Dynamic

| Persona | Primary Action | Responsibility |
| --- | --- | --- |
| **Architect** | Writes/Edits Atoms | Logical consistency of the Universe. |
| **Developer** | Writes/Edits Code | Functional implementation of the Specs. |
| **Analyst** | Reads/Generates Reports | Human communication and System health. |

---

## 🔄 The Analyst Workflow Example

**User:** *"Analyst, I need a summary for my UI designer on how the Caravan system should look and feel across Tiers 1 through 3."*

1. **Search:** The Analyst runs `atd_query` for "Caravan" and "Aesthetics."
2. **Gather:** It finds `Commerce_Caravan.atom.md` and the `Aesthetic_Pillars.atom.md`.
3. **Synthesize:** It doesn't show you the files; it writes:

> *"For T1, the UI should be 'Scavenger' style: rusted, flickering, showing high risk. For T3, it shifts to 'Logistics' style: cleaner, more grid-based. The key data points the designer needs to display are [X, Y, Z]."*

**User:** *"Analyst, how much of the Master Blueprint is actually implemented in the code right now?"*

1. **Audit:** It runs `atd_report_gaps()`.
2. **Report:** *"70% of the Core Atoms are linked to code. However, the 'Intrigue Sabotage' mechanics in Tier 3 are completely unlinked. You have a spec, but no code implementation."*

---

## 🔄 The Interaction Loop

1. **The Architect Flow (The "Discussion"):** You talk to the LLM. It doesn't just "write a doc"—it "files atoms." It says: *"I've updated the `Global_Stability` atom. This impacts 3 other modules. I've marked them as 'Pending Review'."*
2. **The Developer Flow (The "Work"):** You start coding. The LLM reads the linked atoms. It acts as a **"Linter for Logic."** It catches errors not because the syntax is wrong, but because the *intent* is wrong.

---

Dissecting a monolithic legacy document (or a fresh brainstorm) into discrete Atoms is the **"Infection Point"** where the Architect does the most heavy lifting. If the Agent simply "cuts" the text blindly, you get garbage atoms.

The Architect needs a **"Deconstruction Skill"** that identifies "Conceptual Boundaries."

---

## 🛠️ The Deconstruction Tool: `atd_dissect`

This tool doesn't just split text by headers; it analyzes **responsibility**. When an Architect feeds a document to the Agent, the Agent follows this "Dissection Protocol."

### 1. The Semantic Break-Point Analysis

The Agent scans the input for shifts in **Domain**.

* **Narrative/Flavor** -> Lore Atom
* **Input/Output/Formula** -> Mechanic Atom
* **Data Structure/URL** -> API Atom
* **Layout/Color/Visuals** -> UI Atom

### 2. The Extraction Workflow

Instead of doing it all at once, the Agent presents a **Dissection Proposal**:

> **Agent (Architect Mode):** "I've analyzed the 'Commerce' document. I propose breaking it into 4 Atoms:
> 1. `Commerce_Loop` (Mechanic) - Covers the extract/sell cycle.
> 2. `Shielding_Sinks` (Rule) - Covers the subscription costs.
> 3. `Caravan_Return` (Mechanic) - Covers the tech-unlock lag.
> 4. `Rim_Aesthetics` (UI) - Covers the flickering/rust visuals.
> 
> 
> **Should I proceed with the extraction, or would you like to merge/split these further?"**


---

## 🏗️ Technical Implementation of the Skill

To implement `atd_dissect` as an agent skill, we use a **Two-Pass LLM Strategy** to save tokens while maintaining precision.

### Pass 1: Structural Mapping (Low Token Cost)

The Agent generates a list of "Slugs" and "Short Summaries" of potential atoms found in the text.

* *Output:* A JSON list of proposed filenames and their primary responsibility.

### Pass 2: Atomic Refinement (Surgical Cost)

Once the Architect approves the map, the Agent processes the text block-by-block, filling in the **ATD Template** (ID, Type, Rules, Tags) for each approved slug.

---

## 🔄 Example Interaction

**Architect:** *"Here is my brain dump for the 'Intrigue' module. Turn this into atoms."* (User pastes 5 paragraphs).

**Agent:** *"Analysis complete. I see a conflict: Your 'Hacking' section mentions 'Corporate Security,' but we don't have an atom for that yet. I propose creating a 'Global_Security' atom in the Master Blueprint and then a 'Hacking_Minigame' atom for the module. Would you like me to generate that link?"*

**Architect:** *"Yes. Do it."*

---

## 🛠️ The Merging Skill: `atd_reconcile`

When the Architect provides new input, the Agent must perform a **"Conflict Check"** against the existing Atom store before proposing new files.

### 1. Collision Detection (The "Check")

The Agent compares the *intent* of the new text against the existing IDs and tags.

* **Case A (The Extension):** The new text adds detail to an existing Atom.
* *Action:* Propose an **Update**.


* **Case B (The Collision):** The new text contradicts an existing Atom.
* *Action:* Flag a **Conflict**.


* **Case C (The Redundancy):** The new text describes a mechanic already fully covered.
* *Action:* Propose **Discarding** the input segment.



### 2. The Reconciliation Report

Instead of a "Dissection Proposal," the Agent provides a **Reconciliation Map**. This is the core of the "User Overwatch" UI.

| Proposed Atom | Relationship | Target | Logic Change |
| --- | --- | --- | --- |
| `Caravan_Speed` | **UPDATE** | `Commerce_Logistics` | Adds "Weather Multipliers." |
| `Hacking_Tools` | **NEW** | N/A | Initial draft for Intrigue gadgets. |
| `Corporate_Tax` | **CONFLICT** | `Master_Blueprint_Econ` | Input says 5%, but Atom says 10%. |

---

## 🏛️ Updated AGENT.md: The Architect's Merge Logic

Add these instructions to the **Architect Mode** to handle the "Inbound vs. Store" collision:

### **Sub-Mode: Reconciler**

* **Action:** When deconstructing text, the Agent must first query the existing repository for overlapping semantic IDs.
* **Conflict Resolution Protocol:** 1.  **Summarize the Clash:** "In the new text, you mentioned X. However, `Atom_Y` already defines this as Z."
2.  **Request Direction:** "Should I: (A) Overwrite the Atom with the new text, (B) Ignore the new text and keep the Atom, or (C) Merge them into a combined version?"
* **Self-Correction:** If the new input contradicts itself (e.g., Paragraph 1 says a feature is free, Paragraph 5 says it costs 10 credits), the Agent must flag the internal inconsistency before filing any atoms.

---

## 🧩 How "Merging" Saves the Codebase

This is where the link to the Developer persona becomes critical. If the Architect chooses to **Merge/Update** an atom:

1. The Agent identifies that `Atom_A` is updated.
2. It runs the **Impact Crawler** (from the `SKILL.md`).
3. It warns the Architect: *"Merging this change will mark 4 files in the `src/` folder as 'Outdated'. Are you sure you want to proceed with this logical pivot?"*

---

## 🏗️ Implementation: The "Merge" Skill API

To make this functional, the `atd_reconcile` tool should work like a **Git Merge for Game Design**:

* **Step 1: Diffing.** The LLM generates a "Semantic Diff"—not a line-by-line code diff, but a list of changed *rules*.
* **Step 2: Shadowing.** The Agent creates "Shadow Atoms" (temporary drafts).
* **Step 3: Committing.** Only after the Architect clicks "Approve Merge" are the `.atom.md` files in the repository actually overwritten.
