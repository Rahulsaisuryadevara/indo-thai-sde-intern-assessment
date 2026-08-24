import csv
import threading
import time

import requests
import uvicorn

from order_service.app import EventSender, process_file
from position_service.app import app, store


def test_end_to_end(tmp_path):
    # Use a free local port chosen by uvicorn's socket binding.
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    store._positions.clear()
    store._accepted_event_ids.clear()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            if requests.get(f"{base}/health", timeout=0.2).ok:
                break
        except requests.RequestException:
            time.sleep(0.05)
    else:
        server.should_exit = True
        raise AssertionError("service did not start")

    csv_path = tmp_path / "orders.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "symbol", "transaction_type", "quantity"])
        writer.writerow(["e1", "ABC", "BUY", "100"])
        writer.writerow(["e2", "ABC", "SELL", "30"])
        writer.writerow(["bad", "ABC", "BUY", "0"])
        writer.writerow(["e3", "XYZ", "SELL", "20"])

    process_file(
        str(csv_path),
        EventSender(f"{base}/events", rate_limit=1000),
    )

    assert requests.get(f"{base}/position").json() == {
        "ABC": 70,
        "XYZ": -20,
    }

    server.should_exit = True
    thread.join(timeout=3)
