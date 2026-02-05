---
trigger: always_on
---

---
trigger: always_on
---

# AGENTS OPERATING PROCEDURE

## AGENT WORKFLOW PROTOCOL: "Architect-First, Code-Later"

### PHASE 1: Data & Structure (The Contract)
**Goal:** Define the "What". **Reuse existing structures before creating new ones.**

1.  **Discovery & Audit:**
    * Search the codebase for existing structures that match the domain (e.g., if handling users, check for existing `User` or `Profile` definitions).
    * **Reuse Rule:** Prioritize reusing an existing structure even if it contains fields you don't immediately need (excess data is acceptable to avoid duplication).
    * **Extension Rule:** If an existing structure is *almost* perfect but missing fields, prefer **extending** it (inheritance/composition) over creating a copy.

2.  **Creation Logic:**
    * **New Feature:** Create new structures only if the data represents a truly new domain concept.
    * **Refactoring:** Create new structures only if explicitly instructed to decouple or refactor.
    * **Composite Exception (Leeway):** You are authorized to create specific **Input/Output** wrappers (DTOs) that group multiple existing structures or primitives to facilitate clean API signatures or documentation.
    * **Framework Specific:** Distinguish between **Persistence Models** (Database) and **Data Contracts** (API/Internal passing). Do not conflate them if the framework dictates separation (e.g., ORM vs Serializers).

3.  **File Strategy:**
    * **One Primary Structure per File:** Major entities must have their own dedicated definition file.
    * **Naming:** The filename must match the structure name to facilitate retrieval.

4.  **Documentation Strategy:**
    * You must add extensive standard documentation (e.g., Docstrings, TSDoc) to every field explaining:
        * What the data represents.
        * Any constraints (optionality, validation rules).
### PHASE 2: Scaffolding (The Blueprint)
**Goal:** Map out the flow and compile context.
1.  **Signatures Only:** Write the function/class signatures. **Do not write the implementation body yet.**
    * *Guideline:* Keep "Business Logic" separate from "Transport Logic" (e.g., Do not put complex logic inside an HTTP View or Controller; use a dedicated Service or internal function).
2.  **Context Compilation:** In the docstring of the function:
    * Summarize the goal.
    * **Compile Side-Info:** Organize messy context into a usable list.
    * **Step-by-Step Plan:** Write a pseudo-code list of steps.
    * **Unknowns:** Clearly mark steps requiring further analysis.
### PHASE 3: The Test Harness (The Proof)
**Goal:** Prove valid behavior before coding.
1.  **Create Test File:** Create the test suite file using the project's standard naming convention (e.g., `_test.go`, `.spec.js`, `test_*.py`).
2.  **Coverage Requirements:** You must generate at least **3 tests**:
    * **Main Case:** The "Happy Path". If the feature has modes (e.g., a generator with 3 settings), create one test for *each* mode.
    * **Edge Case 1:** Boundary conditions or malformed inputs.
    * **Edge Case 2:** Error handling or unexpected states.
3.  **Mocking:** Setup necessary mocks or stubs based on the structures defined in Phase 1.

### PHASE 4: STOP & REVIEW
**CRITICAL:** Do not implement the function bodies yet.
1.  Output the message: *"Structures, Blueprints, and Tests are ready for review. Please check `[File Names]`."*
2.  Wait for the user to type "Approved" or provide feedback.
3.  **Only after approval:** Implement the logic inside the empty function bodies.

---

## Documentation Standards

As you work on features:

* **Continuation check:** Determine if this is a continuation of a feature or a new one.
* **If Continuation:** Check the containing **Module/App Directory** for `Architecture.md` and `Feature.md` and **READ THEM**.
    * `Architecture.md`: Technical layout and internal mechanics.
    * `Feature.md`: Business logic and drive.
    * **Update Strategy:** Update these files at every prompt with appropriate alterations.
* **If New Feature:** Write both `Architecture.md` and `Feature.md`.
* **Legacy Code:** If files are missing:
    * Analyze the directory and start a new `Architecture.md`.
    * Propose a business interpretation in `Feature.md` and ask for review.

**Warnings:** Warn the user when instructions conflict with `Feature.md`.
**Scope:** Applies to all folders containing source code, modules, services, or shared libraries (e.g., Django Apps, `utils`, `lib`).

### Template: Architecture.md
```md
# Module/Directory Name
One-liner of the intent behind this directory's feature objective.

## Identification
Unique ID of the feature composed of:
* Feature name
* Scope context (e.g., backend, api, frontend, shared library, database).

## Layout
Tree review of the files in this module (one-liners explaining role).

## API / Interface
High Level API access for external users/modules:
* Inputs: Methods & Structures detailed.
* Outputs: Structure detailed.
* Example of usage.

## Internal Mechanics
Brief review of internal mechanics; must mention key structures and methods used at least once.

## Tests
Location and strategy of test files associated with this module.

## Related
Some features are disjointed across multiple spaces in this project (e.g., server-side logic vs. client-side usage). Track every related directory here. The Identification key should help link them.
```

### Template: Feature.md
```md
# Module/Directory Name
One-liner of the intent behind this directory's feature objective.

## Drive
Origin of the request or requirement.

## Planned usage
How this integrates into the project as a whole.
* Target Audience/Users.
* User Stories / Use Cases.

## Business Logic
Explain the business logic driving this feature. Detail as much as possible (rules, calculations, workflows).

## Expectation & Achievement
Use this section to track progress.
* [ ] Expectations not yet met (annotate why: undoable, missing info, dependent on other modules).
* [x] Achieved expectations.
```