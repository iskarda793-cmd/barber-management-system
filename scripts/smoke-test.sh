#!/usr/bin/env bash
# Smoke test for the Barber Management System. Usage: ./scripts/smoke-test.sh [base_url]
set -u
BASE="${1:-http://localhost:5000}"
pass=0; fail=0
check() { # name expected actual
  if [ "$2" = "$3" ]; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1 (expected $2, got $3)"; fail=$((fail+1)); fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
J='Content-Type: application/json'

check "GET /health"                200 "$(code "$BASE/health")"
check "/health body"               '{"db":"connected","status":"ok"}' "$(curl -s "$BASE/health")"
for p in / /appointments /barbers /services; do check "GET page $p" 200 "$(code "$BASE$p")"; done

# --- REST API CRUD on barbers ---
B=$(curl -s -X POST -H "$J" -d '{"name":"Test Barber","phone":"123","specialty":"Tests"}' "$BASE/api/barbers")
BID=$(echo "$B" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
check "API create barber"          "Test Barber" "$(echo "$B" | python3 -c 'import sys,json;print(json.load(sys.stdin)["name"])')"
check "API read barber"            200 "$(code "$BASE/api/barbers/$BID")"
check "API update barber"          "Updated" "$(curl -s -X PUT -H "$J" -d '{"specialty":"Updated"}' "$BASE/api/barbers/$BID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["specialty"])')"
check "API validation (no name)"   400 "$(code -X POST -H "$J" -d '{"phone":"1"}' "$BASE/api/barbers")"
check "API bad price"              400 "$(code -X POST -H "$J" -d '{"name":"x","duration_minutes":10,"price":-5}' "$BASE/api/services")"

# --- appointment referencing the barber ---
A=$(curl -s -X POST -H "$J" -d "{\"customer_name\":\"Smoke\",\"barber_id\":$BID,\"service_id\":1,\"appointment_time\":\"2030-01-01T10:00\"}" "$BASE/api/appointments")
AID=$(echo "$A" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
check "API create appointment"     scheduled "$(echo "$A" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"
check "API bad FK"                 409 "$(code -X POST -H "$J" -d '{"customer_name":"x","barber_id":99999,"service_id":1,"appointment_time":"2030-01-01T10:00"}' "$BASE/api/appointments")"
check "API delete barber in use"   409 "$(code -X DELETE "$BASE/api/barbers/$BID")"
check "API bad status"             400 "$(code -X PUT -H "$J" -d '{"status":"weird"}' "$BASE/api/appointments/$AID")"
check "API complete appointment"   completed "$(curl -s -X PUT -H "$J" -d '{"status":"completed"}' "$BASE/api/appointments/$AID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"

# --- HTML form flow (create / edit / delete) ---
check "Form create service"        302 "$(code -X POST -d 'name=Form Service&duration_minutes=15&price=25' "$BASE/services")"
SID=$(curl -s "$BASE/api/services" | python3 -c 'import sys,json;print([s["id"] for s in json.load(sys.stdin) if s["name"]=="Form Service"][0])')
check "Form edit page"             200 "$(code "$BASE/services/$SID/edit")"
check "Form update service"        302 "$(code -X POST -d 'name=Form Service 2&duration_minutes=20&price=30' "$BASE/services/$SID")"
check "Form updated value"         "Form Service 2" "$(curl -s "$BASE/api/services/$SID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["name"])')"
check "Form validation redirect"   "error=" "$(curl -s -o /dev/null -w '%{redirect_url}' -X POST -d 'name=&duration_minutes=0&price=1' "$BASE/services" | grep -o 'error=')"
check "Form delete service"        302 "$(code -X POST "$BASE/services/$SID/delete")"

# --- cleanup ---
check "API delete appointment"     204 "$(code -X DELETE "$BASE/api/appointments/$AID")"
check "API delete barber"          204 "$(code -X DELETE "$BASE/api/barbers/$BID")"
check "API 404 after delete"       404 "$(code "$BASE/api/barbers/$BID")"
check "Unknown resource"           404 "$(code "$BASE/api/unknown")"

echo "----"; echo "$pass passed, $fail failed"; [ "$fail" -eq 0 ]
