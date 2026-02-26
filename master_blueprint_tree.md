# PROJECT: UPSILON MASTER SPECIFICATION

**Version:** 0.1 (Experimental/Draft)

**Status:** KISS - Scaffolding Phase

**Focus:** Ecosystem Synergy & Data Flow

---

## THE ECOSYSTEM (Parent)

*The high-level "Source of Truth" for the universe state.*

### Narrative Pillar

> **The State of Upsilon:** [Brief 2-3 sentence summary of the current planetary situation, e.g., "A harsh settlement on a resource-rich but hostile planet."]

### Global Universe Variables (The State Machine)

| Variable Name | Description | Range/Type | Affects |
| --- | --- | --- | --- |
| `planet_stability` | Overall health of the colonies | 0 - 100% | All Apps |
| `resource_scarcity` | Global multiplier for extraction costs | 1.0x - 5.0x | Commerce |
| `intel_purity` | Accuracy of enemy movement data | 0.0 - 1.0 | Battle / Intrigue |

---

## MODULE SPECIFICATIONS (The Children)

*Functional "Black Boxes." Focus on Inputs/Outputs.*

### [Module Name: e.g., Commerce]

* **Core Loop:** [e.g., Extract -> Refine -> Sell -> Reinvest]
* **Primary Input (From Core):** [e.g., Market Demand, Resource Node Availability]
* **Primary Output (To Core):** [e.g., Credits, Manufactured Goods, Infrastructure Upgrades]

### [Module Name: e.g., Intrigue]

* **Core Loop:** [e.g., Infiltrate -> Hack -> Sabotage/Influence]
* **Primary Input:** [e.g., Faction Tension, City Security Levels]
* **Primary Output:** [e.g., Tactical Intel, Market Manipulation Modifiers]

---

## BASE API (Inter-App Communication)

*The "Contracts" that allow the apps to talk to Upsilon Core.*

### Data Schema (Common Objects)

```json
{
  "player_id": "UUID",
  "timestamp": "ISO-8601",
  "action_type": "STRING",
  "payload": { "key": "value" }
}

```

### Key Endpoints (The Verbs)

* `POST /update-state`: Reports an event (e.g., "Battle Won") to the Core.
* `GET /fetch-modifiers`: Pulls global variables for app-side calculations.
* `POST /sync-inventory`: Handles items moving between Commerce and Battle.

---

## META-ARCHITECTURE (The Engine)

*Infrastructure requirements to keep the lights on.*

### Authentication & Identity

* **Method:** [e.g., Simple JWT / Firebase / Supabase]
* **Scope:** Single-sign-on across all 3 game clients.

### Logging & Monitoring

* **Strategy:** Event-based logging (Action, User, Success/Fail).
* **Goal:** Track "Pivot metrics" to see which app players spend the most time in.

### Admin / God Mode

* **Requirement:** A dashboard to manually adjust `planet_stability` if the economy collapses during testing.
