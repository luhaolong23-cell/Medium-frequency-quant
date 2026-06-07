# Architecture Notes

## System boundary

This repository should be understood in two layers:

- `current implementation scope`
  the market-regime framework is implemented
- `target system scope`
  the repository is meant to grow into a full mid-frequency quantitative trading system

The target business chain is:

`market regime -> bull-market stock pool -> quality selection -> watchlist -> entry signals -> execution -> monitoring`

That means the repository is not "market regime only" in product direction. It is only "market regime first" in implementation progress.

## Current implementation scope

The code currently implements the market-layer skeleton:

- market reference data
- market observations and feature normalization
- market regime scoring and explanation
- daily orchestration through `DailyRunOrchestrator`
- in-memory repositories
- mock / in-memory provider implementations

Current services that are effectively implemented:

- `refdata_service`
- `market_data_service`
- `regime_service`

## Target system scope

The full target system boundary includes:

- `market regime`
- `universe / bull-market stock pool`
- `quality selection`
- `watchlist management`
- `entry signal engine`
- `execution`
- `position monitoring`
- `risk monitoring`

These future capabilities sit on top of the existing market layer rather than replacing it.

## Future reserved modules

The following modules are part of the intended architecture but are not implemented yet:

- `selection_service`
  Selects quality stocks inside bull markets.
- `watchlist_service`
  Manages the watchlist and candidate state transitions.
- `signal_service`
  Evaluates technical entry and exit conditions.
- `execution_service`
  Handles order placement, cancellation, fills, and broker callbacks.
- `monitoring_service`
  Monitors positions, risk, orders, and abnormal events.

These modules are architectural placeholders only. They are documented now to make the system boundary explicit, not to suggest that they are already available.

## Operating model

The intended operating model is:

- `daily decision layer`
  market regime, stock-pool refresh, quality selection, watchlist updates, signal scan, and trade-plan generation
- `intraday execution and monitoring layer`
  order execution, fill tracking, position monitoring, and risk monitoring

This is a mid-frequency design. "Continuous monitoring" here means intraday execution and risk supervision, not a high-frequency strategy.

## Design rules

- Services communicate through explicit application boundaries even while running in one process.
- Strategy rules live in domain code or versioned config.
- External vendors must be accessed through providers.
- Raw vendor payloads must not leak into business logic.
- Repositories stay behind infra boundaries even before a real database is attached.
- Public gateway routes are separate from internal service routes.
- Daily orchestration is centralized in `DailyRunOrchestrator`.

## Current implementation mode

The current framework uses:

- in-memory repositories
- a mock market-data provider
- a feature builder that normalizes provider observations into `MarketFeature`

This is intentional. The framework is meant to validate boundaries before real integrations are attached.

## Evolution path

1. Market regime
2. Bull-market stock pool
3. Quality selection and watchlist
4. Entry signal engine
5. Execution and order management
6. Position and risk monitoring
