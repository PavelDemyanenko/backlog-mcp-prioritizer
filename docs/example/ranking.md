**Queue:** rho = in_progress / capacity = 9 / 3 = 3.00 -> Effort penalty x3.0

### Ranking Table
| Rank | Task | Critical? | V (Value) | U (Urgency) | C (Cost) | Priority | Notes / Evidence Tier |
|---|---|---|---|---|---|---|---|
| - | [GOLD-3] CVE-2026-40211: RCE в библиотеке шаблонизатора | YES | - | - | - | - | CRITICAL: CVSS 9.8 >= 9 (auto) — executed out of ranking |
| - | [GOLD-4] Сервис генерации недоступен для команд в контуре Б | YES | - | - | - | - | CRITICAL: P1 incident (Show-stopper Incident) (auto) — executed out of ranking |
| - | [GOLD-5] Удалить персональные данные из логов аудита (152-ФЗ) | YES | - | - | - | - | CRITICAL: legal deadline in 16 days (compliance, due 2026-11-25) (auto) — executed out of ranking |
| 1 | [GOLD-14] Rate limiting для API генерации | NO | 0.27 (Conf:1.0) | 4 | 15.00 (Penalty: 3.0) | **0.16** | Evidence: Tier 1 (flag TRUE) |
| 2 | [GOLD-21] Снизить p95 латентности генерации до 2 с | NO | 0.27 (Conf:1.0) | 4 | 24.00 (Penalty: 3.0) | **0.12** | Evidence: Tier 1 (flag TRUE) |
| 3 | [GOLD-1] Подключить 12 продуктовых команд к генерации кода через DC | NO | 0.33 (Conf:1.0) | 3 | 24.00 (Penalty: 3.0) | **0.11** | Evidence: Tier 1 (flag TRUE) |
| 4 | [GOLD-16] Продлить TLS-сертификат внутреннего API генерации | NO | 0.04 (Conf:0.5) | 5 | 3.00 (Penalty: 3.0) | **0.09** | Evidence: Tier 3-4 (flag FALSE) |
| 5 | [GOLD-11] Ускорить холодный старт MCP-сервера | NO | 0.18 (Conf:1.0) | 2 | 9.00 (Penalty: 3.0) | **0.08** | Evidence: Tier 1 (flag TRUE) |
| 6 | [GOLD-6] Подготовка платформы к аудиту PCI DSS | NO | 0.24 (Conf:1.0) | 4 | 39.00 (Penalty: 3.0) | **0.07** | compliance work (compliance): WSJF risk reduction applied; Evidence: Tier 1 (flag TRUE) |
| 7 | [GOLD-10] Автогенерация unit-тестов для сгенерированного кода | NO | 0.22 (Conf:1.0) | 3 | 24.00 (Penalty: 3.0) | **0.07** | Evidence: Tier 1 (flag TRUE) |
| 8 | [GOLD-24] Отчёт о расходе токенов по командам | NO | 0.12 (Conf:1.0) | 2 | 9.00 (Penalty: 3.0) | **0.05** | Evidence: Tier 1 (flag TRUE) |
| 9 | [GOLD-15] Ошибка 500 при генерации файлов больше 2000 строк | NO | 0.07 (Conf:0.5) | 3 | 9.00 (Penalty: 3.0) | **0.05** | Evidence: Tier 3-4 (flag FALSE) |
| 10 | [GOLD-17] Поддержка Kotlin в генераторе кода | NO | 0.28 (Conf:1.0) | 2 | 39.00 (Penalty: 3.0) | **0.04** | Evidence: Tier 1 (flag TRUE) |
| 11 | [GOLD-7] Миграция сервиса генерации на Spring AI 2 | NO | 0.20 (Conf:1.0) | 2 | 39.00 (Penalty: 3.0) | **0.03** | Evidence: Tier 1 (flag TRUE) |
| 12 | [GOLD-20] Документация по MCP-инструментам для продуктовых команд | NO | 0.04 (Conf:0.5) | 2 | 6.00 (Penalty: 3.0) | **0.02** | Evidence: Tier 3-4 (flag FALSE) |
| 13 | [GOLD-2] Кэширование ответов LLM для повторяющихся промптов | NO | 0.07 (Conf:0.5) | 2 | 15.00 (Penalty: 3.0) | **0.02** | Evidence: Tier 3-4 (flag FALSE) |
| 14 | [GOLD-22] Песочница для запуска сгенерированного кода | NO | 0.04 (Conf:0.5) | 3 | 24.00 (Penalty: 3.0) | **0.01** | Evidence: Tier 3-4 (flag FALSE) |
| 15 | [GOLD-19] Ограничить расход токенов до лимита договора с вендором LLM | NO | 0.01 (Conf:0.5) | 5 | 9.00 (Penalty: 3.0) | **0.01** | Evidence: Tier 3-4 (flag FALSE) |
| 16 | [GOLD-8] Переписать оркестратор агентов на event sourcing | NO | 0.07 (Conf:0.5) | 2 | 63.00 (Penalty: 3.0) | **0.01** | architectural change without accepted ADR -> Confidence 0.5; Evidence: Tier 3-4 (flag TRUE) |
| 17 | [GOLD-23] Перевести внутренние вызовы на HTTP/2 | NO | 0.04 (Conf:0.5) | 1 | 15.00 (Penalty: 3.0) | **0.01** | ADR 0031 is missing: not evidence; architectural change without accepted ADR -> Confidence 0.5; Evidence: Tier 3-4 (flag FALSE) |
| 18 | [GOLD-18] Обновить Gradle в шаблонах проектов до 9.x | NO | 0.01 (Conf:0.5) | 1 | 6.00 (Penalty: 3.0) | **0.00** | Evidence: Tier 3-4 (flag FALSE) |

