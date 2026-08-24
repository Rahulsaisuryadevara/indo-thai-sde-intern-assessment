from fastapi.testclient import TestClient

from position_service.app import app, store, PositionStore, OrderEvent


client = TestClient(app)


def setup_function():
    # Reset global in-memory state between tests.
    store._positions.clear()
    store._accepted_event_ids.clear()


def post(event_id, symbol, transaction_type, quantity):
    return client.post(
        "/events",
        json={
            "event_id": event_id,
            "symbol": symbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
        },
    )


def test_buy_sell_and_multiple_symbols():
    assert post("1", "ABC", "BUY", 100).status_code == 200
    assert post("2", "ABC", "SELL", 25).status_code == 200
    assert post("3", "XYZ", "SELL", 50).status_code == 200
    assert post("4", "XYZ", "BUY", 50).status_code == 200

    assert client.get("/position").json() == {
        "ABC": 75,
        "XYZ": 0,
    }


def test_duplicate_event_id_is_ignored():
    assert post("same", "ABC", "BUY", 10).json()["status"] == "accepted"
    assert post("same", "ABC", "SELL", 10).json()["status"] == "duplicate"
    assert client.get("/position").json() == {"ABC": 10}


def test_invalid_events_return_422():
    invalid = [
        {"event_id": "", "symbol": "ABC", "transaction_type": "BUY", "quantity": 1},
        {"event_id": "1", "symbol": "", "transaction_type": "BUY", "quantity": 1},
        {"event_id": "2", "symbol": "ABC", "transaction_type": "HOLD", "quantity": 1},
        {"event_id": "3", "symbol": "ABC", "transaction_type": "BUY", "quantity": 0},
        {"event_id": "4", "symbol": "ABC", "transaction_type": "BUY", "quantity": -1},
        {"event_id": "5", "symbol": "ABC", "transaction_type": "BUY", "quantity": "1.5"},
        {"event_id": "6", "symbol": "ABC", "transaction_type": "BUY", "quantity": ""},
    ]

    for event in invalid:
        assert client.post("/events", json=event).status_code == 422


def test_get_position():
    post("a", "RELIANCE", "BUY", 90)
    post("b", "TCS", "SELL", 75)

    response = client.get("/position")
    assert response.status_code == 200
    assert response.json() == {"RELIANCE": 90, "TCS": -75}


def test_position_store_duplicate_directly():
    s = PositionStore()
    event = OrderEvent(
        event_id="x",
        symbol="ABC",
        transaction_type="BUY",
        quantity=10,
    )
    assert s.apply(event) is True
    assert s.apply(event) is False
    assert s.snapshot() == {"ABC": 10}
