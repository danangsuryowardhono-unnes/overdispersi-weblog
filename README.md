# overdispersi-weblog

Kode analisis untuk naskah JUSTINDO:
**"Overdispersi Kedatangan Request pada Server Web Sektor Publik"**
(*Overdispersion of Request Arrivals on Public Sector Web Servers*).

Penulis: Danang Suryo Wardhono dan Alamsyah, Program Studi Magister Informatika, Fakultas Matematika dan Ilmu Pengetahuan Alam, Universitas Negeri Semarang.

DOI arsip (Zenodo): **[isi setelah rilis v1.0, format 10.5281/zenodo.xxxxxxx]**
Versi yang diacu naskah: **v1.0**

## Data

Log mentah tidak disertakan di repositori ini. Unduh dari sumber aslinya:

- **Web Server Log Dataset v1** (Organisasi X dan Y, 2025), Zenodo, lisensi MIT: https://doi.org/10.5281/zenodo.20001206
  Ekstrak `organization-x.zip` dan `organization-y.zip`, lalu letakkan `organization-x.yaml` dan `organization-y.yaml` di folder yang sama.
- **NASA-HTTP, Juli 1995**, Internet Traffic Archive: https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html (berkas `NASA_access_log_Jul95.gz`).
  SHA-256 berkas yang dipakai: `199109ed0f273e095da6ccd5fc9dc4cd8bb58daa06d62135e62090fea9d27488`.
  Baris utuh terakhir bertimestamp `28/Jul/1995:13:32:25 -0400`; baris paling akhir berkas terpotong dan termasuk 5 baris yang gagal di-*parse*.
- Tanggal data diunduh: **[isi tanggal pengunduhan]**.

## Isi repositori

| Berkas | Fungsi |
|---|---|
| `revisi_overdispersi.py` | Parsing log, pelabelan dengan YAML rules, dan analisis utama: dispersi, uji chi-square (`tabel3_chisquare.csv`), model cacah, autokorelasi, uji bebas jitter, non-stasioneritas, alarm palsu, dan sensitivitas pelabelan |
| `config_revisi.yaml` | Konfigurasi path, zona waktu, dan parameter analisis. Nilai baku `min_attack_req_per_min: 10` dipakai untuk hasil di naskah |
| `sweep_ambang.py` | Menjalankan ulang analisis untuk `min_attack_req_per_min` = 1, 5, 20, 50 dan menggabungkan hasilnya ke `sensitivitas_ambang.csv` (Tabel B3) |
| `kappa_label.py` | Menghitung kesepakatan dua kali pelabelan sampel audit (Cohen's kappa) |
| `ekspor_csv_revisi.py` | Mengekspor deret per menit (`orgX.csv`, `orgY.csv`, `nasa.csv`), sampel audit label, dan Tabel A1 |
| `analisis_tambahan_revisi.py` | IK block bootstrap, uji per jam dan per strata, NB + lag, INGARCH(1,1)-NB, diagnostik residual, rolling-origin, dan metrik monitoring |
| `hasil_revisi/`, `hasil_X.zip`, `hasil_Y.zip`, `hasil_NASA/` | Keluaran yang dipakai pada tabel naskah dan lampiran |

## Lingkungan dan reproduktibilitas

- Python 3.13. Paket dan versi minimum ada di `requirements.txt`; versi persis yang dipakai untuk naskah ada di `requirements-lock.txt` (hasil `pip freeze`).
- Seed acak: `RNG_SEED = 2026` (didefinisikan di `revisi_overdispersi.py`) untuk block bootstrap, jitter, dan pencuplikan.
- Zona waktu: Organisasi X dan Y mengikuti `config_revisi.yaml`; log NASA dibaca dengan zona waktu bawaan log (UTC−4).

```
pip install -r requirements.txt
```

## Cara membangun ulang semua tabel dan gambar

Jalankan dari folder tempat log dan berkas YAML berada, satu perintah per baris, berurutan:

```
# 1. Parsing + pelabelan + analisis utama (Tabel 1-11, tabel3_chisquare.csv, acf_*.png, changepoint_Y.png)
python revisi_overdispersi.py --config config_revisi.yaml --out hasil_revisi

# 2. Sensitivitas ambang menit serangan (Tabel B3); jalankan SESUDAH langkah 1, jangan bersamaan
python sweep_ambang.py

# 3. Ekspor deret per menit, sampel audit, dan Tabel A1
python ekspor_csv_revisi.py --config config_revisi.yaml --lengkap

# 4. Analisis tambahan (Tabel 8, 10, 12, Lampiran B)
python analisis_tambahan_revisi.py --input orgX.csv --name "Org X" --outdir hasil_X
python analisis_tambahan_revisi.py --input orgY.csv --name "Org Y" --outdir hasil_Y
python analisis_tambahan_revisi.py --input nasa.csv --name "NASA" --outdir hasil_NASA

# 5. Kesepakatan pelabelan ulang audit (setelah pelabelan kedua selesai)
python kappa_label.py audit_sampel_X_lama.csv audit_sampel_X_baru.csv
python kappa_label.py audit_sampel_Y_lama.csv audit_sampel_Y_baru.csv
```

`sweep_ambang.py` mengubah `config_revisi.yaml` sementara. Pastikan `min_attack_req_per_min` kembali ke `10` sebelum menjalankan ulang langkah 1.
Langkah 1 menyimpan hasil parsing ke `hasil_revisi/cache_*.pkl` sehingga run berikutnya jauh lebih cepat; berkas cache tidak diunggah karena ukurannya besar.

## Pemeriksaan hasil

Jumlah request benign harus sama dengan naskah: Organisasi X 201.692; Organisasi Y 2.245.963; NASA 1.891.712 (semua request, 39.693 menit).
Chi-square 1 menit (`tabel3_chisquare.csv`): X χ² = 1.987.697 (df 21); Y χ² = 32.592.990 (df 62); NASA χ² = 18.075.549 (df 48).

## Keterbatasan

- Label serangan berbasis aturan YAML dan bukan *ground truth*.
- Audit manual dilakukan oleh satu penilai (penulis pertama) dengan usulan label awal yang dibantu alat AI. Kesepakatan pelabelan ulang (Cohen's kappa) belum dihitung pada rilis ini, sehingga keandalan label audit belum terukur dan hasil audit dibaca sebagai indikasi arah kesalahan aturan.
- Evaluasi *detection rate* Organisasi X bertumpu pada 15 menit serangan (ambang 10 request); lihat Tabel B3 untuk definisi lain.

## Lisensi

Kode dirilis dengan lisensi MIT.
