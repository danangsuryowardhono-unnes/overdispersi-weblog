#!/usr/bin/env python3
"""
Analisis tambahan untuk revisi naskah JUSTINDO
"Overdispersi Kedatangan Request pada Log Web Server Sektor Publik 2025 dan Perbandingannya dengan NASA 1995".

Skrip ini mengisi bagian bertanda PENULIS pada naskah revisi:
  - IK 95% block bootstrap indeks dispersi D untuk panjang blok 30, 60, 120 menit   (Tabel 8)
  - IK 95% profil likelihood untuk parameter dispersi r                              (Bagian 3.4, 3.5, Tabel 12)
  - Uji terkondisi per jam: n, chi-square, D, p, Bonferroni; strata hari kerja/akhir pekan (Lampiran B, Tabel B1)
  - Regresi NB dengan lag (koefisien + SE), INGARCH(1,1) binomial negatif dengan efek jam (Tabel 12)
  - Diagnostik residual Pearson: ACF, Ljung-Box, plot residual vs waktu & vs nilai prediksi (Tabel 12, Gambar B1-B2)
  - Log-score per observasi fase II dan evaluasi rolling-origin (Tabel 6, Tabel 12)
  - Metrik monitoring: confusion matrix, FAR, detection rate (IK Wilson), precision, recall, F1,
    pada beberapa target FAR, ambang kuantil dan mu + 3 sqrt(mu)                     (Tabel 10, Tabel B2)

INPUT  : CSV per log dengan satu baris per menit (bin 1 menit, bin kosong = 0), kolom:
           minute  : timestamp awal bin dalam waktu lokal (WIB untuk X dan Y; waktu server untuk NASA)
           benign  : jumlah request yang lolos filtering
           attack  : (opsional) jumlah request berlabel serangan pada menit tersebut
OUTPUT : folder berisi CSV, PNG, dan ringkasan.md

Contoh:
  python3 analisis_tambahan_revisi.py --input orgX_per_menit.csv --name "Org X" --outdir hasil_X
  python3 analisis_tambahan_revisi.py --demo --outdir hasil_demo     # uji dengan data sintetis

Dependensi: numpy, pandas, scipy, matplotlib
"""
import argparse, json, math, os, sys, warnings
import numpy as np
import pandas as pd
from scipy import stats, optimize, special, signal

warnings.filterwarnings("ignore", category=RuntimeWarning)
RNG = np.random.default_rng(20261113)
SPLIT = 0.60
FAR_TARGETS = [0.0005, 0.00135, 0.005, 0.01]


# ----------------------------------------------------------------------------- utilitas
def dispersion(x):
    x = np.asarray(x, float)
    return x.var(ddof=1) / x.mean()


def wilson(k, n, z=1.959964):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def acf(x, nlags):
    x = np.asarray(x, float) - np.mean(x)
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    a = np.fft.irfft(f * np.conj(f))[: nlags + 1]
    return a / a[0]


def ljung_box(x, lag):
    n = len(x)
    r = acf(x, lag)[1:]
    qstat = n * (n + 2) * np.sum(r ** 2 / (n - np.arange(1, lag + 1)))
    return qstat, stats.chi2.sf(qstat, lag)


def nb_logpmf(y, mu, r):
    """NB2: mean mu, size r, Var = mu + mu^2 / r (sama dengan scipy nbinom(n=r, p=r/(r+mu)))."""
    return (special.gammaln(y + r) - special.gammaln(r) - special.gammaln(y + 1)
            + r * np.log(r / (r + mu)) + y * np.log(mu / (r + mu)))


