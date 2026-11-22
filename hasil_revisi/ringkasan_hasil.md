# Hasil analisis revisi


## isu1_autokorelasi

| Org   |   ACF_lag1 |   ACF_lag60 |   LjungBox_p_lag60 |      D |   p_D |   D_CI95_lo |   D_CI95_hi |   thinning_k |   n_thinned |   D_thinned |   p_D_thinned |   r_NB_hour |   r_NB_hour_lag |
|:------|-----------:|------------:|-------------------:|-------:|------:|------------:|------------:|-------------:|------------:|------------:|--------------:|------------:|----------------:|
| X     |     0.3762 |      0.1954 |                  0 |  17.51 |     0 |       16.23 |       18.81 |          120 |         171 |       18.4  |             0 |       1.324 |           1.504 |
| Y     |     0.8172 |      0.3387 |                  0 | 139.3  |     0 |      109.6  |      171    |          120 |         220 |      196.1  |             0 |       1.014 |           6.462 |
| NASA  |     0.842  |      0.6902 |                  0 |  22.01 |     0 |       18.97 |       25.28 |          120 |         331 |       21.63 |             0 |       3.801 |           8.689 |



## isu2_uji_bebas_jitter

| Org   |   lambda_per_detik |   D_per_detik |   p_D_per_detik |   D_per_detik_terkondisi_jam |   prop_detik_kosong_obs |   prop_detik_kosong_Poisson |   z_detik_kosong |   chi2_run_kosong_vs_geom |   p_run |   KS_min |   KS_max |   CV_min |   CV_max |
|:------|-------------------:|--------------:|----------------:|-----------------------------:|------------------------:|----------------------------:|-----------------:|--------------------------:|--------:|---------:|---------:|---------:|---------:|
| X     |             0.1647 |         5.681 |               0 |                        5.65  |                  0.9278 |                      0.8481 |            245.7 |                 2.557e+06 |       0 |   0.4921 |   0.4941 |    2.271 |    2.275 |
| Y     |             1.42   |         5.855 |               0 |                        5.835 |                  0.5763 |                      0.2417 |            982.8 |                 2.496e+08 |       0 |   0.3156 |   0.3241 |    3.899 |    4.079 |
| NASA  |             0.7943 |         1.642 |               0 |                        1.517 |                  0.5382 |                      0.4519 |            267.6 |                 6.779e+06 |       0 |   0.1234 |   0.13   |    1.778 |    3.227 |



## isu2_distribusi_alternatif

| Org   | Distribusi   |       AIC |      KS | Parameter         |
|:------|:-------------|----------:|--------:|:------------------|
| X     | Eksponensial | 1.122e+06 | 0.4929  | 0, 6.076          |
| X     | Weibull      | 6.857e+05 | 0.1029  | 0.4135, 0, 1.776  |
| X     | Lognormal    | 6.583e+05 | 0.04258 | 2.508, 0, 0.5003  |
| X     | Gamma        | 7.246e+05 | 0.1786  | 0.2794, 0, 21.75  |
| Y     | Eksponensial | 2.658e+05 | 0.3228  | 0, 0.7151         |
| Y     | Weibull      | 6.849e+04 | 0.07643 | 0.5735, 0, 0.3606 |
| Y     | Lognormal    | 3.687e+04 | 0.02816 | 1.731, 0, 0.1533  |
| Y     | Gamma        | 1.211e+05 | 0.1578  | 0.4234, 0, 1.689  |
| NASA  | Eksponensial | 4.944e+05 | 0.1279  | 0, 1.266          |
| NASA  | Weibull      | 4.595e+05 | 0.03316 | 0.7559, 0, 1.042  |
| NASA  | Lognormal    | 4.619e+05 | 0.04157 | 1.492, 0, 0.5148  |
| NASA  | Gamma        | 4.704e+05 | 0.06301 | 0.675, 0, 1.876   |



## isu3_periode_stabil_Y

