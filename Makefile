install:
	pip install -r requirements.txt

test:
	pytest -q

position:
	python -m position_service.app --host 127.0.0.1 --port 8000

orders:
	python -m order_service.app --input ./order_updates.csv --position-url http://127.0.0.1:8000/events --rate-limit 50
