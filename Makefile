run_local_server:
	poetry run python src\app.py host --lhost 0.0.0.0:8765

run_local_client:
	poetry run python src\app.py conn --lhost 0.0.0.0:8766 --rhost 127.0.0.1:8765

run_test:
	poetry run test.py