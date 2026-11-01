#!/usr/bin/env bash
set -euo pipefail
airflow db migrate
if ! airflow users list --output json | python -c 'import json,sys; sys.exit(0 if any(u["username"] == "lecturer" for u in json.load(sys.stdin)) else 1)'; then
  airflow users create --username lecturer --password lecturer --firstname CS611 --lastname Lecturer --role Admin --email lecturer@example.invalid
fi
echo "Airflow UI: http://localhost:18080  username=lecturer password=lecturer"
airflow scheduler &
scheduler_pid=$!
airflow webserver --port 8080 &
webserver_pid=$!
trap 'kill "$scheduler_pid" "$webserver_pid" 2>/dev/null || true; wait || true' TERM INT EXIT
wait -n "$scheduler_pid" "$webserver_pid"
