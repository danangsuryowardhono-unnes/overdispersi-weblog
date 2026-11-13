#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
revisi_overdispersi.py  (versi 4: perbaikan rentang menit, satuan waktu pandas 3, chi-square)
======================
Analisis tambahan untuk menjawab 5 isu mayor peer review naskah
"Overdispersi Kedatangan Request pada Log Web Server Sektor Publik 2025
dan Perbandingannya dengan NASA 1995".

  Isu 1  Autokorelasi      : ACF + Ljung-Box, CI indeks dispersi D dengan
                             moving block bootstrap, uji dispersi pada deret
                             yang dijarangkan (thinning), NB dengan lag.
  Isu 2  Jitter            : uji bebas jitter (jumlah per detik, proporsi
                             detik kosong, panjang run detik kosong vs
                             geometrik), sensitivitas jitter 100 seed,
                             distribusi alternatif (Weibull/lognormal/gamma).
  Isu 3  Non-stasioner Y   : change-point pada total harian, analisis ulang
                             pada periode stabil, NB dengan offset jumlah
                             virtual host aktif, analisis per virtual host.
  Isu 4  False alarm       : FAR fase II + alarm palsu/hari + detection rate
                             untuk ambang Poisson, mu+3*sqrt(mu), NHPP, NB.
  Isu 5  Sensitivitas label: 4 skenario pelabelan (tanpa hapus / strict /
                             moderate / strict+moderate) + YAML rules diterapkan pada NASA.

Cara pakai
----------
  pip install pandas numpy scipy pyyaml matplotlib ruptures tabulate   (statsmodels tidak diperlukan)
  python revisi_overdispersi.py --config config.yaml --out hasil_revisi

Jalankan sekali dengan --only-parse untuk memeriksa hasil parsing dan
ringkasan YAML rules sebelum analisis penuh. Hasil parsing di-cache ke
<out>/cache_<org>.pkl sehingga run berikutnya jauh lebih cepat.

