# LLM Cost Tracker

Dashboard monitoring biaya dan latency panggilan API LLM lintas provider.

> Status: **Blueprint** — belum ada kode.

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

| # | Milestone |
|---|---|
| M0 | Proxy sederhana, log ke console |
| M1 | Simpan ke Postgres + pricing table 3 provider |
| M2 | Dashboard basic (chart biaya harian) |
| M3 | Alert threshold + latency percentile |
| M4 | Multi-tenant (kalau mau dikembangkan jadi tool yang dijual) |

## Catatan

Jangan simpan isi prompt/response penuh kalau sensitif — cukup metadata (token count,
model, biaya, latency) demi privasi data pengguna.