# ----------------------------------------------------------------------------- 1. block bootstrap D
def block_bootstrap_D(x, L, B=1000):
    x = np.asarray(x, float)
    n = len(x)
    nb = int(np.ceil(n / L))
    starts = RNG.integers(0, n - L + 1, size=(B, nb))
    idx = (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(B, -1)[:, :n]
    xs = x[idx]
    Ds = xs.var(axis=1, ddof=1) / xs.mean(axis=1)
    return np.percentile(Ds, [2.5, 97.5])


# ----------------------------------------------------------------------------- 2. NB dengan rata-rata per jam
def fit_nb_hourly(y, hour):
    y = np.asarray(y, float)
    mu_h = pd.Series(y).groupby(hour).mean().reindex(range(24)).fillna(y.mean()).values
    mu_h = np.maximum(mu_h, 1e-9)
    mu = mu_h[hour]

    def ll(logr):
        return np.sum(nb_logpmf(y, mu, np.exp(logr)))

    res = optimize.minimize_scalar(lambda a: -ll(a), bounds=(-8, 12), method="bounded",
                                   options={"xatol": 1e-8})
    logr = res.x
    llmax = -res.fun
    # konvergensi: gradien numerik di optimum
    h = 1e-4
    grad = (ll(logr + h) - ll(logr - h)) / (2 * h)
    # IK profil 95%
    crit = stats.chi2.ppf(0.95, 1) / 2
    f = lambda a: llmax - ll(a) - crit
    try:
        lo = optimize.brentq(f, logr - 10, logr)
    except ValueError:
        lo = np.nan
    try:
        hi = optimize.brentq(f, logr, logr + 10)
    except ValueError:
        hi = np.nan
    return dict(mu_h=mu_h, r=float(np.exp(logr)), r_lo=float(np.exp(lo)), r_hi=float(np.exp(hi)),
                ll=float(llmax), grad_at_opt=float(grad), converged=bool(res.success))


# ----------------------------------------------------------------------------- 3. uji per jam
def chisq_poisson(x):
    x = np.asarray(x, int)
    lam = x.mean()
    kmax = x.max()
    ks = np.arange(kmax + 1)
    obs = np.bincount(x, minlength=kmax + 1).astype(float)
    exp = stats.poisson.pmf(ks, lam) * len(x)
    exp[-1] += stats.poisson.sf(kmax, lam) * len(x)
    # gabungkan kelas pada kedua ekor hingga E >= 5
    O, Ex = list(obs), list(exp)
    while len(Ex) > 2 and Ex[0] < 5:
        Ex[1] += Ex[0]; O[1] += O[0]; Ex.pop(0); O.pop(0)
    while len(Ex) > 2 and Ex[-1] < 5:
        Ex[-2] += Ex[-1]; O[-2] += O[-1]; Ex.pop(); O.pop()
    O, Ex = np.array(O), np.array(Ex)
    chi2 = np.sum((O - Ex) ** 2 / Ex)
    df = max(len(Ex) - 2, 1)
    return chi2, df, stats.chi2.sf(chi2, df)


def per_hour_table(df, interval, alpha=0.05):
    rows = []
    for stratum, sub in [("semua", df), ("hari kerja", df[~df.weekend]), ("akhir pekan", df[df.weekend])]:
        s = sub.resample(f"{interval}min").sum() if interval > 1 else sub
        if interval > 1:
            s["hour"] = s.index.hour
            s["weekend"] = s.index.dayofweek >= 5
            if stratum == "hari kerja":
                s = s[~s.weekend]
            elif stratum == "akhir pekan":
                s = s[s.weekend]
        for h in range(24):
            x = s.loc[s.hour == h, "benign"].values
            if len(x) < 10 or x.mean() == 0:
                continue
            chi2, dfree, p = chisq_poisson(x)
            D = dispersion(x)
            pD = stats.chi2.sf((len(x) - 1) * D, len(x) - 1)
            rows.append(dict(strata=stratum, interval_menit=interval, jam=h, n=len(x), rata2=x.mean(),
                             D=D, chi2=chi2, df=dfree, p_chi2=p, p_dispersi=pD,
                             tolak_bonferroni=bool(p < alpha / 24), overdispersi_bonferroni=bool(pD < alpha / 24)))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- 4a. regresi NB dengan lag
def nb_lag_design(y, hour):
    y = np.asarray(y, float)
    l1 = np.r_[np.nan, y[:-1]]
    l60 = np.r_[np.full(60, np.nan), y[:-60]]
    X = np.column_stack([np.log1p(l1), np.log1p(l60)])
    ok = ~np.isnan(X).any(axis=1)
    return X, ok


def fit_nb_lag(y, hour, X, ok):
    y = np.asarray(y, float)[ok]; hour = hour[ok]; X = X[ok]
    H = np.eye(24)[hour]
    a0 = np.log(np.maximum(pd.Series(y).groupby(hour).mean().reindex(range(24)).fillna(y.mean()).values, 1e-3))
    theta0 = np.r_[a0, 0.0, 0.0, 0.0]

    def nll(th):
        eta = H @ th[:24] + X @ th[24:26]
        mu = np.exp(np.clip(eta, -20, 20))
        return -np.sum(nb_logpmf(y, mu, np.exp(th[26])))

    res = optimize.minimize(nll, theta0, method="BFGS", options={"maxiter": 2000, "gtol": 1e-4})
    se = np.sqrt(np.clip(np.diag(res.hess_inv), 0, None))
    return dict(theta=res.x, se=se, r=float(np.exp(res.x[26])), b1=res.x[24], b2=res.x[25],
                se_b1=se[24], se_b2=se[25], converged=bool(res.success), nll=res.fun)


def predict_nb_lag(fit, hour, X):
    H = np.eye(24)[hour]
    return np.exp(H @ fit["theta"][:24] + X @ fit["theta"][24:26])


# ----------------------------------------------------------------------------- 4b. INGARCH(1,1) NB dengan efek jam
def ingarch_mu(theta, y, hour):
    omega = np.exp(theta[:24])[hour]
    a = special.expit(theta[24]); b = (1 - a) * special.expit(theta[25])  # a + b < 1
    y_prev = np.r_[y.mean(), y[:-1]]
    u = omega + a * y_prev
    zi = signal.lfiltic([1.0], [1.0, -b], [y.mean()])
    lam, _ = signal.lfilter([1.0], [1.0, -b], u, zi=zi)
    return np.maximum(lam, 1e-9), a, b


def fit_ingarch(y, hour):
    y = np.asarray(y, float)
    m_h = pd.Series(y).groupby(hour).mean().reindex(range(24)).fillna(y.mean()).values
    theta0 = np.r_[np.log(np.maximum(m_h * 0.3, 1e-3)), special.logit(0.4), special.logit(0.5), 0.0]

    def nll(th):
        mu, _, _ = ingarch_mu(th, y, hour)
        return -np.sum(nb_logpmf(y, mu, np.exp(th[26])))

    res = optimize.minimize(nll, theta0, method="L-BFGS-B", options={"maxiter": 3000})
    _, a, b = ingarch_mu(res.x, y, hour)
    return dict(theta=res.x, r=float(np.exp(res.x[26])), a=float(a), b=float(b), converged=bool(res.success))


# ----------------------------------------------------------------------------- 5. log-score & rolling-origin
def fit_all(y_tr, h_tr, with_dynamic=True):
    lam = y_tr.mean()
    mu_h = pd.Series(y_tr).groupby(h_tr).mean().reindex(range(24)).fillna(lam).values
    nb = fit_nb_hourly(y_tr, h_tr)
    out = dict(lam=lam, mu_h=np.maximum(mu_h, 1e-9), nb=nb)
    if with_dynamic:
        X, ok = nb_lag_design(y_tr, h_tr)
        out["nblag"] = fit_nb_lag(y_tr, h_tr, X, ok)
        out["ingarch"] = fit_ingarch(y_tr, h_tr)
    return out


def logscores(fits, y_all, h_all, start, end, with_dynamic=True):
    """LS rata-rata per observasi pada indeks [start, end). Model dinamis memakai observasi lalu (one-step-ahead)."""
    y = y_all[start:end].astype(float); h = h_all[start:end]
    res = {}
    res["Poisson homogen"] = np.mean(stats.poisson.logpmf(y, fits["lam"]))
    res["NHPP per jam"] = np.mean(stats.poisson.logpmf(y, fits["mu_h"][h]))
    res["Binomial negatif"] = np.mean(nb_logpmf(y, fits["nb"]["mu_h"][h], fits["nb"]["r"]))
    mus = {"Poisson homogen": np.full(len(y), fits["lam"]), "NHPP per jam": fits["mu_h"][h],
           "Binomial negatif": fits["nb"]["mu_h"][h]}
    if with_dynamic:
        X, ok = nb_lag_design(y_all, h_all)
        Xs, oks = X[start:end], ok[start:end]
        mu_l = predict_nb_lag(fits["nblag"], h, np.nan_to_num(Xs))
        res["NB + lag"] = np.mean(nb_logpmf(y[oks], mu_l[oks], fits["nblag"]["r"]))
        mu_g, _, _ = ingarch_mu(fits["ingarch"]["theta"], y_all[:end].astype(float), h_all[:end])
        mu_g = mu_g[start:end]
        res["INGARCH(1,1)-NB"] = np.mean(nb_logpmf(y, mu_g, fits["ingarch"]["r"]))
        mus["NB + lag"] = mu_l; mus["INGARCH(1,1)-NB"] = mu_g
    return res, mus


# ----------------------------------------------------------------------------- 6. monitoring
def monitoring(fits, df2, phase2_mask):
    y_b = df2.benign.values[phase2_mask].astype(float)
    y_a = df2.attack.values[phase2_mask].astype(float) if "attack" in df2 else np.zeros_like(y_b)
    h = df2.hour.values[phase2_mask]
    attack_min = y_a >= 10
    total = y_b + y_a
    rows = []
    specs = {
        "Poisson homogen": lambda a: stats.poisson.isf(a, np.full(len(h), fits["lam"])),
        "NHPP per jam": lambda a: stats.poisson.isf(a, fits["mu_h"][h]),
        "Binomial negatif": lambda a: stats.nbinom.isf(a, fits["nb"]["r"],
                                                       fits["nb"]["r"] / (fits["nb"]["r"] + fits["nb"]["mu_h"][h])),
    }
    for name, fn in specs.items():
        for a in FAR_TARGETS:
            c = fn(a)
            rows.append(_metrics(name, "kuantil", a, c, y_b, total, attack_min))
    for name, mu in [("Poisson homogen", np.full(len(h), fits["lam"])), ("NHPP per jam", fits["mu_h"][h])]:
        c = mu + 3 * np.sqrt(mu)  # alarm jika N > mu + 3 sqrt(mu)
        rows.append(_metrics(name, "mu+3sqrt(mu)", 0.00135, c, y_b, total, attack_min))
    return pd.DataFrame(rows)


def _metrics(model, metode, alpha, c, y_b, total, attack_min):
    n = len(y_b)
    fa = int(np.sum(y_b > c))                          # FAR pada deret benign (definisi naskah)
    far_lo, far_hi = wilson(fa, n)
    alarm = total > c
    tp = int(np.sum(alarm & attack_min)); fn_ = int(np.sum(~alarm & attack_min))
    fp = int(np.sum(alarm & ~attack_min)); tn = int(np.sum(~alarm & ~attack_min))
    na = tp + fn_
    dr_lo, dr_hi = wilson(tp, na) if na else (np.nan, np.nan)
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / na if na else np.nan
    f1 = 2 * prec * rec / (prec + rec) if prec and rec and not np.isnan(prec) else np.nan
    return dict(model=model, metode=metode, target_FAR=alpha, menit_fase2=n, alarm_palsu_benign=fa,
                FAR=fa / n, FAR_lo=far_lo, FAR_hi=far_hi, rasio_nominal=(fa / n) / alpha,
                alarm_palsu_per_hari=fa / n * 1440, menit_serangan=na, TP=tp, FN=fn_, FP=fp, TN=tn,
                detection_rate=rec, DR_lo=dr_lo, DR_hi=dr_hi, precision=prec, recall=rec, F1=f1)


# ----------------------------------------------------------------------------- 7. plot residual
def residual_plots(outdir, name, idx, y, mus, r_map):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    fig, axes = plt.subplots(len(mus), 3, figsize=(13, 2.8 * len(mus)), squeeze=False)
    for i, (m, mu) in enumerate(mus.items()):
        r = r_map.get(m)
        var = mu + mu ** 2 / r if r else mu
        res = (y - mu) / np.sqrt(var)
        ok = np.isfinite(res)
        rr = res[ok]
        a = acf(rr, 120)
        q60, p60 = ljung_box(rr, 60)
        rows.append(dict(model=m, acf_lag1_resid=a[1], LB60=q60, p_LB60=p60))
        axes[i, 0].bar(range(1, 121), a[1:], width=1.0, color="#4C72B0")
        axes[i, 0].axhline(1.96 / np.sqrt(len(rr)), ls="--", c="grey", lw=.8)
        axes[i, 0].axhline(-1.96 / np.sqrt(len(rr)), ls="--", c="grey", lw=.8)
        axes[i, 0].set_title(f"{m}: ACF residual Pearson", fontsize=9); axes[i, 0].set_xlabel("lag (menit)")
        axes[i, 1].plot(np.asarray(idx)[ok], rr, lw=.3, c="#4C72B0"); axes[i, 1].set_title("residual vs waktu", fontsize=9)
        axes[i, 2].scatter(mu[ok], rr, s=1, alpha=.3, c="#4C72B0"); axes[i, 2].set_xscale("log")
        axes[i, 2].set_title("residual vs nilai prediksi", fontsize=9); axes[i, 2].set_xlabel("μ prediksi")
    fig.suptitle(f"Diagnostik residual fase II — {name}", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "gambar_B_residual.png"), dpi=200)
    plt.close(fig)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- main
