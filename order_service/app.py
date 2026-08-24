import argparse
import csv
import logging
import time
from dataclasses import dataclass
from typing import Dict, Iterator

import requests


LOGGER = logging.getLogger("order_update_service")


@dataclass(frozen=True)
class OrderEvent:
    event_id: str
    symbol: str
    transaction_type: str
    quantity: int

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "symbol": self.symbol,
            "transaction_type": self.transaction_type,
            "quantity": self.quantity,
        }


def validate_row(row: Dict[str, str | None]) -> OrderEvent:
    event_id = (row.get("event_id") or "").strip()
    symbol = (row.get("symbol") or "").strip()
    transaction_type = (row.get("transaction_type") or "").strip()
    raw_quantity = row.get("quantity")

    if not event_id:
        raise ValueError("event_id must be a non-empty string")
    if not symbol:
        raise ValueError("symbol must be a non-empty string")
    if transaction_type not in {"BUY", "SELL"}:
        raise ValueError("transaction_type must be exactly BUY or SELL")
    if raw_quantity is None or not raw_quantity.strip():
        raise ValueError("quantity must be a positive integer")

    quantity_text = raw_quantity.strip()
    try:
        # int("1.0") and int("1e2") fail, which is intentional.
        quantity = int(quantity_text)
    except ValueError:
        raise ValueError("quantity must be a positive integer")

    if quantity <= 0:
        raise ValueError("quantity must be a positive integer")

    return OrderEvent(event_id, symbol, transaction_type, quantity)


def stream_valid_events(path: str) -> Iterator[OrderEvent]:
    seen_ids: set[str] = set()

    with open(path, "r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        expected = {"event_id", "symbol", "transaction_type", "quantity"}
        if reader.fieldnames is None or not expected.issubset(set(reader.fieldnames)):
            raise ValueError(
                "CSV must contain event_id,symbol,transaction_type,quantity columns"
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                event = validate_row(row)
            except ValueError as exc:
                LOGGER.warning("Rejected row %d: %s", line_number, exc)
                continue

            if event.event_id in seen_ids:
                LOGGER.info(
                    "Ignored duplicate event_id=%s at row %d",
                    event.event_id,
                    line_number,
                )
                continue

            seen_ids.add(event.event_id)
            LOGGER.info("Accepted event_id=%s", event.event_id)
            yield event


class EventSender:
    def __init__(
        self,
        position_url: str,
        rate_limit: float = 50.0,
        timeout: float = 5.0,
        session: requests.Session | None = None,
    ):
        if rate_limit <= 0:
            raise ValueError("rate_limit must be greater than zero")
        self.position_url = position_url
        self.interval = 1.0 / rate_limit
        self.timeout = timeout
        self.session = session or requests.Session()
        self._last_send = 0.0

    def send(self, event: OrderEvent) -> None:
        now = time.monotonic()
        wait = self.interval - (now - self._last_send)
        if wait > 0:
            time.sleep(wait)

        response = self.session.post(
            self.position_url,
            json=event.to_dict(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        self._last_send = time.monotonic()
        LOGGER.info("Successfully sent event_id=%s", event.event_id)

    def close(self) -> None:
        self.session.close()


def process_file(path: str, sender: EventSender) -> None:
    try:
        for event in stream_valid_events(path):
            try:
                sender.send(event)
            except requests.RequestException as exc:
                LOGGER.error(
                    "Failed to send event_id=%s: %s",
                    event.event_id,
                    exc,
                )
    finally:
        sender.close()

    LOGGER.info("Input processing complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Order Update Service")
    parser.add_argument("--input", required=True, help="Path to order_updates.csv")
    parser.add_argument(
        "--position-url",
        default="http://127.0.0.1:8000/events",
        help="Position service event endpoint",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=50.0,
        help="Maximum events per second",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    process_file(args.input, EventSender(args.position_url, args.rate_limit))


if __name__ == "__main__":
    main()
