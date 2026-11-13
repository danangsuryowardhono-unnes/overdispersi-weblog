#!/usr/bin/env python3
"""
ekspor_csv_revisi.py
====================
Menjembatani revisi_overdispersi.py -> analisis_tambahan_revisi.py.

Membaca cache hasil parsing + pelabelan (hasil_revisi/cache_<org>.pkl) yang dibuat
revisi_overdispersi.py, lalu menulis:

  orgX.csv, orgY.csv, nasa.csv      deret per menit: minute, benign, attack
                                     (rentang = menit request pertama s.d. terakhir,
                                      menit kosong = 0, sama persis dengan naskah)
  audit_sampel_<org>.csv            sampel acak 200 request dihapus + 200 dipertahankan
                                     untuk audit manual label (isi kolom label_manual)
  tabelA1_<org>.csv                 (opsi --lengkap) jumlah cocok per aturan, irisan
                                     antaraturan, total unik, dan baris gagal parse

Jalankan di folder "tugas 6" (folder yang sama dengan revisi_overdispersi.py):
  python ekspor_csv_revisi.py --config config_revisi.yaml
  python ekspor_csv_revisi.py --config config_revisi.yaml --lengkap     # + Tabel A1 (lebih lama)

Prasyarat: revisi_overdispersi.py sudah pernah dijalankan sehingga hasil_revisi/cache_*.pkl ada.
"""
import argparse, glob, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import revisi_overdispersi as R   # pakai fungsi parsing & rules yang sama persis

NAMA_CSV = {"X": "orgX.csv", "Y": "orgY.csv", "NASA": "nasa.csv"}
NASKAH_BENIGN = {"X": 201692, "Y": 2245963, "NASA": 1891714}
N_AUDIT = 200


def ekspor_deret(org, df, outdir):
    t = df["time"]
    start = t.min().floor("1min")
    end = t.max().floor("1min") + pd.Timedelta(minutes=1)
    is_nasa = org.upper().startswith("NASA")
    benign_mask = np.ones(len(df), bool) if is_nasa else ~df["atk_any"].to_numpy()
    b = R.minute_counts(t[benign_mask], start, end)
    a = R.minute_counts(t[~benign_mask], start, end) if (~benign_mask).any() else b * 0
    out = pd.DataFrame({"minute": b.index.tz_localize(None).strftime("%Y-%m-%d %H:%M:%S"),
                        "benign": b.to_numpy(), "attack": a.to_numpy()})
    path = os.path.join(outdir, NAMA_CSV.get(org, f"{org}.csv"))
    out.to_csv(path, index=False)
    nb = int(benign_mask.sum())
    cek = NASKAH_BENIGN.get(org)
    status = "COCOK" if cek == nb else f"BEDA dengan naskah ({cek:,})"
    print(f"   {org}: {len(out):,} menit, request {'(semua)' if is_nasa else 'benign'} = {nb:,} -> {status}")
    print(f"        rata-rata {out.benign.mean():.2f}/menit, D = {out.benign.var(ddof=1) / out.benign.mean():.2f}"
          f" | ditulis ke {path}")
    return out