def run(df, name, outdir, dynamic=True):
    os.makedirs(outdir, exist_ok=True)
    df = df.copy()
    df["minute"] = pd.to_datetime(df["minute"])
    df = df.set_index("minute").sort_index()
    full = pd.date_range(df.index.min().floor("min"), df.index.max().floor("min"), freq="min")
    df = df.reindex(full, fill_value=0)
    if "attack" not in df:
        df["attack"] = 0
    df["hour"] = df.index.hour
    df["weekend"] = df.index.dayofweek >= 5
    y = df.benign.values.astype(int); hr = df.hour.values
    n = len(y); n1 = int(np.floor(SPLIT * n))
    out = {"nama": name, "n_menit": n, "n_fase1": n1, "n_fase2": n - n1}

    # 1. block bootstrap
    out["D_1menit"] = dispersion(y)
    out["D_block_IK95"] = {L: block_bootstrap_D(y, L).round(3).tolist() for L in (30, 60, 120)}
    th = y[::120]
    out["D_dijarangkan_120"] = dict(n=len(th), D=dispersion(th),
                                    p=float(stats.chi2.sf((len(th) - 1) * dispersion(th), len(th) - 1)))
    a = acf(y, 240)
    out["ACF_lag1"] = a[1]
    out["lag_pertama_ACF_bawah_0.1"] = int(np.argmax(a[1:] < 0.1) + 1) if np.any(a[1:] < 0.1) else None

    # 2-3. uji per jam
    tabs = [per_hour_table(df[["benign", "hour", "weekend"]], iv) for iv in (1, 5, 10)]
    ph = pd.concat(tabs, ignore_index=True)
    ph.to_csv(os.path.join(outdir, "tabel_B1_uji_per_jam.csv"), index=False)
    out["ringkasan_per_jam"] = (ph.groupby(["strata", "interval_menit"])
                                .agg(jam=("jam", "count"), tolak=("tolak_bonferroni", "sum"),
                                     overdispersi=("overdispersi_bonferroni", "sum"), median_D=("D", "median"))
                                .reset_index().to_dict("records"))

    # 4-5. model fase I, log-score fase II
    fits = fit_all(y[:n1], hr[:n1], dynamic)
    out["NB_r_fase1"] = dict(r=fits["nb"]["r"], IK95=[fits["nb"]["r_lo"], fits["nb"]["r_hi"]],
                             gradien_di_optimum=fits["nb"]["grad_at_opt"], konvergen=fits["nb"]["converged"])
    if dynamic:
        f = fits["nblag"]
        out["NB_lag"] = dict(b1=f["b1"], se_b1=f["se_b1"], b2=f["b2"], se_b2=f["se_b2"], r=f["r"], konvergen=f["converged"])
        g = fits["ingarch"]
        out["INGARCH"] = dict(a=g["a"], b=g["b"], r=g["r"], konvergen=g["converged"])
    ls, mus = logscores(fits, y, hr, n1, n, dynamic)
    out["logscore_fase2_per_obs"] = ls

    # 6. residual
    r_map = {"Binomial negatif": fits["nb"]["r"]}
    if dynamic:
        r_map["NB + lag"] = fits["nblag"]["r"]; r_map["INGARCH(1,1)-NB"] = fits["ingarch"]["r"]
    sel = {k: v for k, v in mus.items() if k in r_map}
    rd = residual_plots(outdir, name, df.index[n1:], y[n1:].astype(float), sel, r_map)
    rd.to_csv(os.path.join(outdir, "diagnostik_residual.csv"), index=False)
    out["diagnostik_residual"] = rd.to_dict("records")

    # 7. rolling-origin
    ro = []
    for frac in (0.5, 0.6, 0.7, 0.8):
        o = int(frac * n); e = min(o + 1440, n)
        if e - o < 60:
            continue
        ft = fit_all(y[:o], hr[:o], dynamic)
        s, _ = logscores(ft, y, hr, o, e, dynamic)
        s["titik_asal"] = frac
        ro.append(s)
    ro = pd.DataFrame(ro)
    ro.to_csv(os.path.join(outdir, "rolling_origin.csv"), index=False)
    models = [c for c in ro.columns if c != "titik_asal"]
    out["rolling_origin_rata2"] = ro[models].mean().to_dict()
    out["rolling_origin_menang"] = ro[models].idxmax(axis=1).value_counts().to_dict()

    # 8. monitoring
    mask = np.zeros(n, bool); mask[n1:] = True
    mon = monitoring(fits, df, mask)
    mon.to_csv(os.path.join(outdir, "tabel_B2_monitoring.csv"), index=False)
    out["monitoring_0.135%"] = mon[mon.target_FAR == 0.00135].round(5).to_dict("records")

    with open(os.path.join(outdir, "ringkasan.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    write_md(out, outdir)
    return out


def write_md(o, outdir):
    L = [f"# Ringkasan analisis tambahan — {o['nama']}", "",
         f"Menit dianalisis: {o['n_menit']} (fase I {o['n_fase1']}, fase II {o['n_fase2']})", "",
         f"D 1 menit = {o['D_1menit']:.2f}; ACF lag 1 = {o['ACF_lag1']:.3f}; lag pertama ACF < 0,1 = {o['lag_pertama_ACF_bawah_0.1']}", ""]
    for Lb, ci in o["D_block_IK95"].items():
        L.append(f"- IK 95% block bootstrap, blok {Lb} menit: {ci[0]:.2f}–{ci[1]:.2f}")
    t = o["D_dijarangkan_120"]
    L += [f"- Deret dijarangkan 120 menit: n = {t['n']}, D = {t['D']:.2f}, p = {t['p']:.2e}", ""]
    r = o["NB_r_fase1"]
    L += [f"r NB (fase I) = {r['r']:.3f}, IK 95% profil {r['IK95'][0]:.3f}–{r['IK95'][1]:.3f}; gradien di optimum {r['gradien_di_optimum']:.2e}", ""]
    if "NB_lag" in o:
        b = o["NB_lag"]
        L.append(f"NB + lag: β1 = {b['b1']:.3f} (SE {b['se_b1']:.3f}), β2 = {b['b2']:.3f} (SE {b['se_b2']:.3f}), r = {b['r']:.2f}")
        g = o["INGARCH"]
        L.append(f"INGARCH(1,1)-NB: a = {g['a']:.3f}, b = {g['b']:.3f}, r = {g['r']:.2f}")
        L.append("")
    L.append("Log-score fase II per observasi:")
    for k, v in o["logscore_fase2_per_obs"].items():
        L.append(f"- {k}: {v:.3f}")
    L += ["", "Rolling-origin (rata-rata LS):"]
    for k, v in o["rolling_origin_rata2"].items():
        L.append(f"- {k}: {v:.3f}")
    L.append(f"Model terbaik per titik asal: {o['rolling_origin_menang']}")
    L += ["", "Diagnostik residual (fase II):"]
    for d in o["diagnostik_residual"]:
        L.append(f"- {d['model']}: ACF lag1 = {d['acf_lag1_resid']:.3f}, Ljung–Box(60) p = {d['p_LB60']:.2e}")
    L += ["", "Ringkasan uji per jam (Bonferroni α = 0,05/24):"]
    for d in o["ringkasan_per_jam"]:
        L.append(f"- {d['strata']}, {d['interval_menit']} menit: tolak {d['tolak']}/{d['jam']}, "
                 f"overdispersi {d['overdispersi']}/{d['jam']}, median D {d['median_D']:.1f}")
    L += ["", "Monitoring pada target FAR 0,135%: lihat tabel_B2_monitoring.csv"]
    with open(os.path.join(outdir, "ringkasan.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def demo_data(days=10):
    n = days * 1440
    t = pd.date_range("2025-09-23", periods=n, freq="min")
    h = t.hour.values
    base = 4 + 10 * np.clip(np.sin((h - 6) / 24 * 2 * np.pi), 0, None)
    z = np.zeros(n)
    for i in range(1, n):
        z[i] = 0.8 * z[i - 1] + RNG.normal(0, 0.5)
    mu = base * np.exp(z - 0.5 * z.var())
    y = RNG.negative_binomial(3, 3 / (3 + mu))
    att = np.zeros(n, int)
    for s in RNG.integers(0, n - 30, 12):
        att[s:s + RNG.integers(1, 20)] = RNG.integers(10, 80)
    return pd.DataFrame({"minute": t, "benign": y, "attack": att})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input"); ap.add_argument("--name", default="log")
    ap.add_argument("--outdir", default="hasil"); ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-dynamic", action="store_true", help="lewati NB+lag dan INGARCH (lebih cepat)")
    a = ap.parse_args()
    if a.demo:
        d = demo_data(); a.name = "data sintetis"
    elif a.input:
        d = pd.read_csv(a.input)
    else:
        ap.error("gunakan --input FILE atau --demo")
    run(d, a.name, a.outdir, dynamic=not a.no_dynamic)
    print(open(os.path.join(a.outdir, "ringkasan.md"), encoding="utf-8").read().encode(sys.stdout.encoding or "utf-8", "replace").decode(sys.stdout.encoding or "utf-8"))
