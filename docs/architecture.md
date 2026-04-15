# Архитектура системы мониторинга сервисов

## Назначение

Система мониторинга REST-эндпоинтов для СБЕР. По расписанию проверяет доступность сервисов, хранит историю проверок, считает SLA и отправляет email-уведомления ответственным при падении сервиса.

---

## C4-диаграмма (уровень контейнеров)

```mermaid
C4Container
  title Система мониторинга сервисов — уровень контейнеров

  Person(user, "Пользователь / Оператор", "Настраивает сервисы, просматривает SLA и историю через REST API")

  System_Boundary(monitoring, "Система мониторинга") {
    Container(api, "FastAPI Application", "Python 3.12, FastAPI", "Обрабатывает REST-запросы: CRUD сервисов, управление планировщиком, отчёты SLA")
    Container(scheduler, "APScheduler", "APScheduler AsyncIOScheduler", "Запускает проверки по расписанию (CHECK_INTERVAL_SECONDS). Интегрирован в lifespan FastAPI")
    Container(checker, "HTTP Checker", "httpx (async)", "Выполняет HTTP GET к эндпоинтам. Определяет доступность по статус-коду. Таймаут: CHECKER_TIMEOUT_SECONDS")
    Container(notifier, "Email Notifier", "smtplib / FastMail", "Отправляет email при переходе DOWN и при восстановлении UP. Хранит состояние in-memory")
    ContainerDb(db, "PostgreSQL 16", "PostgreSQL", "Хранит сервисы, эндпоинты, результаты проверок, SLA-конфиг, ответственных лиц")
  }

  System_Ext(smtp, "SMTP-сервер / MailHog", "Принимает и хранит email-уведомления. В dev-окружении — MailHog на порту 8025")
  System_Ext(test_service, "Test Service", "Отдельный FastAPI-сервис на порту 8001. Симулирует UP/DOWN/partial для демонстрации")
  System_Ext(monitored, "Monitored Endpoints", "Реальные REST-сервисы, доступность которых проверяется")

  Rel(user, api, "REST API", "HTTP/JSON, порт 8000")
  Rel(api, db, "Читает / пишет данные", "asyncpg / SQLAlchemy async")
  Rel(api, scheduler, "Старт / стоп / ручной триггер", "in-process")
  Rel(scheduler, checker, "Запускает проверку по расписанию", "async call")
  Rel(checker, db, "Записывает результат проверки", "asyncpg / SQLAlchemy async")
  Rel(checker, notifier, "Передаёт статус после проверки", "async call")
  Rel(checker, monitored, "HTTP GET", "httpx async")
  Rel(checker, test_service, "HTTP GET (в dev)", "httpx async")
  Rel(notifier, smtp, "Отправляет email", "SMTP, порт 1025 (MailHog) / 587 (prod)")
  Rel(notifier, db, "Читает список ответственных", "asyncpg / SQLAlchemy async")
```

---

## Границы модулей

```
app/
├── api/              # FastAPI роутеры — принимают HTTP-запросы, возвращают ответы
│   ├── services.py   #   CRUD: сервисы, эндпоинты, ответственные, SLA-конфиг
│   ├── monitoring.py #   Управление планировщиком: старт, стоп, ручной триггер
│   └── reports.py    #   Отчёты: история проверок, текущий SLA, дашборд
│
├── scheduler/        # APScheduler — инициализация, lifespan-интеграция, job-регистрация
│
├── checker/          # Движок HTTP-проверок
│   └── engine.py     #   check_endpoint(): выполняет запрос, определяет is_available
│
├── notifier/         # Email-уведомления
│   └── email.py      #   notify_down(), notify_recovery(); состояние last_notified in-memory
│
├── models/           # SQLAlchemy ORM-модели (таблицы БД)
├── schemas/          # Pydantic-схемы запросов (XxxRequest) и ответов (XxxResponse)
├── repositories/     # Слой доступа к БД (select/insert/update через AsyncSession)
├── db/               # SessionLocal, Base, get_db dependency
└── main.py           # Точка входа: создание app, подключение роутеров, lifespan
```

---

## Поток данных

### Плановая проверка эндпоинта

