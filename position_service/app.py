import argparse
import logging
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator


LOGGER = logging.getLogger("position_service")

app = FastAPI(title="Position Maintaining Service")


class OrderEvent(BaseModel):
    event_id: str
    symbol: str
    transaction_type: str
    quantity: int = Field(gt=0)

    @field_validator("event_id", "symbol")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        return value

    @field_validator("transaction_type")
    @classmethod
    def valid_transaction_type(cls, value: str) -> str:
        if value not in {"BUY", "SELL"}:
            raise ValueError("transaction_type must be exactly BUY or SELL")
        return value

    @field_validator("quantity", mode="before")
    @classmethod
    def positive_integer(cls, value):
        if isinstance(value, bool):
            raise ValueError("quantity must be a positive integer")
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("quantity must be a positive integer")
            return value
        raise ValueError("quantity must be a positive integer")


class PositionStore:
    def __init__(self):
        self._positions: dict[str, int] = {}
        self._accepted_event_ids: set[str] = set()
        self._lock = threading.RLock()

    def apply(self, event: OrderEvent) -> bool:
        with self._lock:
            if event.event_id in self._accepted_event_ids:
                return False

            self._accepted_event_ids.add(event.event_id)
            current = self._positions.get(event.symbol, 0)
            delta = event.quantity if event.transaction_type == "BUY" else -event.quantity
            self._positions[event.symbol] = current + delta
            return True

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._positions)


store = PositionStore()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events")
def receive_event(event: OrderEvent):
    try:
        accepted = store.apply(event)
    except Exception as exc:
        LOGGER.exception("Unexpected processing failure: %s", exc)
        raise HTTPException(status_code=500, detail="internal processing error")

    if not accepted:
        LOGGER.info("Ignored duplicate event_id=%s", event.event_id)
        return {"status": "duplicate", "event_id": event.event_id}

    LOGGER.info(
        "Accepted event_id=%s symbol=%s type=%s quantity=%d",
        event.event_id,
        event.symbol,
        event.transaction_type,
        event.quantity,
    )
    return {"status": "accepted", "event_id": event.event_id}


@app.get("/position")
def get_position():
    return store.snapshot()


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Position Maintaining Service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
