#!/usr/bin/env bash
set -euo pipefail

if [ -z "${APP_PORT:-}" ] && [ -f .env ]; then
  APP_PORT="$(sed -n 's/^APP_PORT=//p' .env | head -1)"
fi
BASE_URL="${BASE_URL:-http://localhost:${APP_PORT:-8010}}"
STAMP="$(date +%s)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

total=0
lulus=0

check() {
  local label="$1"
  local expected="$2"
  local actual="$3"
  total=$((total + 1))
  if [ "$actual" = "$expected" ]; then
    lulus=$((lulus + 1))
    printf '  OK   %-38s HTTP %s\n' "$label" "$actual"
  else
    printf '  GAGAL %-37s HTTP %s (harus %s)\n' "$label" "$actual" "$expected"
  fi
}

echo "Smoke test Together di $BASE_URL"

code=$(curl -s -o "$TMP_DIR/health.json" -w '%{http_code}' "$BASE_URL/health")
check "GET /health" "200" "$code"

code=$(curl -s -o "$TMP_DIR/stats.json" -w '%{http_code}' "$BASE_URL/api/statistik")
check "GET /api/statistik" "200" "$code"

code=$(curl -s -o "$TMP_DIR/prediksi.json" -w '%{http_code}' \
  -X POST "$BASE_URL/api/prediksi" \
  -H 'Content-Type: application/json' \
  -d '{"wilayah":"Uji Otomatis","curah_hujan_mm":255,"tma_cm":400,"drainase_skor":1,"elevasi_m":5,"impervious_pct":90}')
check "POST /api/prediksi (Awas)" "201" "$code"

misi_id=$(python3 -c "import json,sys;d=json.load(open('$TMP_DIR/prediksi.json'));print((d.get('misi') or {}).get('id',''))")

code=$(curl -s -o "$TMP_DIR/misi.json" -w '%{http_code}' "$BASE_URL/api/misi")
check "GET /api/misi" "200" "$code"

if [ -n "$misi_id" ]; then
  code=$(curl -s -o "$TMP_DIR/gabung.json" -w '%{http_code}' \
    -X POST "$BASE_URL/api/misi/$misi_id/gabung" \
    -H 'Content-Type: application/json' \
    -d "{\"nama\":\"Relawan Uji\",\"kontak\":\"0812-UJI-$STAMP\",\"keahlian\":[\"Logistik\"]}")
  check "POST /api/misi/{id}/gabung" "201" "$code"

  code=$(curl -s -o "$TMP_DIR/duplikat.json" -w '%{http_code}' \
    -X POST "$BASE_URL/api/misi/$misi_id/gabung" \
    -H 'Content-Type: application/json' \
    -d "{\"nama\":\"Relawan Uji\",\"kontak\":\"0812-UJI-$STAMP\",\"keahlian\":[\"Logistik\"]}")
  check "POST gabung duplikat" "409" "$code"

  code=$(curl -s -o "$TMP_DIR/salah.json" -w '%{http_code}' \
    -X POST "$BASE_URL/api/misi/$misi_id/gabung" \
    -H 'Content-Type: application/json' \
    -d "{\"nama\":\"Relawan Salah\",\"kontak\":\"0812-SALAH-$STAMP\",\"keahlian\":[\"Astronot\"]}")
  check "POST gabung keahlian salah" "409" "$code"
else
  echo "  LEWAT  Misi tidak terbentuk; periksa model/ambang risiko."
fi

echo "Hasil: $lulus/$total cek lulus"
[ "$lulus" -eq "$total" ]