def ekspor_audit(org, df, outdir, seed=2026):
    if org.upper().startswith("NASA") or not df["atk_any"].any():
        return
    cols = [c for c in ["time", "vhost", "ip", "method", "path", "status", "ua", "gt_label"] if c in df]
    rng = np.random.default_rng(seed)
    parts = []
    for grp, mask in [("dihapus", df["atk_any"]), ("dipertahankan", ~df["atk_any"])]:
        idx = np.flatnonzero(mask.to_numpy())
        pick = rng.choice(idx, size=min(N_AUDIT, len(idx)), replace=False)
        s = df.iloc[np.sort(pick)][cols].copy()
        s.insert(0, "kelompok", grp)
        parts.append(s)
    out = pd.concat(parts)
    out["label_manual"] = ""          # isi: serangan / normal / ragu
    out["catatan"] = ""
    path = os.path.join(outdir, f"audit_sampel_{org}.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"   audit: {len(out)} baris -> {path} (isi kolom label_manual)")


def tabel_a1(org, oc, cfg, outdir):
    """Parsing ulang dengan fungsi yang sama untuk menghitung gagal parse dan irisan antaraturan."""
    rp = oc.get("rules_path", cfg.get("rules_path"))
    if not rp:
        return
    files = sorted({f for pat in oc["paths"] for f in glob.glob(pat, recursive=True) if os.path.isfile(f)})
    gagal = 0
    for f in files:
        with R.open_any(f) as fh:
            s = pd.Series(fh.read().splitlines())
        if not s.empty:
            gagal += int(s.str.extract(R.LOG_RE)["ts"].isna().sum())
    df = R.parse_files(oc["paths"], oc.get("vhost_from", "none"))
    df["time"] = df["time"].dt.tz_convert(oc["tz"])
    if oc.get("start"):
        df = df[df["time"] >= pd.Timestamp(oc["start"], tz=oc["tz"])]
    if oc.get("end"):
        df = df[df["time"] < pd.Timestamp(oc["end"], tz=oc["tz"])]
    df = df.reset_index(drop=True)
    rules = R.load_rules(rp, cfg.get("percent_mode", "auto"), cfg.get("legacy_regex", False))
    low = df["line"].str.lower()
    if cfg.get("strip_quotes", True):
        low = low.str.replace('"', " ", regex=False)
    status = df["status"].astype(str)
    n_hit = np.zeros(len(df), dtype=np.int16)
    rows = []
    for r in rules:
        hit = np.ones(len(df), dtype=bool)
        for kind, val in r["conds"]:
            if kind == "status":
                hit &= (status == val).to_numpy()
            elif kind == "literal":
                hit &= low.str.contains(val, regex=False, na=False).to_numpy()
            else:
                try:
                    hit &= low.str.contains(val, regex=True, na=False).to_numpy()
                except Exception:
                    hit &= False
            if not hit.any():
                break
        n_hit += hit
        rows.append({"aturan": r["id"], "label": r["label"], "mode": r["sensitivity"],
                     "sumber": r["source"], "n_cocok": int(hit.sum())})
    t = pd.DataFrame(rows)
    t = t[t.n_cocok > 0].sort_values("n_cocok", ascending=False)
    unik = int((n_hit > 0).sum())
    ringkas = pd.DataFrame([
        {"aturan": "IRISAN: request cocok >= 2 aturan", "n_cocok": int((n_hit >= 2).sum())},
        {"aturan": "TOTAL UNIK ditandai serangan", "n_cocok": unik,
         "label": f"{100 * unik / max(len(df), 1):.3f}% dari {len(df):,} request"},
        {"aturan": "Baris gagal parse (semua file yang dibaca)", "n_cocok": gagal},
    ])
    out = pd.concat([t, ringkas], ignore_index=True)
    path = os.path.join(outdir, f"tabelA1_{org}.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"   Tabel A1: {len(t)} aturan cocok, irisan {int((n_hit >= 2).sum()):,}, total unik {unik:,},"
          f" gagal parse {gagal:,} -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_revisi.yaml")
    ap.add_argument("--cache", default="hasil_revisi", help="folder cache_<org>.pkl")
    ap.add_argument("--out", default=".", help="folder tujuan CSV")
    ap.add_argument("--lengkap", action="store_true", help="hitung juga Tabel A1 (parsing ulang, lebih lama)")
    a = ap.parse_args()
    cfg = R.load_config(a.config)
    os.makedirs(a.out, exist_ok=True)
    for org, oc in cfg["orgs"].items():
        cache = os.path.join(a.cache, f"cache_{org}.pkl")
        print(f"\n=== {org} ===")
        if not os.path.exists(cache):
            print(f"   {cache} tidak ada. Jalankan dulu:\n"
                  f"   python revisi_overdispersi.py --config {a.config} --only-parse")
            continue
        df = pd.read_pickle(cache)
        ekspor_deret(org, df, a.out)
        ekspor_audit(org, df, a.out)
        if a.lengkap:
            tabel_a1(org, oc, cfg, a.out)
    print("\nSelesai. Langkah berikutnya:\n"
          "  python analisis_tambahan_revisi.py --input orgX.csv --name \"Org X\" --outdir hasil_X\n"
          "  python analisis_tambahan_revisi.py --input orgY.csv --name \"Org Y\" --outdir hasil_Y\n"
          "  python analisis_tambahan_revisi.py --input nasa.csv --name \"NASA\" --outdir hasil_NASA")


if __name__ == "__main__":
    main()
