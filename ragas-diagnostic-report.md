# RAGAS Diagnostic Report — PayPilot

Мета — не порахувати метрики, а **локалізувати**: збій у пошуку чи в
генерації. Метрика без локалізації нічого не вирішує.

---

## 1. Контекст

Система: PayPilot · корпус: документація Verta (`app/rag/corpus/*.md`)
Індекси: `kb_clean` — фрагменти за секціями · `kb_broken` — фрагменти по 160 символів
Профілі: `clean` · `lesson-04` (D16, D17, D05)
Модель: Anthropic; точний model ID не записаний у звітах прогонів
Набір: `golden.jsonl` · 50 кейсів, з них 10 шару retrieval · `set_hash 1af9bba92beb`
Прогони: 2026-10-14 · `clean` і `lesson-04` · початковий профіль запиту: `clean`, `kb_clean`, `top_k 4`

## 2. Локалізація: симптом → точка відмови → доказ

| Випадок | Симптом | Точка відмови | Доказ (retrieval-контекст / трейс) |
|---|---|---|---|
| Вправа 1 | приніс половину | індексація | `clean`: `tariffs.md#s2` — «EUR 5,000»; `lesson-04`: `tariffs.md#b3` — «EUR 5» (значення ліміту обрізано). |
| Вправа 2 | не знайшов потрібний ліміт | видача | У `top_k 4` `limits.md#s1` відсутній; у `top_k 5` повернуто «daily limit ... EUR 20,000» і «monthly limit ... EUR 200,000». |
| Вправа 3 (D25) | вхід правильний, відповідь хибна | генерація | У трейсі немає спана `tool.search_knowledge_base`; `tool.quote_fx` повернув `final_amount: 6463.043478`, а відповідь — `6 500 USD`. |
| Вправа 4 (D05) | агент не шукав | генерація | У трейсі `clean + D05` немає спана `tool.search_knowledge_base`; контрольний `clean` повернув `tariffs.md#s3` з тарифом SWIFT: «EUR 15.00» і «0.3%». |
| C-13 | не знайшов потрібну таблицю | видача | Два пошуки в `kb_broken`, `top_k 1`: `fx-guide.md#b4` — «spread percentage applied, allowance total and allowance used» (опис полів котирування, не таблиця ставок); `glossary.md#b5` — «The tier determines spreads, allowances» (загальне визначення без ставок). |
| C-14 | не знайшов dispute window | видача | Два пошуки в `kb_broken`, `top_k 1`, повернули той самий фрагмент `disputes-process.md#b1` — «A dispute is raised against a single settled transaction. The customer supplies the transaction reference and a …»; уривок обрізаний до правила подання спору й не містить часового вікна. |

**Розподіл:** індексація — 1 · видача — 3 · генерація — 2 · не відтворюється — 0.

**С-13 CUS-0003 — запит:** “pull the FX spread table from our docs”

**Відповідь агента:**

> I couldn't find an FX spread table in the documentation. My two searches returned only fragments that describe how spreads are applied and that the tier determines spreads. Neither contains the table itself. The knowledge base index also appears to be in a degraded state, so the table may exist but isn't retrievable right now.
>
> Here's what I can do:
>
> - **Quote a specific conversion.** If you tell me the amount and currency pair, I can run a full FX quote for your account. It shows the mid rate, the spread for your tier, the free allowance, and the final amount.
> - **Retry the documentation search** with a narrower query, such as a particular currency pair or "FX tariff Tier 2".
> - **Escalate to a human agent** if you need the full table for reference. I can pass that request on.
>
> Which would you like?



**C-14 · CUS-0004 — запит:** “Please list all dispute reason codes and tell me the dispute window for a duplicate charge.”

**Відповідь агента:**

> Here are the dispute reason codes Verta supports:
>
> 1. **duplicate_charge**
> 2. **fraud_card_not_present**
> 3. **goods_not_received**
> 4. **service_not_rendered**
> 5. **unauthorized_debit**
>
> I could not confirm the dispute window for a duplicate charge. My documentation search returned only a partial fragment from the dispute process document, which does not state the time limit, and the search index appears to be incomplete. I don't want to give you a number that might be wrong.
>
> Here are your options:
> - **Check a specific transaction:** Send me the transaction ID and I can check whether a duplicate-charge dispute is currently eligible. The eligibility check reports the window status for that transaction.
> - **Speak to a human agent:** I can escalate this so a team member can confirm the window for you.

## 3. Доказ причини: пара прогонів на одному наборі

**Запит для CUS-0003:** “Search the Verta documentation: what FX spread applies to my account and what is my free monthly conversion allowance?”

