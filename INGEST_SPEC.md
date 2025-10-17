# Ingest Katmanı – Mevcut Proje Dosyalarından Okuma

## Hedef
Mevcut plan dosyalarını (elle Excel hazırlamadan) okuyup Monte Carlo simülatörünün beklediği şemaya dönüştürmek:
- Çıktılar: `examples/tasks.csv`, `examples/calendars.json` (+ boş `examples/risks.csv`)
- Minimum alanlar: `task_id, task_name, predecessors, calendar_id, milestone_flag`
- Dağılım parametrizasyonu: Dosyada yalnızca deterministik süre varsa **kural bazlı** üçgen dağılım üret:
  - Varsayılan: `d_min = 0.8 * base`, `d_most_likely = base`, `d_max = 1.5 * base`
  - İsteğe bağlı: `owner/work_package` bazlı çarpanlar (config ile)

## Desteklenen formatlar (v1)
1) **MS Project XML (.xml)** – Tam destek (Görevler, Bağımlılıklar, Kısıtlar, Milestone, Takvim).
2) **Primavera P6 XER (.xer)** – Temel destek (Görevler, Bağımlılıklar, Takvim adı).
3) **CSV (kolonlu)** – Basit şema eşlemesi (opsiyon).
> Not: **MPP ikili** dosyayı doğrudan okumak gerekiyorsa, MPXJ köprüsü ekleyebiliriz; yoksa lütfen MPP’yi “Save As → XML” export edin.

## Bağımlılık türleri eşlemesi
- MS Project `Type`: 1=FF, 2=FS, 3=SF, 4=SS
- Lag: örn. `+2d`, `-1d` olarak yaz
- Çıktı formatı: `predecessors`: virgüllü bağlantılar, örn: `T1 FS+0d,T2 SS+2d`

## Takvimler
- MS Project XML’den `Calendar` isimleri çekilir; bulunamazsa `TR_Factory_ShiftA` varsayılanı yazılır.
- P6 XER için takvim adı alanı varsa kullan; yoksa varsayılan.

## Milestone
- `Milestone=true` ise `milestone_flag=true`, ve süre parametreleri `0,0,0`.

## Kısıtlar
- MS Project: `ConstraintType` ve `ConstraintDate` varsa `constraint` ve `fixed_date` alanlarına yazılır (NE/NL/MSO/MFO eşlemesi basit kuralla yapılır).

## Yapı & Komut
- `ingest/` altında format bazlı dönüştürücüler
- Ana CLI: `ingest_project.py`
