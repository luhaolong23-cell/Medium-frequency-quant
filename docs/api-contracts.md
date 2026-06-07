# API Contracts

This document separates:

- `currently implemented interfaces`
- `planned interfaces`

Planned interfaces describe future module direction only. They are not available in the current codebase unless explicitly stated otherwise.

## Currently implemented interfaces

### API Gateway

### `GET /health`
Returns public health information for the gateway and current framework state.

### `GET /markets/today`
Returns public market-regime views for the current date.

### `POST /admin/run-daily`
Triggers the shared `DailyRunOrchestrator` and returns a `JobRunResult` envelope.

## Internal service contracts

### Refdata service
- `POST /v1/refdata/sync/markets`
- `GET /v1/refdata/markets`

### Market data service
- `POST /v1/market-data/ingest/daily`
- `GET /v1/market-data/features/{market_code}`

### Regime service
- `POST /v1/regime/run/daily`
- `GET /v1/regime/markets/today`
- `GET /v1/regime/markets/{market_code}/explain`

The current implementation is still limited to the market layer:

- market reference data
- market features
- market regime
- daily orchestration

## Planned interfaces

The following interfaces represent future modules and should not be treated as implemented contracts yet.

### Watchlist

- `GET /watchlist`
- `POST /watchlist/rebuild`

Intended direction:

- rebuild the watchlist from quality candidates in bull markets
- expose current watchlist members and candidate states

### Signals

- `POST /signals/run-daily`
- `GET /signals/{ticker}`

Intended direction:

- run daily technical signal scans for watchlist names
- explain whether a ticker has an active buy or sell trigger

### Orders

- `POST /orders`

Intended direction:

- submit execution instructions after a signal is approved
- later extend to cancellation and fill-tracking contracts

### Positions

- `GET /positions`

Intended direction:

- query live or latest known positions after execution starts

### Monitoring

- `GET /monitoring/alerts`

Intended direction:

- expose order, position, risk, and abnormal-event alerts

Field-level request and response schemas for these planned interfaces are intentionally deferred until the corresponding modules are implemented.

## Response envelope

Success:

```json
{
  "status": "success",
  "data": {}
}
```

Error:

```json
{
  "status": "error",
  "error": {
    "code": "...",
    "message": "..."
  }
}
```
