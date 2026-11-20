#!/usr/bin/env bash
# Проверка развернутой системы (используется в CI/CD после docker compose up)
source "$(dirname "$0")/common.sh"
fail() { log "FAIL: $*"; docker compose logs --tail=50 app; exit 1; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
post() { printf '%s' "$2" | curl -s -X POST "$APP_URL$1" -H 'Content-Type: application/json' --data-binary @-; }
id_of() { sed -n 's/.*"id":[[:space:]]*\([0-9]*\).*/\1/p'; }
[[ $(code "$APP_URL/health") == 200 ]] || fail "health"
SID=$(post /api/students '{"full_name":"Smoke Test","email":"smoke@ci.test","group_name":"CI"}' | id_of)
[[ -n "$SID" ]] || fail "создание студента"
DID=$(post /api/disciplines '{"title":"Smoke Discipline","credits":4}' | id_of)
[[ -n "$DID" ]] || fail "создание дисциплины"
post /api/grades "{\"student_id\":$SID,\"discipline_id\":$DID,\"score\":91}" | grep -q '"letter":"A-"' || fail "оценка"
curl -s "$APP_URL/api/students/$SID/transcript" | grep -q '"gpa":3.67' || fail "расчёт GPA"
curl -s "$APP_URL/metrics" | grep -q "grades_db_up 1" || fail "метрики"
[[ $(code -X DELETE "$APP_URL/api/students/$SID") == 204 ]] || fail "удаление"
log "Smoke-тест пройден"
