# LLM Cost Tracker

Dashboard monitoring biaya dan latency panggilan API LLM lintas provider.

> Status: **M3 selesai** — budget alert dan percentile latency tersedia.

## Ringkasan

Middleware/proxy ringan yang mencatat setiap panggilan ke OpenAI/Anthropic/Groq/Gemini —
token in/out, biaya estimasi, latency — lalu divisualisasikan di dashboard supaya tim bisa
lihat provider dan endpoint mana yang paling mahal atau paling lambat.

## Fitur utama

- **Proxy layer**: wrap semua panggilan LLM lewat satu gateway, transparan ke aplikasi
- **Cost calculation**: pricing table per model/provider, mudah di-update
- **Dashboard**: breakdown biaya per endpoint/fitur/user, tren harian
- **Alerting**: notifikasi kalau budget harian/bulanan lewat threshold
- **Latency tracking**: p50/p95/p99 per provider, bantu keputusan routing model
- **Export**: laporan CSV/JSON untuk billing internal

## Arsitektur

```
App → LLM Proxy (log request + cost) → LLM Provider
  → response dicatat → Dashboard baca dari DB
```

## Stack (free-tier)

| Layer | Komponen |
|---|---|
| Proxy | FastAPI |
| Storage time-series | Postgres / Timescale |
| Dashboard | Next.js atau Streamlit |
| Hosting | Render / Railway free tier |

## Roadmap

| # | Milestone | Status |
|---|---|---|
| M0 | Proxy sederhana, log ke console | ✅ Selesai |
| M1 | Simpan ke Postgres + pricing table 3 provider | ✅ Selesai |
| M2 | Dashboard basic (chart biaya harian) | ✅ Selesai |
| M3 | Alert threshold + latency percentile | ✅ Selesai |
| M4 | Multi-tenant (kalau mau dikembangkan jadi tool yang dijual) | Belum dimulai |

## Menjalankan M3

Persyaratan: Python 3.9 atau lebih baru.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Isi `LLM_API_KEY` dan `DATABASE_URL` di `.env`. Postgres lokal dapat dijalankan dengan:

```bash
docker compose up -d postgres
```

Muat konfigurasi, jalankan migrasi, lalu mulai server:

```bash
set -a
source .env
set +a
python -m llm_cost_tracker.migrate
uvicorn llm_cost_tracker.main:app --reload
```

Di terminal lain dengan environment yang sama, jalankan dashboard:

```bash
streamlit run src/llm_cost_tracker/dashboard.py
```

Dashboard tersedia secara default di `http://localhost:8501`. Tampilan menyediakan
filter rentang tanggal dan provider, ringkasan biaya/request/token/cakupan harga, chart
biaya harian, p50/p95/p99 latency, serta tabel agregat. Query dashboard hanya membaca
metadata dari `llm_usage`; isi prompt dan response tidak digunakan.

### Budget alert

Threshold bersifat opsional dan dikonfigurasi dalam USD melalui `.env`:

```bash
DAILY_BUDGET_USD=10.00
MONTHLY_BUDGET_USD=200.00
# ALERT_WEBHOOK_URL=https://example.com/hooks/llm-budget
```

Tanpa `ALERT_WEBHOOK_URL`, alert ditulis sebagai JSON ke console. Jika URL diisi, proxy
mengirim `POST` JSON berisi jenis periode, awal periode, threshold, dan biaya aktual.
Alert tidak membawa prompt/response dan hanya dikirim sekali untuk kombinasi periode dan
nilai threshold. Jalankan ulang `python -m llm_cost_tracker.migrate` setelah mengambil
versi M3 untuk membuat tabel deduplikasi `budget_alerts`.

Secara default proxy meneruskan request ke OpenAI. `LLM_PROVIDER` juga mendukung `groq`
dan `gemini` melalui endpoint OpenAI-compatible. Untuk provider lain, isi
`LLM_BASE_URL` secara eksplisit.

Contoh request:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-5-mini","messages":[{"role":"user","content":"Halo"}]}'
```

Setiap request menghasilkan satu baris JSON di console dan satu record `llm_usage` di
Postgres. Data hanya memuat request ID, provider, model, status HTTP, latency, token
input/output/total, serta estimasi biaya USD. Isi prompt dan response tidak dicatat.
Streaming belum didukung.

Harga model dikelola dari satu sumber di
`src/llm_cost_tracker/data/pricing.json`. Migrasi menyinkronkan harga tersebut ke tabel
`model_pricing` dengan mekanisme upsert. Harga awal diverifikasi pada 25 Agustus 2026
dari halaman resmi provider dan mencakup:

| Provider | Model |
|---|---|
| OpenAI | `gpt-5-mini` |
| Groq | `openai/gpt-oss-120b` |
| Gemini | `gemini-2.5-flash` |

Jika model belum terdaftar, request tetap disimpan tetapi `estimated_cost_usd` bernilai
`null`. Untuk memperbarui harga, edit satu berkas JSON tersebut dan jalankan ulang
migrasi. Bila `DATABASE_URL` tidak diisi, aplikasi tetap berjalan dengan console logging
sebagai fallback.

Untuk membatasi akses ke proxy, isi `PROXY_API_KEY` lalu kirim
`Authorization: Bearer <PROXY_API_KEY>` dari aplikasi pemanggil.

Jalankan tes dengan:

```bash
pytest
```

## Catatan

Jangan simpan isi prompt/response penuh kalau sensitif — cukup metadata (token count,
model, biaya, latency) demi privasi data pengguna.