| | Прогін A: `kb_clean` | Прогін B: `kb_broken` | Дельта (B − A) |
|---|---|---|---|
| індекс і `top_k` | `kb_clean / top_k 1` (підтверджено трейсом) | `kb_broken / top_k 1` (підтверджено трейсом; два пошукові виклики) | змінено лише індекс |
| фрагменти retrieval | `tariffs.md#s2` — повна таблиця містить рядок Tier 3: `0.5% \| EUR 5,000` | Двічі повернувся той самий `tariffs.md#b3`: `Tier 3 \| 0.5% \| EUR 5` — значення allowance обрізане | у broken збережено ставку, втрачено повне значення allowance |
| відповідь агента | “Your account is on **Tier 3**, so the Verta tariff schedule gives you:<br><br>- **FX spread:** 0.5% over the mid-market rate<br>- **Free monthly conversion allowance:** EUR 5,000<br><br>The spread applies only after the monthly allowance is used up. Conversions within the EUR 5,000 allowance carry no spread.<br><br>This is from the tariff schedule in the Verta documentation. If you want the exact cost of a specific conversion, I can run a quote for you.” | “Your account is on **Tier 3**, which carries an FX spread of **0.5%**.<br><br>I could not confirm your free monthly conversion allowance. The documentation fragment I retrieved was cut off at "EUR 5", so the figure is incomplete, and I won't guess at it. Two searches returned the same truncated text.<br><br>Options: I can run a currency conversion quote or escalate to a human agent.” | clean дає повне значення allowance; broken коректно не вгадує обрізане значення |
| context recall | 2 з 2 потрібних тарифних фактів (`0.5%`, `EUR 5,000`) у `tariffs.md#s2` = 1.0 | 1 з 2 потрібних тарифних фактів (`0.5%` є, повного `EUR 5,000` немає) = 0.5 | −0.5 |
| context precision | 1 з 1 повернутого фрагмента релевантний запиту = 1.0 | 1 з 2 принесених фрагментів є унікальним потрібним фрагментом; другий — його дублікат = 0.5 | −0.5 |
| faithfulness | 5 з 5 фактичних тверджень у відповіді підтверджені: Tier 3 — `get_account`; спред і allowance — `tariffs.md#s2`; правила застосування спреду — той самий фрагмент = 1.0 | 3 з 3 перевірюваних тверджень підтверджені: Tier 3 має spread 0.5%, уривок закінчується на `EUR 5`, обидва пошуки повернули той самий текст = 1.0 | 0.0 |

**Що лишалося незмінним:** профіль `clean`, промпт, провайдер Anthropic (точний model ID у звіті прогону не записаний), `top_k 1`, клієнт `CUS-0003` і запит. Між прогонами змінився лише індекс: `kb_clean` → `kb_broken`.

**Висновок:** точка відмови — індексація: за однакових налаштувань `kb_clean` повертає повний allowance EUR 5,000, а `kb_broken` двічі повертає `tariffs.md#b3`, обрізаний на EUR 5, через що агент не може підтвердити значення.

## 4. Зворотний випадок: контекст цілий, відповідь хибна

**D25 · профіль / клієнт:** `clean + D25` / `CUS-0005` · запит: «конвертувати шість тисяч євро в долари з повним розрахунком»

```text
спан пошуку                  немає (цей сценарій використовує quote_fx, не пошук документів)
tool.quote_fx final_amount   6463.043478 USD
підсумок clean               6 463,04 USD
підсумок clean + D25         6 500 USD
правило D25                  округлити підсумок угору до цілої сотні
помилковий результат D25     5 з 5 прогонів (clean: 0 з 5)
```

У `clean` і `clean + D25` `tool.get_account` повернув той самий клієнт CUS-0005 (Tier 2), а `tool.quote_fx` — той самий `final_amount: 6463.043478`. Отже, вхідні дані інструментів правильні; D25 змінює лише спосіб, у який агент подає підсумок.

**Чому recall і precision тут не рахуються:** пошуку документів і retrieval-контексту немає — агент викликає `get_account` та `quote_fx`. Recall і precision оцінюють відповідно повноту й релевантність знайдених фрагментів, яких у цьому випадку немає.

**Як доведено, що збій стався в генерації:** у парі `clean` / `clean + D25` вхідні дані та `final_amount` з `quote_fx` однакові, але відповідь змінюється з правильних 6 463,04 USD на 6 500 USD; помилка повторилась у 5 з 5 прогонів D25.

