# Static Frontend
Delivers the Single Page Application (SPA) UI for the Specer Semantic Spec Merger.

## Identification
* Feature: Specer UI
* Scope: frontend

## Layout
* `index.html`: Main entry point, layout structure, and widget containers.
* `style.css`: Visual styling, layout utilities, and component styles.
* `app.js`: Application logic, API interaction, DOM manipulation, and state management.

## API / Interface
This is a browser-side module, consuming the backend API.
* Inputs: User interactions (clicks, text input).
* Outputs: DOM updates, API calls to `/api/...`.

## Internal Mechanics
* **State Management**: Uses global variables (`currentStructure`, `pendingMerges`, `mergeCache`) to track document state and merge operations.
* **Initialization**: `initDocument()` fetches initial data.
* **Protocol Processing**: `processInput()` sends text to `POST /api/process`.
* **Merging**: `selectPendingMerge()` and `getMergePromise()` handle background task polling and result display.
* **Structure Rendering**: `renderStructure()` dynamically builds the sidebar tree.
* **Summary Generation**: `generateFeatureSummary()` calls `POST /api/summary` for the active Feature section. `insertOrReplaceSummarySubsection()` splices or replaces the `#### Summary` subsection at the top of the section and commits the document.

## Tests
Currently no dedicated frontend tests found in this directory.

## Related
* `server/`: Backend API provider.
