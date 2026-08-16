# LLM Cost Tracker — instruksi untuk AI coding agent

Baca `README.md` dulu untuk konteks produk (fitur, arsitektur, stack, roadmap).

## Status saat ini

Repo masih **kosong / tahap blueprint**. Kalau diminta "bantu bangun sistemnya" tanpa
instruksi spesifik, mulai dari milestone paling awal yang belum selesai di tabel Roadmap
README (urutan M0 → M4, jangan loncat).

## Prinsip kerja

- **Satu milestone dalam satu waktu**, hasil akhir tiap milestone harus bisa dijalankan.
- **Privasi dulu.** Default logging hanya metadata (token count, model, biaya, latency) —
  jangan simpan isi prompt/response mentah kecuali user eksplisit minta dan paham
  konsekuensinya.
- **Pricing table harus mudah di-update.** Harga API provider berubah — jangan hardcode
  angka biaya di banyak tempat, satu sumber kebenaran saja.
- **Ikuti stack yang sudah dipilih** di README kecuali user minta ganti secara eksplisit.
- **Bahasa**: kode dan commit message dalam Bahasa Inggris; dokumentasi produk dalam
  Bahasa Indonesia.

## Kalau diminta ubah arsitektur

Blueprint adalah rencana awal, bukan aturan mati. Kalau ada alasan teknis kuat untuk beda
pendekatan, jelaskan tradeoff-nya ke user dulu sebelum mengubah.