```mermaid
sequenceDiagram
  participant S as APScheduler
  participant C as HTTP Checker
  participant E as External Endpoint
  participant DB as PostgreSQL
  participant N as Notifier
  participant SMTP as SMTP / MailHog

  S->>C: run_check(endpoint_id, url)
  C->>E: GET {url} (timeout: CHECKER_TIMEOUT_SECONDS)
  alt HTTP 2xx / 3xx
    E-->>C: 200 OK
    C->>DB: INSERT check_results(is_available=True, status_code, response_time_ms)
    C->>N: on_result(endpoint_id, is_available=True)
    opt Был DOWN → теперь UP
      N->>DB: SELECT responsible WHERE service_id=...
      N->>SMTP: send recovery email
    end
  else HTTP 4xx / 5xx / Timeout / ConnectError
    E-->>C: 500 / timeout
    C->>DB: INSERT check_results(is_available=False, status_code or None, error_message)
    C->>N: on_result(endpoint_id, is_available=False)
    N->>DB: SELECT responsible WHERE service_id=...
    alt Первый DOWN или прошло > NOTIFY_REPEAT_MINUTES
      N->>SMTP: send down email
      N->>N: update last_notified[endpoint_id] = now()
    end
  end
```

### Конфигурация → первый цикл проверок

```mermaid
flowchart LR
  A([Оператор создаёт сервис\nPOST /services]) --> B([Добавляет эндпоинты\nPOST /services/#123;id#125;/endpoints])
  B --> C([Добавляет ответственных\nPOST /services/#123;id#125;/responsible])
  C --> D([Настраивает SLA-цель\nPUT /services/#123;id#125;/sla])
  D --> E{Планировщик\nзапущен?}
  E -- Нет --> F([POST /monitoring/start])
  F --> G([APScheduler\nstarts job])
  E -- Да --> G
  G --> H([Каждые CHECK_INTERVAL_SECONDS\nзапускается check cycle])
  H --> I([checker проверяет все\nактивные эндпоинты параллельно])
  I --> J([Результаты → БД\nСтатус → notifier])
```

---

## Технологический стек

| Слой | Технология | Назначение |
|------|-----------|------------|
| Web-фреймворк | FastAPI 0.11x | REST API, Swagger UI, dependency injection |
| ORM | SQLAlchemy 2.x (async) | Работа с БД через async-сессии |
| Миграции | Alembic | Версионирование схемы БД |
| Планировщик | APScheduler `AsyncIOScheduler` | Периодический запуск проверок |
| HTTP-клиент | httpx (async) | Проверка эндпоинтов |
| СУБД | PostgreSQL 16 | Хранение данных |
| Email | smtplib / FastMail | Отправка уведомлений |
| Логирование | structlog | Структурированные JSON-логи |
| Тесты | pytest, respx, testcontainers | Unit и интеграционные тесты |
| Линтеры | ruff, black, mypy | Качество и типизация кода |
| Инфраструктура | Docker Compose | Оркестрация: app, db, mailhog, test-service |

---

## Правила определения доступности

| Ответ эндпоинта | `is_available` | `status_code` | `error_message` |
|-----------------|---------------|--------------|----------------|
| HTTP 2xx / 3xx | `True` | код ответа | `null` |
| HTTP 4xx / 5xx | `False` | код ответа | `null` |
| `httpx.TimeoutException` | `False` | `null` | текст исключения |
| `httpx.ConnectError` | `False` | `null` | текст исключения |

---

## Расчёт SLA

```
sla_percent = (кол-во is_available=True за 30 дней / всего проверок за 30 дней) × 100
```

- Период: скользящие 30 дней от текущего момента
- Если проверок нет — возвращается `null`, не `0` и не `100`
- Целевой SLA: из `sla_config.target_percent`, дефолт `99.0`

Критичный индекс для производительности:
```sql
CREATE INDEX ix_check_results_endpoint_checked ON check_results(endpoint_id, checked_at);
```

---

## Логика уведомлений

```
Переход UP → DOWN:    отправить email DOWN немедленно
Продолжает DOWN:      повторный email, если прошло > NOTIFY_REPEAT_MINUTES
Переход DOWN → UP:    отправить email RECOVERY
```

Состояние `last_notified[endpoint_id]` хранится in-memory (сброс при рестарте — допустимо для MVP).

---

## Инфраструктура (Docker Compose)

```mermaid
graph LR
  subgraph compose["Docker Compose"]
    app["app\n:8000\nFastAPI + Scheduler"]
    db[("db\nPostgreSQL 16\n:5432")]
    mailhog["mailhog\nSMTP :1025\nUI :8025"]
    test["test-service\n:8001"]
  end

  app -- "asyncpg" --> db
  app -- "SMTP" --> mailhog
```

| Сервис | Порт | Назначение |
|--------|------|-----------|
| `app` | 8000 | FastAPI приложение + Swagger UI |
| `db` | 5432 | PostgreSQL 16 |
| `mailhog` | 1025 / 8025 | SMTP-приёмник / веб-интерфейс писем |
| `test-service` | 8001 | Тестовый сервис с симуляцией падений |
