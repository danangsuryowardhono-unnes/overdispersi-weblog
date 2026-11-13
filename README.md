# overdispersi-weblog

Kode analisis untuk naskah JUSTINDO:
**"Overdispersi Kedatangan Request pada Log Web Server Sektor Publik 2025 dan Perbandingannya dengan NASA 1995"**
(Danang Suryo Wardhono dan Annisa Ramadhani, Magister Informatika, Universitas Negeri Semarang).

## Data

Log mentah tidak disertakan di repositori ini. Unduh dari sumber aslinya:

- **Web Server Log Dataset v1** (Organisasi X dan Y, 2025), Zenodo, lisensi MIT: https://doi.org/10.5281/zenodo.20001206
  Ekstrak `organization-x.zip` dan `organization-y.zip`, lalu letakkan `organization-x.yaml` dan `organization-y.yaml` di folder yang sama.
- **NASA-HTTP, Juli 1995**, Internet Traffic Archive: https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html (berkas `NASA_access_log_Jul95.gz`).

## Isi repositori

| Berkas | Fungsi |
|---|---|
| `revisi_overdispersi.py` | Parsing log (Common/Combined Log Format), pelabelan dengan YAML rules, dan analisis utama: dispersi, model cacah, autokorelasi, uji bebas jitter, non-stasioneritas, alarm palsu, dan sensitivitas pelabelan |
| `config_revisi.yaml` | Konfigurasi path, zona waktu, dan parameter analisis |
| `ekspor_csv_revisi.py` | Mengekspor deret per menit (`orgX.csv`, `orgY.csv`, `nasa.csv`), sampel audit label, dan Tabel A1 (jumlah cocok per aturan) |
| `analisis_tambahan_revisi.py` | Analisis revisi: IK block bootstrap (blok 30/60/120 menit), IK profil r, uji per jam dan per strata, NB + lag, INGARCH(1,1)-NB, diagnostik residual, rolling-origin, serta metrik monitoring (FAR, detection rate, precision, F1) |
| `hasil_revisi.zip`, `hasil_X.zip`, `hasil_Y.zip`, `hasil_NASA/` | Keluaran yang dipakai pada tabel naskah dan lampiran (ekstrak berkas `.zip` untuk melihat isinya) |

## Lingkungan

Python 3.13 dengan paket berikut:

```
pip install numpy pandas scipy matplotlib pyyaml ruptures tabulate
```

## Cara menjalankan

Jalankan dari folder tempat log dan berkas YAML berada:

```
# 1. Parsing + pelabelan + analisis utama (Tabel 1–11)
python revisi_overdispersi.py --config config_revisi.yaml --out hasil_revisi

# 2. Ekspor deret per menit, sampel audit, dan Tabel A1
python ekspor_csv_revisi.py --config config_revisi.yaml --lengkap

# 3. Analisis tambahan revisi (Tabel 8, 10, 12, Lampiran B)
python analisis_tambahan_revisi.py --input orgX.csv --name "Org X" --outdir hasil_X
python analisis_tambahan_revisi.py --input orgY.csv --name "Org Y" --outdir hasil_Y
python analisis_tambahan_revisi.py --input nasa.csv --name "NASA" --outdir hasil_NASA
```

Langkah 1 menyimpan hasil parsing ke `hasil_revisi/cache_*.pkl`, sehingga run berikutnya jauh lebih cepat. Berkas cache tidak diunggah karena ukurannya besar.

## Pemeriksaan hasil

Setelah langkah 2, jumlah request benign harus sama dengan naskah:

- Organisasi X: 201.692
- Organisasi Y: 2.245.963
- NASA: 1.891.712 (semua request)

## Lisensi

Kode dirilis dengan lisensi MIT.
