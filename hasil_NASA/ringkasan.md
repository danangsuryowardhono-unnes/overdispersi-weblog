# Ringkasan analisis tambahan — NASA

Menit dianalisis: 39693 (fase I 23815, fase II 15878)

D 1 menit = 22.01; ACF lag 1 = 0.842; lag pertama ACF < 0,1 = None

- IK 95% block bootstrap, blok 30 menit: 19.68–24.55
- IK 95% block bootstrap, blok 60 menit: 19.05–25.25
- IK 95% block bootstrap, blok 120 menit: 18.12–26.96
- Deret dijarangkan 120 menit: n = 331, D = 21.63, p = 0.00e+00

r NB (fase I) = 3.801, IK 95% profil 3.728–3.875; gradien di optimum 1.66e-04

NB + lag: β1 = 0.596 (SE 0.007), β2 = 0.177 (SE 0.007), r = 9.72
INGARCH(1,1)-NB: a = 0.279, b = 0.698, r = 11.54

Log-score fase II per observasi:
- Poisson homogen: -12.452
- NHPP per jam: -8.318
- Binomial negatif: -4.404
- NB + lag: -4.102
- INGARCH(1,1)-NB: -4.051

Rolling-origin (rata-rata LS):
- Poisson homogen: -12.602
- NHPP per jam: -9.484
- Binomial negatif: -4.438
- NB + lag: -4.028
- INGARCH(1,1)-NB: -3.962
Model terbaik per titik asal: {'INGARCH(1,1)-NB': 4}

Diagnostik residual (fase II):
- Binomial negatif: ACF lag1 = 0.577, Ljung–Box(60) p = 0.00e+00
- NB + lag: ACF lag1 = -0.159, Ljung–Box(60) p = 3.50e-226
- INGARCH(1,1)-NB: ACF lag1 = 0.106, Ljung–Box(60) p = 7.10e-71

Ringkasan uji per jam (Bonferroni α = 0,05/24):
- akhir pekan, 1 menit: tolak 24/24, overdispersi 24/24, median D 6.4
- akhir pekan, 5 menit: tolak 24/24, overdispersi 24/24, median D 19.0
- akhir pekan, 10 menit: tolak 24/24, overdispersi 24/24, median D 30.8
- hari kerja, 1 menit: tolak 24/24, overdispersi 24/24, median D 8.8
- hari kerja, 5 menit: tolak 24/24, overdispersi 24/24, median D 27.1
- hari kerja, 10 menit: tolak 24/24, overdispersi 24/24, median D 47.9
- semua, 1 menit: tolak 24/24, overdispersi 24/24, median D 9.5
- semua, 5 menit: tolak 24/24, overdispersi 24/24, median D 33.7
- semua, 10 menit: tolak 24/24, overdispersi 24/24, median D 59.9

Monitoring pada target FAR 0,135%: lihat tabel_B2_monitoring.csv
