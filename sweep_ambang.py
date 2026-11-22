# -*- coding: utf-8 -*-
"""Sapu ambang min_attack_req_per_min = 1, 5, 10, 20, 50 dan kumpulkan isu4_false_alarm.csv.
Jalankan dari folder yang berisi revisi_overdispersi.py dan config_revisi.yaml:
    python sweep_ambang.py
config_revisi.yaml TIDAK diubah; skrip membuat salinan config_ambang_<k>.yaml.
Bila hasil_revisi/cache_*.pkl sudah ada, cache disalin ke tiap folder keluaran agar log tidak diparsing ulang
(ambang hanya memengaruhi isu 4, bukan hasil parsing).
Hasil: hasil_ambang_<k>/ (satu folder per nilai) dan tabel_B3_sensitivitas_ambang.csv (gabungan)."""
import glob, os, re, shutil, subprocess, sys
import pandas as pd

NILAI = [1, 5, 10, 20, 50]
cfg = open("config_revisi.yaml", encoding="utf-8").read()
assert re.search(r"^min_attack_req_per_min:\s*\d+", cfg, re.M), "kunci min_attack_req_per_min tidak ditemukan"
gab = []
for k in NILAI:
    nama = f"config_ambang_{k}.yaml"
    open(nama, "w", encoding="utf-8").write(
        re.sub(r"^(min_attack_req_per_min:\s*)\d+", rf"\g<1>{k}", cfg, flags=re.M))
    out = f"hasil_ambang_{k}"
    os.makedirs(out, exist_ok=True)
    for c in glob.glob(os.path.join("hasil_revisi", "cache_*.pkl")):
        tujuan = os.path.join(out, os.path.basename(c))
        if not os.path.exists(tujuan):
            shutil.copy2(c, tujuan)
    print(f"== ambang {k} ==", flush=True)
    subprocess.run([sys.executable, "revisi_overdispersi.py", "--config", nama, "--out", out], check=True)
    df = pd.read_csv(os.path.join(out, "isu4_false_alarm.csv"))
    df.insert(0, "min_attack_req_per_min", k)
    gab.append(df)
pd.concat(gab).to_csv("tabel_B3_sensitivitas_ambang.csv", index=False)
print("selesai: tabel_B3_sensitivitas_ambang.csv")