| Periode                                     |   n_menit |   rata2 |     D |     r |   AIC_NB_pct_Poisson | terbaik_in_sample   | terbaik_out_of_sample   |   ll2_Poisson |    ll2_NHPP |      ll2_NB | Org   |   r_tanpa_offset |   AIC_NB_offset |   AIC_NB_tanpa_offset |
|:--------------------------------------------|----------:|--------:|------:|------:|---------------------:|:--------------------|:------------------------|--------------:|------------:|------------:|:------|-----------------:|----------------:|----------------------:|
| Periode penuh                               |     26362 |    85.2 | 139.3 | 1.014 |                9.696 | Binomial negatif    | Binomial negatif        |    -2.325e+05 |  -2.422e+05 |  -5.763e+04 | Y     |          nan     |     nan         |           nan         |
| Periode stabil (>= 2025-04-19)              |     17722 |   110.4 | 131.4 | 1.845 |               11.36  | Binomial negatif    | Binomial negatif        |    -2.134e+05 |  -2.158e+05 |  -3.812e+04 | Y     |          nan     |     nan         |           nan         |
| Periode penuh, NB + offset log(vhost aktif) |     26362 |   nan   | nan   | 1.753 |              nan     | nan                 | nan                     |   nan         | nan         | nan         | Y     |            1.366 |       2.779e+05 |             2.857e+05 |



## isu3_per_vhost_Y

| Org   | vhost                     |   n_request |   rata2_per_menit |      D |      r |
|:------|:--------------------------|------------:|------------------:|-------:|-------:|
| Y     | lab-sub3.sub9.domain1.com |       48588 |             2.742 |  30.02 | 2.46   |
| Y     | sub1.domain1.com          |      347871 |            19.69  | 135.1  | 0.4485 |
| Y     | sub14.domain1.com         |       71708 |             4.316 |  88.98 | 1.175  |
| Y     | sub15.domain1.com         |       88643 |             5.002 | 146    | 1.244  |
| Y     | sub16.domain1.com         |       73024 |             4.121 |  57.1  | 1.346  |
| Y     | sub17.domain1.com         |      137266 |             8.494 |  67.6  | 0.7839 |
| Y     | sub18.domain1.com         |       60586 |             3.419 |  35.85 | 1.879  |
| Y     | sub19.domain1.com         |       57925 |             3.269 |  44.62 | 1.612  |
| Y     | sub20.domain1.com         |       91495 |             5.163 |  36.13 | 1.523  |
| Y     | sub21.domain1.com         |       77940 |             4.398 | 123.5  | 1.209  |
| Y     | sub22.domain1.com         |      160707 |             9.843 |  66.2  | 0.8064 |
| Y     | sub3.domain1.com          |      115599 |             7.091 |  83.66 | 0.8445 |
| Y     | sub3.sub14.domain1.com    |       45886 |             2.589 |  19.75 | 3.005  |
| Y     | sub4.domain1.com          |       83014 |             4.684 | 129.8  | 1.059  |
| Y     | sub5.domain1.com          |       35422 |             2.003 |  86.08 | 0.1937 |
| Y     | sub6.domain1.com          |       44301 |             2.5   |  27.92 | 3.325  |
| Y     | sub8.domain1.com          |      143108 |             8.57  | 182.7  | 0.9489 |
| Y     | sub9.domain1.com          |      274055 |            17.7   |  61.62 | 1.379  |



Ringkasan per vhost: median D = 66.9, median r = 1.23, IQR r = [0.871, 1.59]


## isu4_false_alarm