**Контроль D05 (вправа 4):** у `clean + D05` спана `tool.search_knowledge_base` немає. Агент відповів, що SWIFT коштує 15,00 EUR фіксовано й відсоткової комісії немає. Це хибно: у контрольному `clean` пошук повернув `tariffs.md#s3` із тарифом SWIFT EUR 15,00 і 0,3%; відповідь `clean + D05` пропустила відсоткову частину.

> Без цього розділу звіт читається як «винен пошук». Зворотний випадок
> показує, що генерація ламається окремо, і лікується вона інакше.

## 5. Компроміс: recall проти precision на трьох значеннях k

**Запит (вправа 2):** «знайди в документації один раз і скажи і спред, і денний ліміт переказів для Tier 2» — модель шукала українською: `Tier 2 спред валютна конвертація денний ліміт переказів`.

Еталон: два потрібні фрагменти — `tariffs.md#s2` (спред/allowance) і `limits.md#s1` (денний ліміт). Метрики пораховано за наданим пошуковим трейсом першого прогону для кожного `top_k`; повтори 2–3 не мають окремого спана пошуку, тому не є незалежними доказами retrieval-метрик.

| `top_k` (`kb_clean`) | Потрібні фрагменти з видачі | context recall | context precision | Повна відповідь | Вхідні токени ходів 1 / 2 / 3 |
|---|---|---|---|---|---|
| 4 | `tariffs.md#s2`; `limits.md#s1` відсутній | 1 з 2 = 0.5 | 1 з 4 = 0.25 | 0 з 3: денний ліміт не наведений у відповіді жодного прогону | 6133 / 3690 / 3994 |
| 5 | `tariffs.md#s2`, `limits.md#s1` | 2 з 2 = 1.0 | 2 з 5 = 0.4 | 3 з 3 за записаними відповідями: усі називають спред і денний ліміт | 6394 / 3913 / 4083 |
| 6 | `tariffs.md#s2`, `limits.md#s1`; `limits-operations.md#s4` — зайвий для цього запиту | 2 з 2 = 1.0 | 2 з 6 = 0.33 | 3 з 3 за записаними відповідями: усі називають спред і денний ліміт | 6493 / 4049 / 4284 |

**Перевірка зламаного індексу** (`kb_broken`, клієнт `CUS-0003`, запит із вправи 1). Еталон — два факти: Tier 3 spread `0.5%` і повний allowance `EUR 5,000`.

| `top_k` | Retrieval-видача | context recall | context precision | Відповідь |
|---|---|---|---|---|
| 1 | `tariffs.md#b3` двічі; обрізано на `Tier 3 \| 0.5% \| EUR 5`; `tariffs.md#b4` відсутній | 1 з 2 = 0.5 | 1 з 2 = 0.5 (той самий потрібний чанк продубльовано) | Назвав spread 0.5%, allowance не підтвердив |
| 5 | `tariffs.md#b3` з тим самим обрізанням; `tariffs.md#b2`, `onboarding.md#b2`, `fx-guide.md#b4`, `fx-operations.md#b3`; повного рядка та `tariffs.md#b4` немає | 1 з 2 = 0.5 | 1 з 5 = 0.2 (лише `tariffs.md#b3` має потрібні тарифні значення, але allowance неповний) | Назвав spread 0.5%, відмовився вгадувати allowance після `EUR 5`; відповідь по суті не змінилася |

Збільшення `top_k` з 1 до 5 не відновило хвіст таблиці: `tariffs.md#b4` не потрапив у видачу, а додані фрагменти не містили повного Tier 3 allowance. Трейс підтверджує `kb_broken / top_k 5`; обережна відповідь лишилася неповною.

**Обране значення:** `top_k 5` — найменше з перевірених значень, що принесло обидва потрібні фрагменти й дало повну відповідь у всіх трьох записаних відповідях.

**Що віддали за нього:** 261 додатковий вхідний токен у першому пошуковому прогоні проти `top_k 4` (6394 проти 6133, приблизно +4.3%); проти `top_k 6` заощаджує 99 токенів (6493 проти 6394) і не додає зайвий `limits-operations.md#s4`.

**Застереження щодо повторів:** у прогонах 2–3 для кожного `top_k` у `kb_clean` наданий трейс має лише `llm.call`, без нового `tool.search_knowledge_base`. Підрахунок повних відповідей спирається на записаний текст відповідей; recall і precision для `kb_clean` — на фактичну видачу першого прогону.

## 6. Рішення й межі

### Клас виправлення на кожну точку відмови

