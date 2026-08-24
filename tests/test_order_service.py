import csv

from order_service.app import validate_row, stream_valid_events


def test_buy_and_sell_validation():
    buy = validate_row({
        "event_id": "evt-1",
        "symbol": "TCS",
        "transaction_type": "BUY",
        "quantity": "100",
    })
    sell = validate_row({
        "event_id": "evt-2",
        "symbol": "TCS",
        "transaction_type": "SELL",
        "quantity": "40",
    })
    assert buy.quantity == 100
    assert sell.transaction_type == "SELL"


def test_invalid_transaction_type():
    try:
        validate_row({
            "event_id": "evt-1",
            "symbol": "TCS",
            "transaction_type": "buy",
            "quantity": "10",
        })
        assert False
    except ValueError:
        assert True


def test_invalid_quantities():
    base = {
        "event_id": "evt-1",
        "symbol": "TCS",
        "transaction_type": "BUY",
    }

    for quantity in ["0", "-1", "1.5", "", "abc"]:
        row = dict(base, quantity=quantity)
        try:
            validate_row(row)
            assert False, quantity
        except ValueError:
            pass


def test_blank_event_id_and_symbol():
    for field in ["event_id", "symbol"]:
        row = {
            "event_id": "evt-1",
            "symbol": "TCS",
            "transaction_type": "BUY",
            "quantity": "1",
        }
        row[field] = " "
        try:
            validate_row(row)
            assert False, field
        except ValueError:
            pass


def test_duplicate_event_id_first_valid_wins(tmp_path):
    path = tmp_path / "orders.csv"
    rows = [
        ["evt-1", "ABC", "BUY", "10"],
        ["evt-1", "XYZ", "SELL", "999"],
        ["evt-2", "TCS", "SELL", "5"],
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "symbol", "transaction_type", "quantity"])
        writer.writerows(rows)

    events = list(stream_valid_events(str(path)))
    assert [(e.event_id, e.symbol, e.quantity) for e in events] == [
        ("evt-1", "ABC", 10),
        ("evt-2", "TCS", 5),
    ]


def test_invalid_row_does_not_stop_later_rows(tmp_path):
    path = tmp_path / "orders.csv"
    rows = [
        ["evt-1", "ABC", "BUY", "0"],
        ["evt-2", "TCS", "BUY", "5"],
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "symbol", "transaction_type", "quantity"])
        writer.writerows(rows)

    events = list(stream_valid_events(str(path)))
    assert [e.event_id for e in events] == ["evt-2"]
