<p align="center">
  <img src="docs/assets/logo-128.png" width="96" height="96" alt="Логотип Backlog MCP Prioritizer">
</p>

<h1 align="center">Backlog MCP Prioritizer</h1>

<p align="center">
  Приоритизация бэклога <b>YouTrack</b> с опорой на доказательства, которую выполняет ваш ИИ-агент<br>
  (Claude Code, Cursor, Claude Desktop): агент оценивает, детерминированный калькулятор считает,<br>
  и ничего не применяется, пока человек не скажет <b>Approve</b>.
</p>

<p align="center">
  <a href="https://github.com/PavelDemyanenko/backlog-mcp-prioritizer/actions/workflows/ci.yml"><img src="https://github.com/PavelDemyanenko/backlog-mcp-prioritizer/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="Лицензия MIT"></a>
</p>

<p align="center"><a href="README.md">English version</a></p>

---

## Зачем

На просьбу «расставь приоритеты в бэклоге» LLM обычно выдаёт уверенный список на угаданных цифрах.
Здесь работа разделена:

- **MCP-сервер** читает YouTrack (только чтение) и отдаёт компактный нормализованный вид каждой задачи:
  story points, статус, флаг доказательств, ссылки на ADR с проверкой по вашему репозиторию и
  сигналы триажа (приоритет, тип, теги, срок, CVSS). Сырые описания модели не передаются.
- **Навык** объясняет агенту, что оценивать (Impact по метрикам, Urgency) и чего делать нельзя
  (поднимать Confidence без доказательств, убирать штраф за загрузку, применять что-либо без подтверждения).
- **Калькулятор** (`priority.py`) считает всё: `Priority = V·U / C^0.7` в духе WSJF/RICE, уровни
  доказательств, штраф за загрузку команды по живым данным, PERT-оценки, автотриаж критичных задач
  и полную трассировку расчёта.

## Как устроено

```text
MCP-клиент (Claude Code, Cursor, …) ──stdio──▶ backlog-mcp-prioritizer ──HTTPS GET──▶ YouTrack REST API
   │  навык: backlog-prioritization-engine        (MCP-сервер на Spring AI,        (токен только на чтение)
   │  навык: adr-custodian                          Java 25)  ──читает──▶ docs/adr/*.md вашего репозитория
   └──▶ python3 priority.py  (вся арифметика, правила, триаж)
```

## Инструменты

| Инструмент | Параметры | Возвращает |
|---|---|---|
| `youtrack_query_backlog` | `search_query`, `limit=20` (максимум 100) | `[{id, summary, status, story_points, story_points_source, evidence_found_in_text, adr_refs, triage}]` |
| `youtrack_count_issues` | `search_query` | `{count, capped}`: точное число задач без лимита 100 (задачи в работе для ρ) |
| `adr_list` | `status?` | ADR вашего репозитория: `{id, title, status, date, superseded_by, file}` |
| `adr_read` | `id` | Текст одного ADR (только по номеру, путь передать нельзя) |

Сопоставление полей, правила доказательств и формат ответа: [docs/tools.md](docs/tools.md).

## Быстрый старт

