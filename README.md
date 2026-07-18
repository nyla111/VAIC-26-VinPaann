# AI Layer 2 - Forecast & Dispatch Agent

`ai2_dispatch` is the Layer 2 service in the ĐBSCL agricultural logistics coordination system.
It receives shipments that have already been routed through the Cần Thơ transshipment hub by
Layer 1 (route & cost optimization), tracks accumulated load per outbound mode (road/water),
forecasts how load will accumulate over the next few hours, and returns a dispatch decision -
`dispatch_now`, `wait_for_load`, or `wait_for_vehicle` - together with a machine-readable
explanation.

The service combines two complementary behaviors:

- **Event-driven**: upstream systems push shipment, vehicle, and weather events; every read
  endpoint recomputes forecast and decision state from current data, so consumers can poll it
  safely at any time without side effects.
- **Autonomous**: a background loop independently re-evaluates the dispatch decision on a
  fixed interval, even with no new events and no incoming request - the classic agent cycle of
  observe → forecast → decide → (re-)observe. See [Autonomous agent loop](#autonomous-agent-loop).

## Status

This is a v1 implementation. It runs end-to-end against the project's real canonical dataset
(not a synthetic placeholder). Two components are backed by real data rather than hand-picked
defaults or pure rule logic:

- Priority-score weights are calibrated against a simulated replay of real historical order
  data (see [Decision logic](#decision-logic)).
- Load forecasting can use a trained regression model instead of a static rolling average (see
  [Predictive model](#predictive-model)).

See [Known limitations](#known-limitations) below for what is intentionally simplified in this
version.

## Architecture

```text
ai2_dispatch/
├── app/
│   ├── main.py             # FastAPI application, route wiring, agent lifespan startup
│   ├── schemas.py          # Pydantic request/response models
│   ├── enums.py            # Route, mode, decision, and reason-code enums
│   ├── data_loader.py      # Canonical dataset access (commodities, fleet, weather bulletins)
│   ├── state_store.py      # In-memory shipment/vehicle state, event idempotency
│   ├── forecasting.py      # Rolling-horizon load forecast (ML-backed, with fallback)
│   ├── ml_forecaster.py    # Loads the trained forecasting model, if present
│   ├── decision_engine.py  # Hard constraints + weighted priority scoring
│   └── agent.py            # Autonomous periodic re-evaluation loop
├── scripts/
│   ├── simulate_and_tune.py  # Replay-based grid search for priority-score weights
│   └── train_forecaster.py   # Trains the load-forecasting model on real historical data
├── models/
│   ├── arrival_forecaster.joblib   # Trained model artifact (produced by train_forecaster.py)
│   └── training_metrics.json       # Honest evaluation metrics from the last training run
├── reports/
│   └── tuning_report.json    # Output of the last tuning run (evidence, not just claims)
├── tests/
│   └── test_smoke.py       # End-to-end tests against the real dataset
├── examples/
│   ├── sample_events.json
│   └── sample_responses.json
└── requirements.txt
```

## Data sources

The service reads directly from the project's canonical dataset
(`data_package/data/generated/annual/csv/`) via the same loader used by the Layer 1 route
optimizer, so both layers always operate on a consistent snapshot of `commodities`, `fleet`,
`weather_bulletins`, and `nodes`.

- **Cargo profiles** (`time_sensitivity`, `max_safe_wait_hours`, refrigeration requirement,
  compatible vehicle types) are derived from `commodities.csv` rather than hard-coded.
- **Vehicles** are bootstrapped from `fleet.csv` (filtered to vehicles located at the Cần Thơ
  hub) and then updated in real time via `vehicle-status` events.
- **Weather risk and route closures** are read from `weather_bulletins.csv` for the Cần
  Thơ → Ho Chi Minh City corridor, with a manual override endpoint available for scenario
  testing.

## Route encoding

Layer 1 exposes five route options identified by internal codes (`A_DIRECT_ROAD` through
`E_ROAD_WATER_VIA_CT`). Layer 2 consumes a corresponding set of five snake_case route
identifiers that make the inbound/outbound transport mode explicit:

| Route | Hub → Cần Thơ | Cần Thơ → HCMC |
|---|---|---|
| `direct_hcm_road` | - (bypasses Cần Thơ) | road |
| `via_can_tho_road_then_road` | road | road |
| `via_can_tho_water_then_road` | water | road |
| `via_can_tho_water_then_water` | water | water |
| `via_can_tho_road_then_water` | road | water |

Only the four routes that pass through Cần Thơ are relevant to this service;
`direct_hcm_road` shipments are rejected with `ROUTE_NOT_APPLICABLE`. The `selected_route`
field accepts either the five snake_case identifiers above or Layer 1's internal route codes
(`A_DIRECT_ROAD`..`E_ROAD_WATER_VIA_CT`) interchangeably - the service normalizes on input, so
upstream callers do not need to perform this translation themselves. `inbound_mode_to_can_tho`
and `outbound_mode_from_can_tho` are optional: if omitted, they are derived from
`selected_route`; if provided, they must be consistent with it.

## API reference

### Events

All event endpoints are idempotent on `event_id`: resubmitting a previously seen event returns
`duplicate: true` without mutating state.

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/events/shipment-routed` | Register a shipment that has been routed through Cần Thơ |
| `POST /api/v1/events/shipment-arrived` | Mark a shipment as physically arrived at Cần Thơ |
| `POST /api/v1/events/shipment-cancelled` | Remove a shipment from the pending pool |
| `POST /api/v1/events/vehicle-status` | Update a vehicle's availability, capacity, or location |
| `POST /api/v1/events/weather-update` | Override the automatically-read weather assessment for scenario testing |
| `POST /api/v1/events/dispatch-completed` | Confirm that a dispatch (typically the one proposed via `dispatch_order_proposal`) has actually departed, removing those shipments from the pending pool |

Every event endpoint returns:

```json
{"accepted": true, "event_id": "evt_001", "state_version": 3, "recomputed": true, "duplicate": false}
```

Domain errors use a structured error envelope:

| Code | HTTP status | Condition |
|---|---:|---|
| `SHIPMENT_NOT_FOUND` | 404 | Referenced `shipment_id` has no prior `shipment-routed` event |
| `INVALID_STATE_TRANSITION` | 409 | Event implies an invalid shipment lifecycle transition |

Schema-level validation errors (e.g. route/mode mismatch) return the standard FastAPI/Pydantic
422 response.

### Forecast and dispatch status

```text
GET /api/v1/forecast?outbound_mode=road|water&decision_ts=<ISO8601>
GET /api/v1/dispatch-status?outbound_mode=road|water&decision_ts=<ISO8601>
```

`outbound_mode` is required conceptually (road and water are tracked as independent load
pools with independent vehicle pools); if omitted, the service selects whichever pool
currently holds more pending weight. `decision_ts` defaults to the current time and should be
passed explicitly by callers that need reproducible results.

`GET /api/v1/forecast` returns a rolling multi-bucket forecast (default: 30-minute buckets over
a 6-hour horizon) plus a `predicted_full_load_time` - the earliest time at which the selected
vehicle is expected to reach capacity, rather than a single fixed-horizon number.

`GET /api/v1/dispatch-status` returns the current `decision`, structured `reason_codes`, a
human-readable `explanation`, the selected vehicle, a full priority-score breakdown, and - when
the decision is `dispatch_now` - a `dispatch_order_proposal` describing which shipments should
be loaded onto which vehicle. See `examples/sample_responses.json` for a real response captured
against the dataset.

## Decision logic

For a given `outbound_mode`, the service evaluates conditions in a fixed order. Hard
constraints take precedence over the priority score and cannot be overridden by it:

1. No shipments currently waiting → `wait_for_load`.
2. No compatible vehicle available (matching mode and refrigeration requirement) →
   `wait_for_vehicle`.
3. The outbound route is closed per the current weather bulletin → `wait_for_load`
   (`weather_blocked`).
4. Any waiting shipment has reached its maximum safe wait time → `dispatch_now`
   (`safe_wait_limit_reached`), regardless of current fill level.
5. The selected vehicle is at or above capacity → `dispatch_now` (`vehicle_full`).
6. Otherwise, a weighted priority score determines the outcome:

```text
priority_score = 0.60 × fill_component + 0.30 × urgency_component + 0.10 × weather_component
```

`fill_component` is the current load as a fraction of vehicle capacity. `urgency_component` is
the maximum, across all waiting shipments, of `elapsed_time / max_safe_wait_hours ×
time_sensitivity` - the most time-sensitive cargo in a mixed load drives the urgency of the
whole batch. `weather_component` reflects current flood/route risk. The score is additive by
design so that a single zero-valued component cannot suppress the others; if the score reaches
`0.65`, the service returns `dispatch_now`, otherwise `wait_for_load`.

### How the weights were chosen

The weights and threshold above are not hand-picked defaults - they were selected by
`scripts/simulate_and_tune.py`, a grid search that replays real historical orders (drawn from
the canonical dataset across three sample months) through the actual routing logic used by
Layer 1 and this service's own decision engine, including a modeled vehicle turnaround time
derived from real leg durations. Each candidate weight combination is scored against a proxy
objective (waiting time, underfill, and unresolved-shipment cost); the selected combination
reduced that proxy loss by roughly 25% relative to an unweighted default. The objective is a
documented approximation, not a real-cost model - see `reports/tuning_report.json` for the
full grid results and `scripts/simulate_and_tune.py` for the methodology and its stated
caveats before treating these numbers as final.

## Predictive model

The `predicted_unknown_kg` component of the forecast (load not yet known via any confirmed
shipment, i.e. arrivals the service hasn't been told about yet) is produced by a trained
regression model when one is available, rather than a single global average.

`scripts/train_forecaster.py` builds a bucketed (30-minute) time series of real Cần Thơ-bound
arrivals from the canonical order history - reusing the same real-data extraction used for
priority-score tuning - with features for hour of day, day of week, month, outbound mode, and
short-term lag/rolling statistics, and fits a gradient-boosted regression model against it. The
resulting artifact (`models/arrival_forecaster.joblib`) is loaded lazily by
`app/ml_forecaster.py` and consumed by `forecasting.py` on every forecast computation, using
lag features drawn from the service's own observed arrival history at request time.

If the artifact is missing, or `scikit-learn`/`joblib` are unavailable at runtime, the service
falls back to the rolling-mean baseline automatically - no request ever fails because of a
missing or broken model file. `GET /api/v1/forecast` reports which one produced a given result
via `config.model_name` (`gradient_boosting_arrival_forecaster_v1` or `rolling_mean_v1`).

The model currently offers a modest, not dramatic, improvement over the rolling-mean baseline
(see `models/training_metrics.json` for the exact figures) on a fairly small, sparse historical
sample. It should be read as a working predictive pipeline rather than a finished, tuned
forecaster - see [Known limitations](#known-limitations).

## Autonomous agent loop

Independently of any inbound request, `app/agent.py` runs a background loop (started at
process startup via FastAPI's lifespan hook) that periodically re-evaluates the dispatch
decision for every outbound mode with shipments currently waiting, and logs whenever a decision
changes. This is what makes the service an *agent* rather than a pure request/response API: a
shipment approaching its safe-wait limit will eventually trigger a `dispatch_now` decision on
its own, without any client needing to poll at the right moment. The tick interval is
configurable via `AI2_AGENT_TICK_SECONDS` (default 30s) and the loop can be disabled entirely
with `AI2_DISABLE_AGENT_TICK=1`, primarily for test environments.

## Installation and usage

**Requirements:** Python 3.10+. Dependencies are listed in `requirements.txt`
(FastAPI, Pydantic, pandas, NumPy, scikit-learn, joblib, pytest, httpx).

```bash
cd VAIC-26-VinPaann
python -m pip install -r ai2_dispatch/requirements.txt
```

Run the service:

```bash
python -m uvicorn ai2_dispatch.app.main:app --reload --host 127.0.0.1 --port 8001
```

Interactive API docs are available at `http://127.0.0.1:8001/docs`.

Run tests (executed against the real canonical dataset, no mocked data):

```bash
python -m pytest ai2_dispatch/tests/test_smoke.py -v
```

(Re-)train the forecasting model and (re-)run priority-score tuning (optional - a trained
model and tuning report are already committed; only needed if the underlying dataset or
methodology changes):

```bash
python -m ai2_dispatch.scripts.train_forecaster
python -m ai2_dispatch.scripts.simulate_and_tune
```

### Configuration

All configuration is via environment variables; none are required to run with sensible
defaults.

| Variable | Default | Purpose |
|---|---|---|
| `AI2_STATE_FILE` | `ai2_dispatch/.state/ai2_state.pkl` | Path to the local state snapshot file (see [Known limitations](#known-limitations)) |
| `AI2_AGENT_TICK_SECONDS` | `30` | Interval, in seconds, between autonomous re-evaluation ticks (see [Autonomous agent loop](#autonomous-agent-loop)) |
| `AI2_DISABLE_AGENT_TICK` | unset (loop enabled) | Set to `1` to disable the autonomous loop entirely, e.g. in test environments |

## Known limitations

- **State persistence is a local snapshot file, not a database.** The service writes its full
  in-memory state to a local file after every accepted event and reloads it on startup, so a
  process restart does not lose data. This is sufficient for single-instance demo/integration
  use but is not a substitute for a shared, multi-instance-safe store in production.
- **Unknown commodity codes do not fail the request.** If `commodity_id` does not match the
  canonical commodity list, the service falls back to a moderate, cargo-agnostic urgency
  profile rather than rejecting the shipment or silently excluding it from scoring - trading a
  small amount of decision accuracy for pipeline robustness.
- **The trained forecasting model is a directional check, not a tuned production model.** It
  was trained on a relatively small, sparse historical sample (see
  [Predictive model](#predictive-model)) and offers only a modest improvement over the
  rolling-mean baseline. Lag/rolling features used at inference time are held static across the
  whole forecast horizon rather than updated recursively bucket-by-bucket, which is a
  simplification, not a limitation of the underlying data.
- **The agent loop's lag/rolling features come from this service's own observed history**,
  which is empty on a fresh process start - early forecasts after a restart are less informed
  than ones made after the service has been running and observing arrivals for a while.
- **Priority score weights are tuned against a proxy objective, not a real cost model.**
  Simulation-based tuning (see [Decision logic](#decision-logic)) improves on hand-picked
  defaults but still optimizes a hand-defined approximation of waiting/underfill/unresolved
  cost, not actual transport or spoilage cost in VND - real cost data would change the result.
- **No forecasting model has been trained on this system's own event history yet.** The
  forecasting baseline (above) and the priority-score tuning both currently draw on the
  canonical historical dataset via replay, not on live production traffic; both should be
  revisited once real operational event logs accumulate.
- **Cargo urgency parameters** (`time_sensitivity`, `max_safe_wait_hours`) are derived from the
  dataset's `perishability_level` and `max_hold_hours` fields via a documented but unverified
  conversion; they should be reviewed against the original data-generation intent before being
  treated as authoritative.
- Concurrency is handled with a single process-wide lock, sufficient for demo-scale traffic but
  not load-tested.
- No authentication, rate limiting, or production logging is implemented.
