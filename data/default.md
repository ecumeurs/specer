# Document Title

## Lexicon

## Context, Aim & Integration

### Context

### Aim

### Architectural Stack

The system operates on a strict three-tier separation of concerns to ensure simulation integrity and client responsiveness.

| Layer | Responsibility | Authority |
| --- | --- | --- |
| **The Engine** | State production, delta computation, and "Heartbeat" simulation. | Absolute (Source of Truth) |
| **The Controller** | ACL validation, "What-If" forecasting, and contract brokerage. | Logical (Gatekeeper) |
| **The UI** | Diegetic visualization, forecast HUDs, and command buffering. | Visual (Presentation) |

#### Communication Flow

1. **The Forecast Loop:** UI requests a simulation from the Controller -> Controller queries Engine state -> Controller runs local "What-If" logic -> UI renders "Ghost Bars."
2. **The Command Loop:** UI sends batch instructions -> Controller validates funds/ACL -> Controller issues authoritative command to Engine -> Engine updates State.
## Features

### Feature 1

#### Context, Aim & Integration

#### Constraints

#### User Stories

#### Technical Requirements

#### API

#### Data Layer

#### Validation

#### Dependencies

#### Other Notes

Error merging content: Timeout after 60s: ReadTimeout
## Roadmap

### Milestone 1

#### Content

#### Validation


### Milestone: 1: The Scavenger (MVP)

#### Content

* **Phase 1 (Basic Idle):** Resource Controller (RawReality, Credits), Building classes, and basic City View.
* **Phase 2 (Survival Loop):** Shielding system (Credit drain), Threat Controller (RNG Raids), and Stability HUD.


#### Validation
Error merging content: Timeout after 60s: ReadTimeout