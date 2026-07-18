# Mekong Delta Agri-Logistics Orchestrator

**Smart multimodal logistics & inter-regional transshipment for the Mekong Delta**
Built for the Vietnam AI Innovation Challenge - Agriculture track, in partnership with the Cần Thơ People's Committee.

## The Problem

Cần Thơ sits at the center of the Mekong Delta, positioned to serve as the region's
multimodal transshipment hub for agricultural goods moving toward Ho Chi Minh City. Today,
that potential is underused: shippers lack a systematic way to compare transport options,
consolidation at the transshipment point is manual and reactive, and there is no
real-time, data-driven layer coordinating cost, time, and perishability across the network.
The result is higher logistics cost, inefficient use of road and waterway capacity, and
avoidable losses on time-sensitive produce.

## The Solution

We built a two-layer AI decision system that sits on top of the existing road and waterway
network connecting four provincial collection hubs (Vị Thanh, Long Xuyên, Sóc Trăng, Vĩnh
Long) to Cần Thơ and on to Ho Chi Minh City:

```
Provincial Hub
      │  new order (cargo type, weight, timestamp)
      ▼
┌───────────────────────────────┐
│  Layer 1 - Route & Cost       │   Evaluates 5 transport options per order:
│  Optimizer                    │   direct road to HCMC, or via Cần Thơ using
└───────────────────────────────┘   any road/waterway combination.
      │  route via Cần Thơ selected
      ▼
┌───────────────────────────────┐
│  Layer 2 - Forecast &         │   Consolidates loads at Cần Thơ per outbound
│  Dispatch Agent               │   mode, forecasts incoming volume, and decides
└───────────────────────────────┘   when to dispatch a vehicle.
      │
      ▼
┌───────────────────────────────┐
│  Backend & Real-Time Platform │   Connects both AI layers, persists state,
└───────────────────────────────┘   streams live updates to the dashboard.
      │
      ▼
Operations Dashboard (Provincial Hub view · Cần Thơ Hub view)
```

The core idea: **Layer 1 answers "which route," Layer 2 answers "when to leave."** Separating
routing from dispatch consolidation lets each hub make an immediate, cost-optimal routing
decision while the Cần Thơ hub independently optimizes vehicle utilization by waiting for
the right combination of load, time, and weather conditions - rather than dispatching on a
fixed schedule or a fixed load threshold.

## How It Works

**Route & Cost Optimizer.** When a hub logs a new shipment, the optimizer prices out all
five viable routes in real time - factoring in freight rates, fuel prices, weather-driven
speed/cost penalties, spoilage risk for the specific cargo, and transshipment handling fees -
and returns a ranked recommendation with a full cost breakdown, plus the reasoning for any
route that isn't currently viable (e.g. weather closure, deadline risk, no compatible
vehicle).

**Forecast & Dispatch Agent.** For shipments routed through Cần Thơ, the agent tracks
accumulating load per outbound mode (road and waterway are optimized independently), forecasts
how much additional volume will arrive over the next several hours, and continuously
re-evaluates whether to dispatch now, wait for more load, or wait for a vehicle. The decision
logic layers a small set of safety constraints - vehicle availability, weather-driven route
closures, and hard deadlines for perishable cargo - underneath a weighted scoring model that
balances load fill, cargo urgency, and route risk. Every decision comes with a machine-readable
explanation, not just a label.

**Real-time coordination.** The backend connects both layers through an event-driven API and
pushes live state to the dashboard over WebSockets, so hub operators and the Cần Thơ
consolidation team see the same picture at the same time, with no manual polling or reporting
lag.

**Dashboard.** Two purpose-built views: a provincial hub view for logging shipments and
reviewing routing recommendations, and a Cần Thơ operations view showing consolidated
inventory by cargo type, live dispatch status, and weather conditions.

## Why This Approach

- **Decisions grounded in real cost and network data**, not static rules - freight rates,
  fuel prices, fleet capacity, and weather all feed directly into both AI layers from a shared
  dataset, so recommendations reflect actual operating conditions rather than fixed heuristics.
- **Two independent optimization problems, cleanly separated.** Routing and consolidation have
  different time horizons and different constraints; treating them as one monolithic decision
  would blur both. The event-driven handoff between layers keeps each optimizer simple,
  explainable, and independently improvable.
- **Explainable by design.** Every routing and dispatch decision returns structured reasoning
  (cost breakdown, constraint triggered, score components) - built for operators who need to
  trust and act on the system's output, not just observe it.
- **Consolidation that responds to conditions, not the clock.** The Cần Thơ dispatch agent
  weighs current fill level, the most time-sensitive cargo waiting, and current weather/route
  risk together, so a single perishable shipment can trigger an early dispatch while durable
  cargo is held to fill a vehicle more efficiently.

## Technology

- **Route & Cost Optimizer** - Python, FastAPI, pandas - a deterministic pricing and
  feasibility engine validated against a curated set of reference test cases.
- **Forecast & Dispatch Agent** - Python, FastAPI, scikit-learn - an event-driven service with
  a rolling multi-horizon load forecaster and a weighted priority-scoring decision engine.
- **Backend** - FastAPI (async), SQLModel/SQLite, WebSockets - orchestrates both AI layers and
  streams real-time state to clients.
- **Data platform** - a reproducible, seeded simulation package covering the transport network,
  fleet, weather, fuel and freight pricing, and grounding documents, used consistently across
  every layer so all components reason over the same source of truth.

