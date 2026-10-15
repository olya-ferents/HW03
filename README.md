# L04 · RAGAS Diagnostic Report — PayPilot

Набір із ДЗ_2: [olya-ferents/HW02Matirial](https://github.com/olya-ferents/HW02Matirial)

## Запуск
Покладіть `golden.jsonl` у `~/paypilot/l03/sets/` і виконайте:

```bash
docker compose run --rm eval --set golden --profile clean
```

`set_hash`: `1af9bba92beb`

## Retrieval-кейси

| id | Джерело | Файл і рядок корпусу |
| --- | --- | --- |
| RET-H01 | complaint C-13 | `tariffs.md:16` — FX spreads by tier, Tier 3 |
| RET-H02 | complaint C-14 | `disputes.md:10` — duplicate_charge |
| RET-H03 | lab, вправа 1 | `tariffs.md:16` — FX spreads by tier, Tier 3 |
| RET-H04 | lab, вправа 2 | `limits.md:12` — Tier 2 daily/monthly limits |
| RET-H05 | corpus | `limits.md:11` — Tier 1 daily/monthly limits |
| RET-H06 | corpus | `limits.md:13` — Tier 3 daily/monthly limits |
| RET-H07 | corpus | `tariffs.md:23` — SWIFT fee |
| RET-H08 | corpus | `tariffs.md:24` — card payment fee |
| RET-H09 | corpus | `disputes.md:9` — goods_not_received |
| RET-H10 | corpus | `disputes.md:12` — unauthorized_debit |

## Прогони

| Прогін | Профіль | Результат | Звіт |
| --- | --- | --- | --- |
| Baseline | `clean` | 43/45 (retrieval 9/10) | [reports/golden-clean-20261014T173546.json](reports/golden-clean-20261014T173546.json) |
| Профіль заняття | `lesson-04` | 36/45 (retrieval 3/10) | [reports/golden-lesson-04-20261014T174004.json](reports/golden-lesson-04-20261014T174004.json) |

Прогноз до прогону `lesson-04`: RET-H01 може впасти, бо C-13 на дефектному індексі може отримати обрізаний рядок Tier 3 або не виконати пошук; RET-H02 — через `D17` (`top_k 1`) і відсутність рядка `duplicate_charge | 60` у першому чанку; RET-H03 — бо `tariffs.md#b3` обрізає Tier 3 allowance на `EUR 5`; RET-H04 — бо одного фрагмента може не вистачити для спреду й денного ліміту; RET-H05/RET-H06 — бо `limits.md#b1` закінчується до числових рядків; RET-H07 — бо `D05` забороняє пошук transfer fees і надає застаріле правило SWIFT без 0.3%; RET-H09 — бо `top_k 1` може повернути вступ замість рядка вікон; RET-H10 — з тієї самої причини: вступний чанк `disputes.md#b1` не містить чисел вікон.

Коміт із прогнозом: `66b82229f1aad0c61dadfa43c989818f64cc6a74` (до фінальних прогонів).

Що впало у `clean`: `DIS-C11`, `RET-H04`. Що впало у `lesson-04`: `DIS-005`, `CMP-004`, `RET-H01`, `RET-H02`, `RET-H04`, `RET-H05`, `RET-H06`, `RET-H07`, `RET-H10`. Розбіжність із прогнозом: RET-H03 пройшов, бо `quote_fx` дав агенту повний allowance попри обрізаний retrieved-фрагмент; це pass відповіді, а не доказ повноти retrieval. RET-H09 пройшов після повторного запиту, який повернув `disputes.md#b2` із рядком `goods_not_received | 90`. Інші прогнозовані retrieval-збої відтворилися.

### Чому RET-H04 падає у `clean`

RET-H04 очікує, що відповідь міститиме денний ліміт Tier 2 — `EUR 20,000` з `limits.md#s1`. У прогоні `clean` пошук у `kb_clean` мав `top_k 4`: він повернув `glossary.md#s6`, `tariffs.md#s2`, `tariffs.md#s1` та `onboarding.md#s1`. Потрібний `limits.md#s1` не потрапив до четвірки. Тож модель знайшла спред і тарифний ліміт конвертації, але не мала джерела для денного ліміту переказів і не стала його вгадувати; перевірка RET-H04 упала, бо у відповіді немає `EUR 20,000`.

Це той самий поріг видачі, що й у вправі 2: при `top_k 4` `limits.md#s1` відсутній, а при `top_k 5` повертається разом із `tariffs.md#s2`, і відповідь містить обидва потрібні факти. Отже, для RET-H04 на `clean` причина — обмежений `top_k`, а не відсутність потрібного рядка в корпусі чи помилка генерації. Деталі порівняння: [lw04.md](./lw04.md#вправа-2-видача-чотирьох-фрагментів-замало).
