# -*- coding: utf-8 -*-
"""Kesepakatan pelabelan ulang (diri sendiri). Pemakaian:
    python kappa_label.py audit_sampel_X_lama.csv audit_sampel_X_baru.csv
Kedua berkas berasal dari audit_sampel_<org>.csv yang sama; kolom label_manual berisi serangan / normal / ragu.
Labeli ulang pada salinan berkas baru TANPA membuka label lama."""
import sys
import pandas as pd
a = pd.read_csv(sys.argv[1]); b = pd.read_csv(sys.argv[2])
assert len(a) == len(b), "jumlah baris berbeda"
x = a["label_manual"].astype(str).str.strip().str.lower()
y = b["label_manual"].astype(str).str.strip().str.lower()
n = len(x); po = (x == y).mean()
cats = sorted(set(x) | set(y))
pe = sum((x == c).mean() * (y == c).mean() for c in cats)
kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
print(f"n = {n}; kesepakatan mentah = {po:.3f}; Cohen's kappa = {kappa:.3f}")
print(pd.crosstab(x, y, rownames=["pelabelan 1"], colnames=["pelabelan 2"]))