Pelabelan memakai organization-x.yaml / organization-y.yaml (skema: id,
ground_truth_label, sensitivity, filter AND). Lihat bagian 2 untuk aturan
interpretasi pola, dan file label_per_rule_<org>.csv untuk jumlah kecocokan.
"""
import argparse, glob, gzip, io, json, math, os, re, sys, warnings
from collections import Counter

import numpy as np
import pandas as pd
from scipy import stats, optimize

warnings.filterwarnings("ignore")
ALPHA_ALARM = 0.00135          # setara batas tiga-sigma satu sisi
RNG_SEED = 2026

# =============================================================================
# 0. KONFIGURASI
# =============================================================================
DEFAULT_CONFIG = {
    # Struktur folder yang diharapkan (ekstrak organization-x.zip & organization-y.zip):
    #   data/organization-x/...  -> web-access.log, web-access.log.1, web-access.log.N.gz, access.log
    #   data/organization-y/...  -> <vhost>.access_log, <vhost>.access_log.YYYY_MM_DD(.NN)
    #   data/NASA_access_log_Jul95.gz
    #   data/organization-x.yaml, data/organization-y.yaml   (YAML ground truth / rules)
    # error_log, web-error.log, other_vhosts_access.log, auth.log, syslog tidak dibaca.
    "orgs": {
        "X": {"paths": ["data/organization-x/**/web-access.log*", "data/organization-x/**/access.log"],
              "rules_path": "data/organization-x.yaml", "tz": "Asia/Jakarta",
              "start": None, "end": None, "vhost_from": "none", "expected_total": 213205, "expected_benign": 212478},
        "Y": {"paths": ["data/organization-y/**/*.access_log*"],
              "rules_path": "data/organization-y.yaml", "tz": "Asia/Jakarta",
              "start": "2025-04-13", "end": None, "vhost_from": "filename", "expected_total": 7084558, "expected_benign": 2245963},
        "NASA": {"paths": ["data/NASA_access_log_Jul95*"],
                 "rules_path": ["data/organization-x.yaml", "data/organization-y.yaml"], "tz": "Etc/GMT+4",
                 "start": None, "end": None, "vhost_from": "none", "expected_total": 1891714},
    },
        "strict_modes": ["strict"],
    "percent_mode": "auto",
    "strip_quotes": True,        # samakan dengan pipeline lama (rule " python")
    "legacy_regex": False,       # True = tiru pipeline lama (pola LIKE tanpa escape)      # auto: '%' di awal pola = wildcard LIKE; lainnya literal
    "phase1_frac": 0.6,
    "block_len_min": 60,          # panjang blok bootstrap (menit)
    "n_boot": 1000,
    "n_jitter_seeds": 100,
    "ks_sample": 200_000,
    "min_attack_req_per_min": 10, # menit dihitung "menit serangan" bila >= nilai ini
    "min_vhost_requests": 5000,   # ambang vhost untuk analisis per vhost
    "stable_start_Y": None,       # isi manual (mis. "2025-04-20") untuk menimpa hasil change-point
}


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        import yaml
        with open(path, encoding="utf8") as f:
            user = yaml.safe_load(f) or {}
        for k, v in user.items():
            if k == "orgs":
                for o, oc in v.items():
                    cfg["orgs"].setdefault(o, {}).update(oc)
            else:
                cfg[k] = v
    return cfg


# =============================================================================
# 1. PARSING LOG (Common / Combined Log Format)
# =============================================================================
LOG_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<request>.*?)" '
    r'(?P<status>\d{3}|-) (?P<size>\S+)(?: "(?P<referer>.*?)" "(?P<ua>.*?)")?'
)


def open_any(p):
    return gzip.open(p, "rt", encoding="utf8", errors="replace") if p.endswith(".gz") \
        else open(p, encoding="utf8", errors="replace")


def parse_files(paths, vhost_from):
    files = sorted({f for pat in paths for f in glob.glob(pat, recursive=True) if os.path.isfile(f)})
    if not files:
        raise FileNotFoundError(f"Tidak ada file untuk pola {paths}")
    frames = []
    for f in files:
        base = os.path.basename(f)
        m = re.match(r"^(.+?)\.access_log", base)
        vh = (m.group(1) if m else re.sub(r"(\.log)?(\.\d+)?(\.gz)?$", "", base)) \
            if vhost_from == "filename" else "all"
        with open_any(f) as fh:
            s = pd.Series(fh.read().splitlines())
        if s.empty:
            continue
        df = s.str.extract(LOG_RE)
        df["line"] = s
        bad = df["ts"].isna().sum()
        df = df.dropna(subset=["ts"])
        df["vhost"] = vh
        frames.append(df)
        print(f"   {os.path.basename(f)}: {len(df):,} baris valid, {bad:,} dilewati")
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["ts"], format="%d/%b/%Y:%H:%M:%S %z", utc=True, errors="coerce")
    df = df.dropna(subset=["time"]).drop(columns=["ts"])
    rq = df["request"].fillna("").str.extract(r"^(\S*)\s*(.*?)(?:\s+HTTP/[\d.]+)?$")
    df["method"], df["path"] = rq[0].fillna(""), rq[1].fillna("")
    for c in ["ua", "referer"]:
        df[c] = df[c].fillna("")
    return df


# =============================================================================
# 2. YAML RULES  (skema Web Server Log Dataset: organization-x.yaml / organization-y.yaml)
# =============================================================================
#   - id: dir_scan
#     ground_truth_label: dir_scan
#     sensitivity: moderate | strict
#     filter: [pola1, pola2, ...]     -> SEMUA pola harus cocok (AND), case-insensitive
#
# Aturan interpretasi pola (dicocokkan ke baris log mentah, huruf kecil):
#   * "code: NNN"        -> kode status HTTP == NNN (bentuk log2timeline; di log mentah = kolom status)
#   * pola diawali '%'   -> wildcard gaya SQL LIKE: '%' = sembarang karakter (dipakai rule strict)
#   * selain itu         -> substring literal (mis. "SELECT%" = teks "select%", URL-encoded)
#   Mode '%' dapat diubah lewat config: percent_mode = auto | like | literal
def _cond(pat, percent_mode, legacy_regex=False):
    p = str(pat)
    m = re.fullmatch(r"\s*code:\s*(\d{3})\s*", p, flags=re.I)
    if m:
        return ("status", m.group(1))
    like = (percent_mode == "like") or (percent_mode == "auto" and p.startswith("%"))
    if like and "%" in p:
        esc = (lambda t: t) if legacy_regex else re.escape
        parts = [esc(x.lower()) for x in p.split("%") if x]
        return ("regex", ".*".join(parts) if parts else ".*")
    return ("literal", p.lower())


def load_rules(path, percent_mode="auto", legacy_regex=False):
    import yaml
    paths = path if isinstance(path, list) else [path]
    rules = []
    for f in paths:
        if not os.path.exists(f):
            raise FileNotFoundError(f"File rules tidak ditemukan: {f}")
        with open(f, encoding="utf8") as fh:
            doc = yaml.safe_load(fh)
        items = doc if isinstance(doc, list) else (doc or {}).get("rules", [])
        for i, r in enumerate(items):
            flt = r.get("filter") or []
            flt = flt if isinstance(flt, list) else [flt]
            if not flt:
                continue
            rules.append({"id": r.get("id", f"rule{i}"),
                          "label": r.get("ground_truth_label", r.get("id", "")),
                          "sensitivity": str(r.get("sensitivity", "moderate")).lower(),
                          "conds": [_cond(x, percent_mode, legacy_regex) for x in flt],
                          "source": os.path.basename(f)})
    if not rules:
        raise ValueError(f"Tidak ada rule terbaca dari {path}")
    print(f"\n   --- RINGKASAN RULES ({', '.join(os.path.basename(p) for p in paths)}) ---")
    print(f"   total rule: {len(rules)} | per sensitivity: {dict(Counter(r['sensitivity'] for r in rules))}")
    return rules


def apply_rules(df, rules, strict_modes, strip_quotes=True):
    """Kolom atk_strict, atk_moderate, atk_any + label pertama yang cocok.
    strip_quotes=True: tanda kutip diganti spasi sebelum pencocokan (setara pipeline lama,
    sehingga rule " python" cocok dengan user-agent "python-requests/...")."""
    strict_modes = {m.lower() for m in strict_modes}
    low = df["line"].str.lower()
    if strip_quotes:
        low = low.str.replace('"', " ", regex=False)
    status = df["status"].astype(str)
    df["atk_strict"] = False
    df["atk_moderate"] = False
    df["gt_label"] = ""
    stats_rows = []
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
                except re.error:
                    hit &= False
            if not hit.any():
                break
        n = int(hit.sum())
        stats_rows.append({"source": r["source"], "id": r["id"], "label": r["label"],
                           "sensitivity": r["sensitivity"],
                           "filter": " AND ".join(f"{k}:{v}" for k, v in r["conds"]), "n_match": n})
        if n:
            col = "atk_strict" if r["sensitivity"] in strict_modes else "atk_moderate"
            df[col] |= hit
            df.loc[hit & (df["gt_label"] == "").to_numpy(), "gt_label"] = r["label"]
    df["atk_any"] = df["atk_strict"] | df["atk_moderate"]
    st = pd.DataFrame(stats_rows)
    print(st[st["n_match"] > 0][["id", "label", "sensitivity", "n_match"]].to_string(index=False)
          if (st["n_match"] > 0).any() else "   (tidak ada rule yang cocok)")
    return df, st


# =============================================================================
# 3. FUNGSI STATISTIK DASAR
# =============================================================================
def minute_counts(times, start, end, freq="1min"):
    idx = pd.date_range(start, end, freq=freq, inclusive="left")
    c = times.dt.floor(freq).value_counts().reindex(idx, fill_value=0)
    return c.sort_index()


def dispersion(y):
    y = np.asarray(y, float)
    n, m, v = len(y), y.mean(), y.var(ddof=1)
    D = v / m if m > 0 else np.nan
    p = stats.chi2.sf((n - 1) * D, n - 1)
    return D, p


def chisq_poisson(y):
    y = np.asarray(y, int)
    lam = y.mean()
    kmax = y.max()
    obs = np.bincount(y, minlength=kmax + 1).astype(float)
    exp = stats.poisson.pmf(np.arange(kmax + 1), lam) * len(y)
    exp[-1] += stats.poisson.sf(kmax, lam) * len(y)
    # gabung kelas dari kedua ekor hingga E >= 5
    o, e = list(obs), list(exp)
    while len(e) > 2 and e[0] < 5:
        v, w = e.pop(0), o.pop(0); e[0] += v; o[0] += w
    while len(e) > 2 and e[-1] < 5:
        v, w = e.pop(), o.pop(); e[-1] += v; o[-1] += w
    o, e = np.array(o), np.array(e)
    chi = ((o - e) ** 2 / e).sum()
    df = max(len(e) - 2, 1)
    return chi, df, stats.chi2.sf(chi, df)


def nb_ll(y, mu, r):
    return stats.nbinom.logpmf(y, r, r / (r + mu)).sum()


def fit_r(y, mu):
    res = optimize.minimize_scalar(lambda lr: -nb_ll(y, mu, math.exp(lr)),
                                   bounds=(-8, 12), method="bounded")
    return math.exp(res.x), -res.fun


def fit_models(series, phase1_frac=0.6):
    """Poisson homogen, NHPP per jam, NB (mean per jam). Fase I fit, fase II uji."""
    y = series.to_numpy().astype(int)
    h = series.index.hour.to_numpy()
    n1 = int(len(y) * phase1_frac)
    y1, y2, h1, h2 = y[:n1], y[n1:], h[:n1], h[n1:]
    lam = y1.mean()
    mu_h = pd.Series(y1).groupby(h1).mean().reindex(range(24)).fillna(lam).to_numpy()
    mu_h = np.maximum(mu_h, 1e-6)
    out = {}
    ll = stats.poisson.logpmf(y1, lam).sum()
    out["Poisson homogen"] = dict(k=1, ll1=ll, ll2=stats.poisson.logpmf(y2, lam).sum())
    ll = stats.poisson.logpmf(y1, mu_h[h1]).sum()
    out["NHPP per jam"] = dict(k=24, ll1=ll, ll2=stats.poisson.logpmf(y2, mu_h[h2]).sum())
    r, ll = fit_r(y1, mu_h[h1])
    out["Binomial negatif"] = dict(k=25, ll1=ll, ll2=nb_ll(y2, mu_h[h2], r), r=r)
    for m in out.values():
        m["AIC"] = 2 * m["k"] - 2 * m["ll1"]
        m["BIC"] = m["k"] * math.log(n1) - 2 * m["ll1"]
    lrt1 = 2 * (out["NHPP per jam"]["ll1"] - out["Poisson homogen"]["ll1"])
    lrt2 = 2 * (out["Binomial negatif"]["ll1"] - out["NHPP per jam"]["ll1"])
    meta = dict(lam=lam, mu_h=mu_h, r=r, n1=n1,
                LRT_NHPP_vs_Pois=lrt1, p1=stats.chi2.sf(lrt1, 23),
                LRT_NB_vs_NHPP=lrt2, p2=0.5 * stats.chi2.sf(lrt2, 1))
    return out, meta


def interarrival(times, seed=0):
    # detik sejak epoch, aman untuk resolusi ns (pandas 2) maupun us (pandas 3)
    sec = np.sort(((times - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)).to_numpy()).astype(float)
    rng = np.random.default_rng(seed)
    t = np.sort(sec + rng.uniform(0, 1, len(sec)))
    return np.diff(t)


def ks_cv(gaps, n=200_000, seed=0):
    rng = np.random.default_rng(seed)
    g = rng.choice(gaps, size=min(n, len(gaps)), replace=False)
    ks = stats.kstest(g, "expon", args=(0, g.mean()))
    return ks.statistic, ks.pvalue, g.std(ddof=1) / g.mean()


def block_bootstrap_D(y, L, B, seed=RNG_SEED):
    y = np.asarray(y, float)
    n = len(y)
    k = int(np.ceil(n / L))
    rng = np.random.default_rng(seed)
    Ds = np.empty(B)
    base = np.arange(L)
    for b in range(B):
        starts = rng.integers(0, n - L + 1, size=k)
        idx = (starts[:, None] + base[None, :]).ravel()[:n]
        s = y[idx]
        Ds[b] = s.var(ddof=1) / s.mean()
    return np.percentile(Ds, [2.5, 97.5])



# ---- pengganti statsmodels (hanya numpy/scipy; aman dari blokir DLL Windows) ----
from scipy.special import gammaln, digamma


def acf_np(y, nlags):
    y = np.asarray(y, float) - np.mean(y)
    n = len(y)
    f = np.fft.rfft(y, n=2 ** int(np.ceil(np.log2(2 * n))))
    ac = np.fft.irfft(f * np.conj(f))[:nlags + 1]
    return ac / ac[0]


def ljung_box_p(y, lag):
    n = len(y)
    r = acf_np(y, lag)[1:]
    q = n * (n + 2) * np.sum(r ** 2 / (n - np.arange(1, lag + 1)))
    return stats.chi2.sf(q, lag)


def nb2_fit(y, X, offset=None):
    """GLM binomial negatif (NB2, link log) dengan MLE: return (beta, alpha, loglik, aic)."""
    y = np.asarray(y, float); X = np.asarray(X, float)
    off = np.zeros(len(y)) if offset is None else np.asarray(offset, float)
    k = X.shape[1]
    b0 = np.zeros(k); b0[0] = np.log(max(y.mean(), 1e-6)) - off.mean()

    def nll(theta):
        b, la = theta[:k], np.clip(theta[k], -15, 10)
        a = np.exp(la); eta = np.clip(X @ b + off, -30, 30); mu = np.exp(eta)
        ia = 1.0 / a
        ll = (gammaln(y + ia) - gammaln(ia) - gammaln(y + 1)
              - ia * np.log1p(a * mu) + y * (np.log(a * mu) - np.log1p(a * mu)))
        gb = X.T @ ((y - mu) / (1 + a * mu))
        ga = np.sum(ia ** 2 * (digamma(ia) - digamma(y + ia) + np.log1p(a * mu))
                    + (y - mu) / (a * (1 + a * mu)))
        return -ll.sum(), -np.r_[gb, ga * a]

    res = optimize.minimize(nll, np.r_[b0, 0.0], jac=True, method="L-BFGS-B",
                            options={"maxiter": 2000})
    ll = -res.fun
    return res.x[:k], float(np.exp(res.x[k])), ll, 2 * (k + 1) - 2 * ll


def hour_design(hours, extra=None):
    H = pd.get_dummies(pd.Categorical(hours, categories=range(24)), drop_first=True).to_numpy(float)
    cols = [np.ones(len(hours)), *H.T]
    if extra is not None:
        cols += list(np.asarray(extra, float).T)
    return np.column_stack(cols)

# =============================================================================
# 4. ANALISIS PER ISU
# =============================================================================
def issue1_autocorr(org, s1, cfg, outdir):
    y = s1.to_numpy().astype(float)
    a = acf_np(y, 120)
    lb_p60 = ljung_box_p(y, 60)
    D, pD = dispersion(y)
    lo, hi = block_bootstrap_D(y, cfg["block_len_min"], cfg["n_boot"])
    thr = 2 / math.sqrt(len(y))
    k = next((i for i in range(1, len(a)) if abs(a[i]) < thr), 120)
    yt = y[::k]
    Dt, pDt = dispersion(yt)
    # NB dengan dummy jam + lag (menangkap autokorelasi)
    r_lag = np.nan
    try:
        d = pd.DataFrame({"y": y, "h": s1.index.hour})
        d["l1"] = np.log1p(d["y"].shift(1)); d["l60"] = np.log1p(d["y"].shift(60))
        d = d.dropna()
        _, alpha, _, _ = nb2_fit(d["y"], hour_design(d["h"].to_numpy(), d[["l1", "l60"]].to_numpy()))
        r_lag = 1 / alpha
    except Exception as e:
        print(f"   [isu1] NB-lag gagal: {e}")
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.bar(range(1, 121), a[1:], color="0.3", width=0.8)
        ax.axhline(thr, ls="--", c="k", lw=0.8); ax.axhline(-thr, ls="--", c="k", lw=0.8)
        ax.set_xlabel("Lag (menit)"); ax.set_ylabel("ACF"); ax.set_title(f"ACF jumlah request per menit - {org}")
        fig.tight_layout(); fig.savefig(os.path.join(outdir, f"acf_{org}.png"), dpi=200); plt.close(fig)
    except Exception:
        pass
    return dict(Org=org, ACF_lag1=a[1], ACF_lag60=a[60] if len(a) > 60 else np.nan,
                LjungBox_p_lag60=lb_p60, D=D, p_D=pD,
                D_CI95_lo=lo, D_CI95_hi=hi, thinning_k=k, n_thinned=len(yt),
                D_thinned=Dt, p_D_thinned=pDt, r_NB_hour=np.nan, r_NB_hour_lag=r_lag)


def issue2_jitter(org, times, cfg):
    sec = times.dt.floor("1s")
    start, end = sec.min(), sec.max() + pd.Timedelta(seconds=1)
    cs = sec.value_counts().reindex(pd.date_range(start, end, freq="1s", inclusive="left"), fill_value=0).sort_index()
    y = cs.to_numpy()
    lam = y.mean()
    D1, pD1 = dispersion(y)
    # D per detik terkondisi jam (rata-rata per jam)
    mu_h = pd.Series(y).groupby(cs.index.hour).transform("mean").to_numpy()
    D1h = ((y - mu_h) ** 2).sum() / (len(y) - 24) / y.mean()
    p0_obs = (y == 0).mean(); p0_exp = math.exp(-lam)
    z0 = (p0_obs - p0_exp) / math.sqrt(p0_exp * (1 - p0_exp) / len(y))
    # panjang run detik kosong vs geometrik(1 - e^-lam)
    z = (y == 0).astype(int)
    runs = np.diff(np.flatnonzero(np.diff(np.r_[0, z, 0]) != 0))[::2] if z.any() else np.array([])
    q = 1 - p0_exp
    chi_run = p_run = np.nan
    if len(runs) > 50:
        kmax = int(np.percentile(runs, 99))
        obs = np.array([(runs == k).sum() for k in range(1, kmax + 1)] + [(runs > kmax).sum()], float)
        pk = stats.geom.pmf(np.arange(1, kmax + 1), q)
        exp = np.r_[pk, stats.geom.sf(kmax, q)] * len(runs)
        keep = exp >= 5
        o2 = np.r_[obs[keep], obs[~keep].sum()]; e2 = np.r_[exp[keep], exp[~keep].sum()]
        if e2[-1] == 0: o2, e2 = o2[:-1], e2[:-1]
        chi_run = ((o2 - e2) ** 2 / e2).sum(); p_run = stats.chi2.sf(chi_run, max(len(e2) - 2, 1))
    # sensitivitas jitter
    res = []
    for s in range(cfg["n_jitter_seeds"]):
        g = interarrival(times, seed=s)
        ks, _, cv = ks_cv(g, cfg["ks_sample"], seed=s)
        res.append((ks, cv))
    res = np.array(res)
    # distribusi alternatif (seed 0)
    g = interarrival(times, seed=0)
    rng = np.random.default_rng(0)
    g = rng.choice(g[g > 0], size=min(cfg["ks_sample"], (g > 0).sum()), replace=False)
    fits = []
    for name, dist in [("Eksponensial", stats.expon), ("Weibull", stats.weibull_min),
                       ("Lognormal", stats.lognorm), ("Gamma", stats.gamma)]:
        try:
            par = dist.fit(g, floc=0)
            ll = dist.logpdf(g, *par).sum()
            k = len(par) - 1
            fits.append(dict(Org=org, Distribusi=name, AIC=2 * k - 2 * ll,
                             KS=stats.kstest(g, dist.cdf, args=par).statistic,
                             Parameter=", ".join(f"{p:.4g}" for p in par)))
        except Exception as e:
            print(f"   [isu2] fit {name} gagal: {e}")
    row = dict(Org=org, lambda_per_detik=lam, D_per_detik=D1, p_D_per_detik=pD1,
               D_per_detik_terkondisi_jam=D1h, prop_detik_kosong_obs=p0_obs,
               prop_detik_kosong_Poisson=p0_exp, z_detik_kosong=z0,
               chi2_run_kosong_vs_geom=chi_run, p_run=p_run,
               KS_min=res[:, 0].min(), KS_max=res[:, 0].max(),
               CV_min=res[:, 1].min(), CV_max=res[:, 1].max())
    return row, fits


def issue3_nonstationary(df, s1, cfg, outdir):
    daily = s1.resample("1D").sum()
    vh_day = df.groupby(df["time"].dt.floor("1D"))["vhost"].nunique()
    vh_day = vh_day.reindex(daily.index).ffill().bfill()
    cp_date = cfg.get("stable_start_Y")
    if not cp_date:
        try:
            import ruptures as rpt
            sig = np.log1p(daily.to_numpy()).reshape(-1, 1)
            try:
                bk = rpt.Binseg(model="l2", min_size=2, jump=1).fit(sig).predict(n_bkps=1)
            except Exception:
                bk = []
            bks = [b for b in bk if b < len(daily)]
            cp_date = str(daily.index[bks[0]].date()) if bks else str(daily.index[0].date())
            print(f"   [isu3] change-point (ruptures/Binseg, 1 titik): indeks hari {bks} -> periode stabil mulai {cp_date}")
        except ImportError:
            raise SystemExit("ruptures tidak terpasang: pip install ruptures, atau isi stable_start_Y di config")
    st = pd.Timestamp(cp_date, tz=s1.index.tz)
    rows = []
    for label, s in [("Periode penuh", s1), (f"Periode stabil (>= {cp_date})", s1[s1.index >= st])]:
        m, meta = fit_models(s, cfg["phase1_frac"])
        D, _ = dispersion(s)
        best_in = min(m, key=lambda k: m[k]["AIC"]); best_out = max(m, key=lambda k: m[k]["ll2"])
        rows.append(dict(Periode=label, n_menit=len(s), rata2=s.mean(), D=D, r=meta["r"],
                         AIC_NB_pct_Poisson=100 * m["Binomial negatif"]["AIC"] / m["Poisson homogen"]["AIC"],
                         terbaik_in_sample=best_in, terbaik_out_of_sample=best_out,
                         ll2_Poisson=m["Poisson homogen"]["ll2"], ll2_NHPP=m["NHPP per jam"]["ll2"],
                         ll2_NB=m["Binomial negatif"]["ll2"]))
    # NB dengan offset log(vhost aktif)
    try:
        vh = vh_day.reindex(s1.index.floor("1D")).to_numpy().astype(float)
        X = hour_design(s1.index.hour.to_numpy())
        yy = s1.to_numpy()
        _, a0, _, aic0 = nb2_fit(yy, X)
        _, a1, _, aic1 = nb2_fit(yy, X, offset=np.log(vh))
        rows.append(dict(Periode="Periode penuh, NB + offset log(vhost aktif)", n_menit=len(yy),
                         r=1 / a1, r_tanpa_offset=1 / a0, AIC_NB_offset=aic1, AIC_NB_tanpa_offset=aic0))
    except Exception as e:
        print(f"   [isu3] NB-offset gagal: {e}")
    # per virtual host
    per = []
    start, end = s1.index[0], s1.index[-1] + pd.Timedelta(minutes=1)
    for vh, g in df.groupby("vhost"):
        if len(g) < cfg["min_vhost_requests"]:
            continue
        g0 = g[g["time"] >= st]
        if g0.empty:
            continue
        s = minute_counts(g0["time"], max(st, g0["time"].min().floor("1min")), end)
        if s.sum() < cfg["min_vhost_requests"] / 2:
            continue
        D, _ = dispersion(s)
        mu = s.groupby(s.index.hour).transform("mean").to_numpy()
        r, _ = fit_r(s.to_numpy(), np.maximum(mu, 1e-6))
        per.append(dict(vhost=vh, n_request=len(g0), rata2_per_menit=s.mean(), D=D, r=r))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax1 = plt.subplots(figsize=(7, 3))
        ax1.plot(daily.index, daily.values, "k-o", ms=3, label="Request/hari")
        ax1.axvline(st, ls="--", c="0.4"); ax1.set_ylabel("Request benign per hari")
        ax2 = ax1.twinx(); ax2.plot(vh_day.index, vh_day.values, "s--", c="0.5", ms=3, label="vhost aktif")
        ax2.set_ylabel("Virtual host aktif"); ax1.set_title("Organisasi Y: level trafik dan cakupan log")
        fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(os.path.join(outdir, "changepoint_Y.png"), dpi=200); plt.close(fig)
    except Exception:
        pass
    return rows, per


def issue4_false_alarm(org, s_benign, s_attack, cfg):
    m, meta = fit_models(s_benign, cfg["phase1_frac"])
    n1 = meta["n1"]
    y2 = s_benign.to_numpy()[n1:]
    a2 = s_attack.reindex(s_benign.index, fill_value=0).to_numpy()[n1:]
    h2 = s_benign.index.hour.to_numpy()[n1:]
    lam, mu_h, r = meta["lam"], meta["mu_h"], meta["r"]
    mu2 = mu_h[h2]
    thr = {
        "Poisson homogen, mu+3*sqrt(mu)": np.full(len(y2), lam + 3 * math.sqrt(lam)),
        "Poisson homogen, kuantil": np.full(len(y2), stats.poisson.ppf(1 - ALPHA_ALARM, lam)),
        "NHPP per jam, mu_h+3*sqrt(mu_h)": mu2 + 3 * np.sqrt(mu2),
        "NHPP per jam, kuantil": stats.poisson.ppf(1 - ALPHA_ALARM, mu2),
        "Binomial negatif, kuantil": stats.nbinom.ppf(1 - ALPHA_ALARM, r, r / (r + mu2)),
    }
    tot = y2 + a2
    atk_min = a2 >= cfg["min_attack_req_per_min"]
    rows = []
    for name, t in thr.items():
        far = (y2 > t).mean()
        far_tot = (tot[~atk_min] > t[~atk_min]).mean() if (~atk_min).any() else np.nan
        det = (tot[atk_min] > t[atk_min]).mean() if atk_min.any() else np.nan
        rows.append({"Org": org, "Ambang": name, "FAR_benign_%": 100 * far,
                     "FAR_nominal_%": 100 * ALPHA_ALARM, "Rasio_FAR/nominal": far / ALPHA_ALARM,
                     "Alarm_palsu_per_hari": far * 1440,
                     "FAR_menit_tanpa_serangan_%": 100 * far_tot,
                     "n_menit_serangan_fase2": int(atk_min.sum()),
                     "Detection_rate_%": 100 * det if det == det else np.nan})
    return rows


def core_metrics(org, scen, times, start, end, cfg):
    s = minute_counts(times, start, end)
    D, _ = dispersion(s)
    _, _, cv = ks_cv(interarrival(times, 0), cfg["ks_sample"], 0)
    m, meta = fit_models(s, cfg["phase1_frac"])
    best = min(m, key=lambda k: m[k]["AIC"])
    return dict(Org=org, Skenario=scen, n_request=len(times), rata2_per_menit=s.mean(),
                D_1menit=D, CV_jeda=cv, r_NB=meta["r"], model_terbaik_AIC=best,
                AIC_NB_pct_Poisson=100 * m["Binomial negatif"]["AIC"] / m["Poisson homogen"]["AIC"])


# =============================================================================
# 5. MAIN
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default="hasil_revisi")
    ap.add_argument("--only-parse", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    os.makedirs(args.out, exist_ok=True)

    data = {}
    for org, oc in cfg["orgs"].items():
        cache = os.path.join(args.out, f"cache_{org}.pkl")
        print(f"\n=== Parsing {org} ===")
        if os.path.exists(cache) and not args.no_cache:
            df = pd.read_pickle(cache); print(f"   dari cache: {len(df):,} baris")
        else:
            df = parse_files(oc["paths"], oc.get("vhost_from", "none"))
            df["time"] = df["time"].dt.tz_convert(oc["tz"])
            if oc.get("start"):
                df = df[df["time"] >= pd.Timestamp(oc["start"], tz=oc["tz"])]
            if oc.get("end"):
                df = df[df["time"] < pd.Timestamp(oc["end"], tz=oc["tz"])]
            rp = oc.get("rules_path", cfg.get("rules_path"))
            if rp and oc.get("label", True):
                df, st = apply_rules(df, load_rules(rp, cfg.get("percent_mode", "auto"),
                                                    cfg.get("legacy_regex", False)),
                                     cfg["strict_modes"], cfg.get("strip_quotes", True))
                st.to_csv(os.path.join(args.out, f"label_per_rule_{org}.csv"), index=False)
            else:
                df["atk_strict"] = False; df["atk_moderate"] = False; df["atk_any"] = False; df["gt_label"] = ""
            df = df.drop(columns=["line", "request", "referer"], errors="ignore")
            df = df.sort_values("time").reset_index(drop=True)
            df.to_pickle(cache)
        print(f"   {org}: {len(df):,} request | {df['time'].min()} s.d. {df['time'].max()}")
        print(f"   ditandai serangan: strict {df['atk_strict'].mean():.2%}, moderate {df['atk_moderate'].mean():.2%}, "
              f"gabungan {df['atk_any'].mean():.2%}")
        nb = int((~df["atk_any"]).sum())
        if oc.get("expected_total"):
            print(f"   CEK: total  = {len(df):,} | naskah = {oc['expected_total']:,}")
        if oc.get("expected_benign"):
            print(f"   CEK: benign = {nb:,} | naskah/pipeline lama = {oc['expected_benign']:,} "
                  f"(selisih {100 * (nb - oc['expected_benign']) / oc['expected_benign']:+.2f}%)")
        if "vhost" in df and df["vhost"].nunique() > 1:
            print(f"   virtual host: {df['vhost'].nunique()} -> {sorted(df['vhost'].unique())[:6]} ...")
        data[org] = df
    if args.only_parse:
        return

    T = {k: [] for k in ["t1", "t2", "t2b", "t3", "t3b", "t4", "t5"]}
    for org, df in data.items():
        oc = cfg["orgs"][org]
        # rentang = menit request pertama s.d. menit request terakhir (sama dengan naskah);
        # JANGAN dibulatkan ke hari penuh karena menambah menit nol palsu di awal/akhir.
        start = df["time"].min().floor("1min"); end = df["time"].max().floor("1min") + pd.Timedelta(minutes=1)
        is_nasa = org.upper().startswith("NASA")
        benign = df if is_nasa else df[~df["atk_any"]]
        s1 = minute_counts(benign["time"], start, end)
        print(f"\n=== Analisis {org} ({'semua request' if is_nasa else 'benign'}: {len(benign):,}) ===")

        print("   isu 1: autokorelasi ...")
        row = issue1_autocorr(org, s1, cfg, args.out)
        _, meta = fit_models(s1, cfg["phase1_frac"]); row["r_NB_hour"] = meta["r"]
        T["t1"].append(row)

        print("   isu 2: uji bebas jitter ...")
        r2, fits = issue2_jitter(org, benign["time"], cfg)
        T["t2"].append(r2); T["t2b"] += fits

        if oc.get("vhost_from") == "filename":
            print("   isu 3: non-stasioneritas & virtual host ...")
            rows, per = issue3_nonstationary(benign, s1, cfg, args.out)
            for r in rows: r["Org"] = org
            T["t3"] += rows; T["t3b"] += [dict(Org=org, **p) for p in per]

        if not is_nasa:
            print("   isu 4: false alarm & detection ...")
            atk = minute_counts(df.loc[df["atk_any"], "time"], start, end)
            T["t4"] += issue4_false_alarm(org, s1, atk, cfg)

        print("   isu 5: sensitivitas pelabelan ...")
        scen = [("A. Tanpa penghapusan", df["time"]),
                ("B. Hapus rule strict saja", df.loc[~df["atk_strict"], "time"]),
                ("C. Hapus rule moderate saja", df.loc[~df["atk_moderate"], "time"]),
                ("D. Hapus strict + moderate (naskah)", df.loc[~df["atk_any"], "time"])]
        for name, t in scen:
            r = core_metrics(org, name, t, start, end, cfg)
            r["persen_dihapus"] = 100 * (1 - len(t) / len(df))
            T["t5"].append(r)

    names = {"t1": "isu1_autokorelasi", "t2": "isu2_uji_bebas_jitter", "t2b": "isu2_distribusi_alternatif",
             "t3": "isu3_periode_stabil_Y", "t3b": "isu3_per_vhost_Y", "t4": "isu4_false_alarm",
             "t5": "isu5_sensitivitas_label"}
    md = ["# Hasil analisis revisi\n"]
    for k, v in T.items():
        if not v:
            continue
        d = pd.DataFrame(v)
        d.to_csv(os.path.join(args.out, names[k] + ".csv"), index=False)
        md += [f"\n## {names[k]}\n", d.to_markdown(index=False, floatfmt=".4g"), "\n"]
        if k == "t3b":
            md.append(f"\nRingkasan per vhost: median D = {d['D'].median():.3g}, "
                      f"median r = {d['r'].median():.3g}, IQR r = [{d['r'].quantile(.25):.3g}, {d['r'].quantile(.75):.3g}]\n")
    with open(os.path.join(args.out, "ringkasan_hasil.md"), "w", encoding="utf8") as f:
        f.write("\n".join(md))
    print(f"\nSelesai. Lihat folder '{args.out}': CSV per isu, ringkasan_hasil.md, acf_*.png, changepoint_Y.png")


if __name__ == "__main__":
    main()
