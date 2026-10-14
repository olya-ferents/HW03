# L04 · RAGAS Diagnostic Report — PayPilot

Набір із ДЗ_2: [olya-ferents/HW02Matirial](https://github.com/olya-ferents/HW02Matirial)

## Запуск
Покладіть `golden.jsonl` у `~/paypilot/l03/sets/` і виконайте:

```bash
docker compose run --rm eval --set golden --profile clean
```

`set_hash`: `f0a14d1edbe8`

## Retrieval-кейси

| id | Джерело | Файл і рядок корпусу |
| --- | --- | --- |
| RET-H01 | lab, вправа 1 | `tariffs.md:16` — FX spreads by tier, Tier 3 |
| RET-H02 | lab, C-14 | `disputes.md:10` — duplicate_charge |
| RET-H03 | corpus | `tariffs.md:14` — Tier 1 FX spread |
| RET-H04 | corpus | `tariffs.md:15` — Tier 2 conversion allowance |
| RET-H05 | corpus | `limits.md:11` — Tier 1 daily/monthly limits |
| RET-H06 | corpus | `limits.md:13` — Tier 3 daily/monthly limits |
| RET-H07 | corpus | `tariffs.md:23` — SWIFT fee |
| RET-H08 | corpus | `tariffs.md:24` — card payment fee |
| RET-H09 | corpus | `disputes.md:9` — goods_not_received |
| RET-H10 | corpus | `disputes.md:12` — unauthorized_debit |

## Прогони

| Прогін | Профіль | Результат | Звіт |
| --- | --- | --- | --- |
| Baseline | `clean` | ще не виконано | — |
| Профіль заняття | `lesson-04` | ще не виконано | — |

Прогноз до прогону `lesson-04`: RET-H01 може впасти, бо `kb_broken` обрізає рядок Tier 3 allowance на `EUR 5`; RET-H02 може впасти, бо `D17` обмежує видачу одним фрагментом, тоді як рядок `duplicate_charge | 60` є в наступному чанку; RET-H07 може впасти, бо `D05` забороняє шукати transfer fees і містить застаріле правило SWIFT без 0.3%. Прогноз спирається на опис профілю й результати/рішення L04, але потребує перевірки прогоном.

Коміт із прогнозом: буде додано після коміту прогнозу.

Що впало: ще не перевірено. Розбіжність із прогнозом: ще не перевірено.