### Refused / Needs Decomposition
- [GOLD-9] ZERO_VALUE: V = 0: never executed regardless of urgency
- [GOLD-12] NEEDS_ESTIMATE: no story_points and no 3-point estimate
- [GOLD-13] ZERO_VALUE: V = 0: never executed regardless of urgency

### Triage: needs your confirmation (scored as non-critical until confirmed)
- [GOLD-15] P1 priority 'Show-stopper' on a Bug: incident/downtime > 15 min?
- [GOLD-16] due in 6 days (2026-11-15): is it a mandatory legal deadline?

### Math trace
- GOLD-14: V = (0.30*2 + 0.15*4 + 0.05*3) / 5 * 1.0 = 0.2700; C0 = story_points = 5 (custom_field); C = 5.00 * 3.0 = 15.00; P = 0.2700 * 4 / 15.00^0.7 = 0.1622
- GOLD-21: V = (0.30*1 + 0.15*5 + 0.10*3) / 5 * 1.0 = 0.2700; C0 = story_points = 8 (custom_field); C = 8.00 * 3.0 = 24.00; P = 0.2700 * 4 / 24.00^0.7 = 0.1168
- GOLD-1: V = (0.30*5 + 0.05*3) / 5 * 1.0 = 0.3300; C0 = story_points = 8 (custom_field); C = 8.00 * 3.0 = 24.00; P = 0.3300 * 3 / 24.00^0.7 = 0.1070
- GOLD-16: V = (0.15*2 + 0.05*2) / 5 * 0.5 = 0.0400; C0 = story_points = 1 (custom_field); C = 1.00 * 3.0 = 3.00; P = 0.0400 * 5 / 3.00^0.7 = 0.0927
- GOLD-11: V = (0.15*3 + 0.10*4 + 0.05*1) / 5 * 1.0 = 0.1800; C0 = story_points = 3 (custom_field); C = 3.00 * 3.0 = 9.00; P = 0.1800 * 2 / 9.00^0.7 = 0.0773
- GOLD-6: V = (0.15*1 + 0.05*4) / 5 * 1.0 = 0.0700; compliance (compliance): risk weighted as top metric, V = 0.30*4 / 5 * 1.0 = 0.2400; C0 = story_points = 13 (custom_field); C = 13.00 * 3.0 = 39.00; P = 0.2400 * 4 / 39.00^0.7 = 0.0739
- GOLD-10: V = (0.20*5 + 0.05*2) / 5 * 1.0 = 0.2200; C0 = story_points = 8 (custom_field); C = 8.00 * 3.0 = 24.00; P = 0.2200 * 3 / 24.00^0.7 = 0.0714
- GOLD-24: V = (0.30*2) / 5 * 1.0 = 0.1200; C0 = story_points = 3 (custom_field); C = 3.00 * 3.0 = 9.00; P = 0.1200 * 2 / 9.00^0.7 = 0.0516
- GOLD-15: V = (0.20*2 + 0.15*2) / 5 * 0.5 = 0.0700; C0 = story_points = 3 (custom_field); C = 3.00 * 3.0 = 9.00; P = 0.0700 * 3 / 9.00^0.7 = 0.0451
- GOLD-17: V = (0.30*4 + 0.20*1) / 5 * 1.0 = 0.2800; C0 = story_points = 13 (custom_field); C = 13.00 * 3.0 = 39.00; P = 0.2800 * 2 / 39.00^0.7 = 0.0431
- GOLD-7: V = (0.20*2 + 0.15*2 + 0.05*3 + 0.05*3) / 5 * 1.0 = 0.2000; C0 = story_points = 13 (custom_field); C = 13.00 * 3.0 = 39.00; P = 0.2000 * 2 / 39.00^0.7 = 0.0308
- GOLD-20: V = (0.30*1 + 0.05*2) / 5 * 0.5 = 0.0400; C0 = story_points = 2 (custom_field); C = 2.00 * 3.0 = 6.00; P = 0.0400 * 2 / 6.00^0.7 = 0.0228
- GOLD-2: V = (0.15*3 + 0.10*2) / 5 * 0.5 = 0.0650; C0 = story_points = 5 (custom_field); C = 5.00 * 3.0 = 15.00; P = 0.0650 * 2 / 15.00^0.7 = 0.0195
- GOLD-22: V = (0.15*2 + 0.05*3) / 5 * 0.5 = 0.0450; C0 = story_points = 8 (custom_field); C = 8.00 * 3.0 = 24.00; P = 0.0450 * 3 / 24.00^0.7 = 0.0146
- GOLD-19: V = (0.05*2) / 5 * 0.5 = 0.0100; C0 = story_points = 3 (custom_field); C = 3.00 * 3.0 = 9.00; P = 0.0100 * 5 / 9.00^0.7 = 0.0107
- GOLD-8: V = (0.15*3 + 0.10*2) / 5 * 0.5 = 0.0650; C0 = story_points = 21 (custom_field); C = 21.00 * 3.0 = 63.00; P = 0.0650 * 2 / 63.00^0.7 = 0.0072
- GOLD-23: V = (0.15*1 + 0.10*2) / 5 * 0.5 = 0.0350; C0 = story_points = 5 (custom_field); C = 5.00 * 3.0 = 15.00; P = 0.0350 * 1 / 15.00^0.7 = 0.0053
- GOLD-18: V = (0.05*2 + 0.05*1) / 5 * 0.5 = 0.0150; C0 = story_points = 2 (custom_field); C = 2.00 * 3.0 = 6.00; P = 0.0150 * 1 / 6.00^0.7 = 0.0043