Нужно: YouTrack (Cloud или Server), MCP-клиент, **Docker** (или вместо него Java 25) и
**Python 3.10+** для калькулятора. Всё собрано в
[последнем релизе](https://github.com/PavelDemyanenko/backlog-mcp-prioritizer/releases/latest).

1. **Создайте токен только на чтение.** YouTrack → аватар → Profile → Account Security → Tokens →
   *New token…*, область **YouTrack**. Используйте учётную запись, которая может только *читать*
   нужные проекты.

2. **Подключите сервер в своём проекте** (выполнять в папке проекта, чтобы ADR и токен были свои
   у каждого проекта). Claude Code:
   ```bash
   claude mcp add -s local backlog \
     -e YOUTRACK_BASE_URL=https://yourcompany.youtrack.cloud -e YOUTRACK_TOKEN=perm:xxxx \
     -- docker run -i --rm -e YOUTRACK_BASE_URL -e YOUTRACK_TOKEN \
        -v "$PWD/docs/adr:/adr:ro" ghcr.io/paveldemyanenko/backlog-mcp-prioritizer:latest
   ```
   `-s local` хранит токен в вашей пользовательской настройке (`~/.claude.json`), а не в репозитории.
   Никогда не кладите токен в коммитящийся `.mcp.json`. Если ADR в проекте нет, уберите часть `-v …`:
   иначе Docker создаст пустую папку `docs/adr` с владельцем root.

   <details><summary>Cursor / Claude Desktop</summary>

   `.cursor/mcp.json` (добавьте в .gitignore) или `claude_desktop_config.json`:
   ```json
   { "mcpServers": { "backlog": {
       "command": "docker",
       "args": ["run", "-i", "--rm", "-e", "YOUTRACK_BASE_URL", "-e", "YOUTRACK_TOKEN",
                "-v", "/ABS/PATH/TO/PROJECT/docs/adr:/adr:ro",
                "ghcr.io/paveldemyanenko/backlog-mcp-prioritizer:latest"],
       "env": { "YOUTRACK_BASE_URL": "https://yourcompany.youtrack.cloud", "YOUTRACK_TOKEN": "perm:xxxx" } } } }
   ```
   Навыки — функция Claude Code; в других клиентах используйте `SKILL.md` как правило или промпт.
   </details>

   <details><summary>Без Docker (Java 25)</summary>

   Скачайте `backlog-mcp-server-<version>.jar` из релиза:
   ```bash
   claude mcp add -s local backlog \
     -e YOUTRACK_BASE_URL=https://yourcompany.youtrack.cloud -e YOUTRACK_TOKEN=perm:xxxx \
     -- java -jar /ABS/PATH/backlog-mcp-server-<version>.jar
   ```
   ADR читаются из `docs/adr` относительно папки, в которой запущен клиент (меняется через `ADR_DIR`).
   </details>

3. **Установите навыки.** Распакуйте `backlog-mcp-prioritizer-skills-<version>.zip` из релиза в
   `.claude/skills/` проекта (или в `~/.claude/skills/`, чтобы навыки были во всех проектах):
   ```bash
   mkdir -p .claude/skills && unzip backlog-mcp-prioritizer-skills-<version>.zip -d .claude/skills/
   ```

4. **По желанию: настройте под свою команду** файлом `.backlog-prioritizer.json` в корне проекта:
   свои метрики ценности и веса, свои названия приоритетов, типов задач и тегов (например, для
   русскоязычного YouTrack). См. [настройку](skills/backlog-prioritization-engine/references/configuration.md).

5. **Перезапустите MCP-клиент** (или `/mcp` в Claude Code) и попросите:
   *«Приоритизируй бэклог YouTrack проекта DEV»*. Агент посчитает задачи в работе, спросит ёмкость
   команды и спорные критичные задачи, покажет ранжирование с трассировкой расчёта и будет ждать
   **Approve / Reject**.

За прокси или с YouTrack на `localhost`: см. [docs/tools.md](docs/tools.md#network).

## Пример

Полная сессия на настоящем YouTrack: диалог, таблица ранжирования, как читать каждый столбец и
расчёт; воспроизводится одной командой: [docs/example.md](docs/example.md) (на английском).

## Что читается из YouTrack

| Сигнал | Откуда в YouTrack |
|---|---|
| status | поле `State` |
| story_points | поле `Story points`; если пусто — `Estimation` (период) ÷ 8 ч с пометкой `time_estimate_fallback` |
| evidence_found_in_text | в описании ссылка на Confluence / Google Docs, слово «evidence» или ссылка на **принятый** ADR вашего репозитория |
| adr_refs | упоминания `docs/adr/NNNN-*.md` / `ADR-15`, сверенные с вашей папкой ADR (принят, предложен, заменён, отсутствует) |
| triage | `Type`, `Priority`, теги, `Subsystem(s)`, `Due Date`, максимальный CVSS в названии и описании |

## Безопасность

- **Только чтение:** сервер отправляет только `GET`; используйте токен учётной записи без права записи.
- **Prompt injection:** описания задач пишет кто угодно с доступом к трекеру, поэтому они модели не
  передаются, только извлечённые типизированные сигналы.
- **Человек в контуре:** навык никогда не применяет ранжирование сам; каждый отчёт заканчивается Approve / Reject.
- **stdout — канал MCP:** все логи идут в stderr.

Подробности и сообщение об уязвимостях: [SECURITY.md](SECURITY.md).

## Разработка

Java 25 + Maven, Python 3.10+, Docker.

```bash
mvn verify                                                     # модульные, WireMock-IT (Testcontainers), E2E по STDIO
python3 -I -m unittest discover -s skills/backlog-prioritization-engine/scripts
python3 -I -m unittest discover -s evals/golden                # пайплайн эвалов Golden Dataset (без LLM)
docker build -t backlog-mcp-prioritizer . && python3 e2e/docker_smoke.py backlog-mcp-prioritizer
```

Настоящий YouTrack в Docker для контрактной проверки: [e2e/youtrack-sandbox](e2e/youtrack-sandbox/README.md).
Живые эвалы агента (NDCG@10, соблюдение правил, отказы, ветка Reject; тратят токены LLM):
[evals/golden](evals/golden/README.md). Архитектурные решения: [docs/adr](docs/adr).
Тег `v*` публикует релиз (jar, архив навыков, контрольные суммы) и мультиархитектурный образ в ghcr.io.
См. [CONTRIBUTING.md](CONTRIBUTING.md).

## Лицензия

[MIT](LICENSE)
