#!/usr/bin/env bash
# Заполнение системы тестовыми (вымышленными) данными через API
source "$(dirname "$0")/common.sh"
# Тело запроса передаётся через stdin: на Windows (Git Bash) кириллица в аргументах искажается
post() { printf '%s' "$2" | curl -s -X POST "$APP_URL$1" -H 'Content-Type: application/json; charset=utf-8' --data-binary @-; echo; }
id_of() { sed -n 's/.*"id":[[:space:]]*\([0-9]*\).*/\1/p'; }
D1=$(post /api/disciplines '{"title":"Прикладные аспекты DevOps","credits":5}' | id_of)
D2=$(post /api/disciplines '{"title":"Базы данных","credits":4}' | id_of)
D3=$(post /api/disciplines '{"title":"Компьютерные сети","credits":3}' | id_of)
S1=$(post /api/students '{"full_name":"Сейтова Дана","email":"dana@example.com","group_name":"CSE-22"}' | id_of)
S2=$(post /api/students '{"full_name":"Нурланов Ерлан","email":"erlan@example.com","group_name":"CSE-22"}' | id_of)
S3=$(post /api/students '{"full_name":"Ким Алина","email":"alina@example.com","group_name":"CSE-22"}' | id_of)
g() { post /api/grades "{\"student_id\":$1,\"discipline_id\":$2,\"score\":$3}" >/dev/null; }
g "$S1" "$D1" 96; g "$S1" "$D2" 91; g "$S1" "$D3" 88
g "$S2" "$D1" 74; g "$S2" "$D2" 68; g "$S2" "$D3" 81
g "$S3" "$D1" 85; g "$S3" "$D2" 47; g "$S3" "$D3" 79
log "Тестовые данные загружены"; curl -s "$APP_URL/api/stats"; echo
echo "--- Рейтинг группы CSE-22 ---"; curl -s "$APP_URL/api/groups/CSE-22/ranking"; echo