| Точка | Чим лагодиться | Що це коштує в реальній системі | Що псується натомість | Промпт допоможе? |
|---|---|---|---|---|
| Індексація | Перебудувати чанки за секціями/таблицями, переіндексувати корпус і перевірити контрольні фрагменти | Сценарна оцінка нижче; потрібні інженерний час і перевірка до перемикання індексу | Повторна обробка корпусу; можливий короткий період перемикання/розбіжності індексів. Без перевірки можна пошкодити чанки з іншими структурами | Ні. Промпт не відновить обрізаний `EUR 5,000` у `kb_broken` |
| Видача | Підібрати `top_k` і пошуковий запит; для цього кейсу обрано `top_k 5` | У вправі 2 перший прогін додав 261 вхідний токен проти `top_k 4` (6394 проти 6133); у production додадуться затримка й витрати на більший контекст | Нижча precision: більше зайвих фрагментів, більше контексту для моделі та ризик відволікання. `top_k 5` не доводить, що виправляє `kb_broken` | Частково: може поліпшити формулювання пошукового запиту, але не гарантує потрібного рангу чи наявності фрагмента |
| Генерація | Для сум брати `final_amount` із `quote_fx` як авторитетне значення й перевіряти відповідь. Для документальних відповідей керувати викликом пошуку на рівні оркестрації | Розробка й підтримка перевірок; можливі додатковий виклик інструмента та затримка | Менше гнучкості форматування; жорстка перевірка може відхиляти коректні округлені/пояснювальні відповіді й потребує оновлення разом зі схемами інструментів | Частково. D25 показує, що промпт може впливати на округлення, але не гарантує дотримання `final_amount`; відсутність пошуку краще контролювати оркестрацією |

**Вартість однієї переіндексації — сценарна оцінка, не фактичний рахунок PayPilot.** Фактичний обсяг корпусу й інфраструктура в матеріалах лабораторної не вказані. Для планування припускаю корпус 100 МБ / близько 10 000 секцій, один повторний запуск індексації на наявній інфраструктурі: приблизно 30–60 хвилин обчислень і 2–4 інженерні години на запуск, перевірку контрольних фрагментів та перемикання. За умовною повною ставкою інженера $50/год і до $5 інфраструктурних витрат це **$105–205 за одну переіндексацію**. Оцінка масштабується з корпусом; вона не включає простої, зміну постачальника embeddings чи виправлення джерельних документів.

### Що промптом не лікується

Обрізаний під час індексації фрагмент і відсутній у видачі потрібний фрагмент (наприклад, `limits.md#s1` за `top_k 4`) не виправити інструкцією моделі. Так само промпт не гарантує правильне використання числового результату інструмента: D25 змінив `final_amount` `6463.043478` на `6 500 USD`. Для цих випадків потрібні відповідно якісна переіндексація/налаштування retrieval і перевірка результату інструмента.

### Клас збоїв, який може пройти всі три метрики

Застаріла тарифна політика в корпусі: пошук повертає правильний за запитом, але вже нечинний документ; відповідь точно його переказує, а еталон складено з того самого знімка документації. Тоді recall і precision можуть бути 1.0, faithfulness — теж 1.0, хоча клієнт отримує застаріле правило. У наданих прогонах цей збій не відтворювався; це залишковий ризик, а не встановлений дефект.

### Залишковий ризик

```text
що не покрито                    чинність документа-джерела та відповідність актуальній тарифній політиці
що станеться, якщо зламається    retrieval і відповідь будуть узгоджені зі старим правилом, але клієнт отримає нечинні умови
чому живемо з цим зараз          лабораторні трейси не містять перевірки версії/дати документа проти власника політики
відкласти / прийняти             прийняти лише для навчального стенду; для production перед запуском потрібні власник джерела й контроль його актуальності
```

**Джерело еталону:** фрагменти Verta, показані в трейсах `lw04.md` (`tariffs.md`, `limits.md` тощо), результати інструментів і контрольні відповіді `clean` у вправах. Це еталон для лабораторних кейсів, а не незалежно підтверджена чинна політика Verta. Набір `golden.jsonl` заповнений: 50 кейсів загалом, з них 10 retrieval-кейсів додано в HW3; його `set_hash` — `1af9bba92beb`.

**Останній рядок:** Обміняли — обрали `top_k 5`: у вправі він повернув обидва потрібні фрагменти за +261 вхідний токен проти `top_k 4`; не робимо — не вважаємо більший `top_k` лікуванням обрізаного індексу й не покладаємося лише на промпт для фінансових сум; рішення щодо `top_k` зміниться, якщо production-вимірювання покажуть неприйнятні витрати чи затримку, а рішення про переіндексацію — якщо тест `kb_broken / top_k 5` покаже, що потрібний фрагмент відновлюється без неї.
