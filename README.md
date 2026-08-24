# Indo Thai — SDE Intern Take-Home Assessment

A small two-service order processing system implemented in Python.

## Architecture

```text
order_updates.csv
      |
      v
+-----------------------+
| Order Update Service  |
| - streaming CSV read  |
| - validation           |
| - duplicate filtering  |
| - <= 50 events/sec     |
+-----------+-----------+
            | HTTP POST /events
            v
+-----------------------+
| Position Service      |
| - in-memory positions |
| - duplicate filtering |
| - thread-safe state   |
| - GET /position       |
+-----------------------+
```

### Why HTTP?

HTTP keeps the solution simple, observable, and independently runnable without external infrastructure. It is explicitly permitted by the assessment. The sender receives an HTTP status code and logs delivery failures.

### Event schema

```json
{
  "event_id": "evt-0001",
  "symbol": "RELIANCE",
  "transaction_type": "BUY",
  "quantity": 90
}
```

### Delivery limitations

Delivery is best-effort HTTP. There is no durable queue, retry persistence, exactly-once guarantee across restarts, or recovery after a complete process restart. The assessment explicitly excludes those requirements. The position service's accepted-event ID set is in memory and therefore resets on restart.

## Requirements

- Python 3.10+
- No database
- No external infrastructure required

## Setup

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the Position Maintaining Service

```bash
python -m position_service.app --host 127.0.0.1 --port 8000
```

The API remains available while events are processed.

## Run the Order Update Service

In another terminal:

```bash
python -m order_service.app --input ./order_updates.csv --position-url http://127.0.0.1:8000/events --rate-limit 50
```

The input path, service address, port, and rate limit are configurable.

## API

Get all current positions:

```bash
curl http://127.0.0.1:8000/position
```

Example:

```json
{
  "RELIANCE": 90,
  "TCS": -75
}
```

Symbols remain present even when their net position reaches zero.

## Tests

```bash
pytest -q
```

The test suite covers:

- BUY and SELL calculations
- Multiple symbols
- Negative and zero positions
- Duplicate event IDs
- Invalid transaction types
- Zero, negative, non-integer, and blank quantities
- Blank event IDs and symbols
- Continuing after invalid rows
- GET `/position`
- HTTP service behavior

## Configuration

Order Update Service:

| Option | Default | Meaning |
|---|---:|---|
| `--input` | required | CSV input file |
| `--position-url` | `http://127.0.0.1:8000/events` | Position service endpoint |
| `--rate-limit` | `50` | Maximum events per second |

Position Service:

| Option | Default |
|---|---|
| `--host` | `127.0.0.1` |
| `--port` | `8000` |

## Logging

The sender logs accepted, rejected, sent, and failed events and logs completion. The receiver logs accepted events, duplicates, malformed payloads, and processing errors.

## Design notes

- CSV rows are read one at a time using `csv.DictReader`; the complete file is never loaded into memory.
- The first valid event for an event ID wins at the sender.
- The receiver also protects itself from duplicate event IDs.
- Validation rejects blank IDs/symbols, transaction types other than exactly `BUY`/`SELL`, and quantities that are not positive integers.
- A lock protects position and event-ID state so concurrent HTTP requests and API reads remain correct.
- A zero position is retained because the symbol is inserted when its first accepted event is processed.

## AI-assisted tools

AI assistance was used during development. The submitted implementation and design should be reviewed and understood by the candidate before submission, consistent with the assessment instructions.