| Org   | Ambang                          |   FAR_benign_% |   FAR_nominal_% |   Rasio_FAR/nominal |   Alarm_palsu_per_hari |   FAR_menit_tanpa_serangan_% |   n_menit_serangan_fase2 |   Detection_rate_% |
|:------|:--------------------------------|---------------:|----------------:|--------------------:|-----------------------:|-----------------------------:|-------------------------:|-------------------:|
| X     | Poisson homogen, mu+3*sqrt(mu)  |         9.59   |           0.135 |              71.03  |                138.1   |                      10.18   |                       15 |              80    |
| X     | Poisson homogen, kuantil        |         9.002  |           0.135 |              66.68  |                129.6   |                       9.73   |                       15 |              80    |
| X     | NHPP per jam, mu_h+3*sqrt(mu_h) |         8.451  |           0.135 |              62.6   |                121.7   |                       8.933  |                       15 |              73.33 |
| X     | NHPP per jam, kuantil           |         7.483  |           0.135 |              55.43  |                107.8   |                       8.037  |                       15 |              73.33 |
| X     | Binomial negatif, kuantil       |         0.4164 |           0.135 |               3.085 |                  5.996 |                       0.5276 |                       15 |              20    |
| Y     | Poisson homogen, mu+3*sqrt(mu)  |        15.91   |           0.135 |             117.9   |                229.1   |                       4.905  |                     9546 |              88.56 |
| Y     | Poisson homogen, kuantil        |        15.37   |           0.135 |             113.9   |                221.4   |                       4.905  |                     9546 |              87.8  |
| Y     | NHPP per jam, mu_h+3*sqrt(mu_h) |        17.66   |           0.135 |             130.8   |                254.3   |                       4.605  |                     9546 |              87    |
| Y     | NHPP per jam, kuantil           |        16.96   |           0.135 |             125.6   |                244.2   |                       4.404  |                     9546 |              86.33 |
| Y     | Binomial negatif, kuantil       |         0.3793 |           0.135 |               2.81  |                  5.462 |                       0      |                     9546 |              24.57 |



## isu5_sensitivitas_label

| Org   | Skenario                            |   n_request |   rata2_per_menit |   D_1menit |   CV_jeda |   r_NB | model_terbaik_AIC   |   AIC_NB_pct_Poisson |   persen_dihapus |
|:------|:------------------------------------|------------:|------------------:|-----------:|----------:|-------:|:--------------------|---------------------:|-----------------:|
| X     | A. Tanpa penghapusan                |      213205 |            10.45  |      18.83 |     2.34  | 1.288  | Binomial negatif    |               38.78  |         0        |
| X     | B. Hapus rule strict saja           |      202315 |             9.912 |      17.59 |     2.275 | 1.324  | Binomial negatif    |               40.62  |         5.108    |
| X     | C. Hapus rule moderate saja         |      212576 |            10.41  |      18.76 |     2.338 | 1.288  | Binomial negatif    |               38.77  |         0.295    |
| X     | D. Hapus strict + moderate (naskah) |      201692 |             9.882 |      17.51 |     2.273 | 1.324  | Binomial negatif    |               40.62  |         5.4      |
| Y     | A. Tanpa penghapusan                |     7084558 |           268.7   |     396.3  |     6.177 | 0.7124 | Binomial negatif    |                4.656 |         0        |
| Y     | B. Hapus rule strict saja           |     2516072 |            95.44  |     152.2  |     4.286 | 0.9993 | Binomial negatif    |                9.481 |        64.49     |
| Y     | C. Hapus rule moderate saja         |     6814449 |           258.5   |     385.5  |     5.768 | 0.717  | Binomial negatif    |                4.726 |         3.813    |
| Y     | D. Hapus strict + moderate (naskah) |     2245963 |            85.2   |     139.3  |     3.982 | 1.014  | Binomial negatif    |                9.696 |        68.3      |
| NASA  | A. Tanpa penghapusan                |     1891712 |            47.66  |      22.01 |     1.938 | 3.801  | Binomial negatif    |               34.19  |         0        |
| NASA  | B. Hapus rule strict saja           |     1891712 |            47.66  |      22.01 |     1.938 | 3.801  | Binomial negatif    |               34.19  |         0        |
| NASA  | C. Hapus rule moderate saja         |     1891604 |            47.66  |      22.01 |     3.162 | 3.801  | Binomial negatif    |               34.19  |         0.005709 |
| NASA  | D. Hapus strict + moderate (naskah) |     1891604 |            47.66  |      22.01 |     3.162 | 3.801  | Binomial negatif    |               34.19  |         0.005709 |

