# MSK Server Inventory

Дата: 2026-05-26  
Хост: `msk`  
Назначение документа: единая сводка по проектам, Docker runtime, nginx routing и найденным источникам описания на сервере.

Remote convenience copy for bots:

- `/home/opsadmin/SERVER_INVENTORY.md`

## 1. Базовая структура хоста

Пользовательский корень:

- `/home/opsadmin`

Основные видимые каталоги/артефакты:

- `/home/opsadmin/APUAI`
- `/home/opsadmin/adcrew`
- `/home/opsadmin/jstun-deploy_msk.sh`
- `/home/opsadmin/jstun-docker-compose.yml`
- `/home/opsadmin/wg.devee.ru`

Дополнительные системные зоны:

- `/etc/nginx`
- `/opt/jstun`

## 2. Основные проектные корни

### 2.1. Jstun

Рабочий runtime root:

- `/opt/jstun`

Что лежит в корне:

- `.env`
- `docker-compose.yml`
- `docs/`
- `monitoring/`
- `scripts/`
- `.deploy-meta`

Вывод:

- Для `jstun` основным рабочим каталогом является именно `/opt/jstun`, а не `/home/opsadmin`.
- `/home/opsadmin/jstun-docker-compose.yml` и `/home/opsadmin/jstun-deploy_msk.sh` выглядят как вспомогательные/операционные артефакты для deploy и обзора.

### 2.2. AdCrew

Рабочий корень:

- `/home/opsadmin/adcrew`

Что есть:

- `.docs/`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `deploy/`
- `scripts/`
- `api/`
- `web/`
- `workers/`

### 2.3. APUAI

Рабочий корень:

- `/home/opsadmin/APUAI`

Что есть:

- `docs/`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `app/`
- `scripts/`
- `tests/`
- `reports/`

## 3. Docker runtime

На момент осмотра на хосте были подняты следующие заметные контуры.

### 3.1. Jstun / TUN-related

- `jstun-portal-1`
- `jstun-control-api-1`
- `jstun-postgres-1`
- `tun-monitoring-api`
- `tun-monitoring-ingestor`
- `tun-monitoring-postgres`

Порты:

- `127.0.0.1:18095 -> jstun portal`
- `127.0.0.1:18110 -> jstun control api`
- `127.0.0.1:15432 -> jstun postgres`
- `0.0.0.0:18070 -> monitoring api`
- `0.0.0.0:18071 -> monitoring ingestor`
- `0.0.0.0:15433 -> monitoring postgres`

### 3.2. AdCrew

- `adcrew-api-1`
- `adcrew-postgres-1`
- `adcrew-web_public-1`
- `adcrew-web_app-1`
- `adcrew-web_admin-1`

Порты:

- `127.0.0.1:18181 -> api`
- `127.0.0.1:18090 -> public web`
- `127.0.0.1:18091 -> app web`
- `127.0.0.1:18092 -> admin web`

### 3.3. ChatMarketAI

- `chatmarketai-api`
- `chatmarketai-frontend`
- `chatmarketai-outbox-worker`
- `chatmarketai-postgres`
- `chatmarketai-redis`

Порты:

- `127.0.0.1:28000 -> backend`
- `127.0.0.1:28100 -> frontend`

### 3.4. Domens

- `domens-api-1`
- `domens-frontend-1`
- `domens-postgres-1`
- `domens-redis-1`

Порты:

- `127.0.0.1:28080 -> api`
- `127.0.0.1:28200 -> frontend`
- `127.0.0.1:5432 -> postgres`
- `127.0.0.1:6379 -> redis`

### 3.5. GridAI

- `gridai-web`
- `gridai-bot`
- `gridai-frontend`
- `gridai-monitor`

Порты:

- `127.0.0.1:13080 -> frontend nginx`

### 3.6. Другие контуры

- `whatsapp-receiver-docker-*`
- `bx24pg-*`
- `justgpt-control-plane-*`
- `deploy-mcp_*`
- `glavpro-*`

Вывод:

- Хост используется как мультипроектный docker runtime.
- Основная схема публикации: контейнеры слушают `127.0.0.1:<port>`, а внешний доступ организован через nginx.

## 4. Nginx routing

### 4.1. Конфиги

Основные директории:

- `/etc/nginx/sites-available`
- `/etc/nginx/sites-enabled`
- `/etc/nginx/conf.d`

Активные домены по `sites-enabled`:

- `adcrew.pro`
- `b24-test.devee.ru`
- `bot.devee.ru`
- `bx24.devee.ru`
- `glavpro.devee.ru`
- `gridai.ru`
- `hr.devee.ru`
- `idns.devee.ru`
- `jstmarket.ru`
- `jstun.com`
- `justgpt.ru.http`
- `justgpt.ru.https`
- `market.devee.ru`
- `max.devee.ru`
- `sms.devee.ru`
- `wg.devee.ru`

### 4.2. Jstun routing

Файл:

- `/etc/nginx/sites-enabled/jstun.com`

Что делает:

- `id.jstun.com`
- `lk.jstun.com`
- `api.jstun.com`
- `admin.jstun.com`
- `app.jstun.com`

Все эти subdomain-ы проксируются на:

- `http://127.0.0.1:18095`

Дополнительно:

- `jstun.com`, `www.jstun.com`, `jstun.ru`, `www.jstun.ru` редиректятся на `https://jstun.ru`
- wildcard `*.jstun.com` тоже редиректится на `https://jstun.ru`

Вывод:

- Снаружи `jstun` выглядит как многодоменный портал, но текущий nginx-файл сводит пользовательские subdomain-ы к одному upstream на `18095`.

### 4.3. WG routing

Файл:

- `/etc/nginx/sites-enabled/wg.devee.ru`

Upstream:

- `http://10.200.0.4:18090`

Особенности:

- `/admin/` проксируется туда же
- для `/new/` и `/lk/login/` включены rate limits

Вывод:

- `wg.devee.ru` не указывает на локальный docker port на `127.0.0.1`, а идёт на внутренний адрес `10.200.0.4:18090`
- это отдельный признак того, что часть WG/Jstun topology разнесена по внутренней сети, а не полностью живёт в одном compose-контуре

### 4.4. bot.devee.ru

Файл:

- `/etc/nginx/sites-enabled/bot.devee.ru`

Маршруты:

- `/alice/` -> `127.0.0.1:3002`
- `/gateway` -> `127.0.0.1:8000`
- `/` -> `127.0.0.1:8000`

Замечание:

- Конфиг содержит жёстко прописанные bearer/token headers для OpenClaw
- по текущему комментарию пользователя этот контур, вероятно, уже исторический и требует валидации на актуальность

## 5. Домены и upstream-карта

| Domain / host | Nginx config | Upstream | Container / runtime | Project root | Status |
| --- | --- | --- | --- | --- | --- |
| `adcrew.pro` | `/etc/nginx/sites-enabled/adcrew.pro` | `127.0.0.1:18090` | `adcrew-web_public-1` | `/home/opsadmin/adcrew` | `active` |
| `api.adcrew.pro` | `/etc/nginx/sites-enabled/adcrew.pro` | `127.0.0.1:18181` | `adcrew-api-1` | `/home/opsadmin/adcrew` | `active` |
| `app.adcrew.pro`, `lk.adcrew.pro` | `/etc/nginx/sites-enabled/adcrew.pro` | `127.0.0.1:18091`, `/bff/ -> 127.0.0.1:18181/api/v1/` | `adcrew-web_app-1`, `adcrew-api-1` | `/home/opsadmin/adcrew` | `active` |
| `admin.adcrew.pro`, `adm.adcrew.pro` | `/etc/nginx/sites-enabled/adcrew.pro` | `127.0.0.1:18092` | `adcrew-web_admin-1` | `/home/opsadmin/adcrew` | `active` |
| `jstun.com`, `id.jstun.com`, `lk.jstun.com`, `api.jstun.com`, `admin.jstun.com`, `app.jstun.com` | `/etc/nginx/sites-enabled/jstun.com` | `127.0.0.1:18095` | `jstun-portal-1` | `/opt/jstun` | `active` |
| `wg.devee.ru` | `/etc/nginx/sites-enabled/wg.devee.ru` | `10.200.0.4:18090` | internal upstream behind local nginx; not local `127.0.0.1` docker publish | `unclear`, operationally tied to Jstun/WG contour | `active` |
| `market.devee.ru` | `/etc/nginx/sites-enabled/market.devee.ru` | `127.0.0.1:28100`, `/api|/webhooks|/static|/healthz -> 127.0.0.1:28000` | `chatmarketai-frontend`, `chatmarketai-api` | `unclear` | `active` |
| `jstmarket.ru`, `lk.jstmarket.ru`, `admin.jstmarket.ru` | `/etc/nginx/sites-enabled/jstmarket.ru` | `127.0.0.1:28100`, API/static/health via `127.0.0.1:28000` | `chatmarketai-frontend`, `chatmarketai-api` | `unclear` | `active` |
| `api.jstmarket.ru`, `auth.jstmarket.ru` | `/etc/nginx/sites-enabled/jstmarket.ru` | same ChatMarketAI contour; exact host behavior should be revalidated against full file/runtime | `chatmarketai-*` | `unclear` | `active / partial-unclear` |
| `idns.devee.ru` | `/etc/nginx/sites-enabled/idns.devee.ru` | `127.0.0.1:28200`, `/v1|/docs|/openapi.json|/health -> 127.0.0.1:28080` | `domens-frontend-1`, `domens-api-1` | `unclear` | `active` |
| `bx24.devee.ru` | `/etc/nginx/sites-enabled/bx24.devee.ru` | `127.0.0.1:28310` | `bx24pg-web` | `unclear` | `active` |
| `glavpro.devee.ru` | `/etc/nginx/sites-enabled/glavpro.devee.ru` | `127.0.0.1:18080` | `glavpro-joomla-1` | `unclear` | `active` |
| `sms.devee.ru` | `/etc/nginx/sites-enabled/sms.devee.ru` | `127.0.0.1:18096` | `whatsapp-receiver-docker-app-1` | `unclear` | `active` |
| `gridai.ru`, `www.gridai.ru`, `auth.gridai.ru`, `career.gridai.ru`, `hiring.gridai.ru`, `admin.gridai.ru`, `api.gridai.ru` | `/etc/nginx/sites-enabled/gridai.ru` | `127.0.0.1:13001`, `/legacy/ -> 127.0.0.1:13080` | `gridai-frontend` confirms `13080`; runtime behind `13001` was not matched to a published docker port during inspection | `unclear` | `active / partial-unclear` |
| `hr.devee.ru` | `/etc/nginx/sites-enabled/hr.devee.ru` | `127.0.0.1:13001`, `/api|/oauth -> 127.0.0.1:13001`, `/legacy/ -> 127.0.0.1:13080` | same contour as `gridai.ru`; `13001` runtime not directly identified in `docker ps` | `unclear` | `active / partial-unclear` |
| `justgpt.ru`, `www.justgpt.ru` | `/etc/nginx/sites-enabled/justgpt.ru.https` | static `200 OK` response | nginx-only health/landing stub | `unclear` | `active` |
| `app.justgpt.ru`, `api.justgpt.ru` | `/etc/nginx/sites-enabled/justgpt.ru.https` | `127.0.0.1:19100` | local JustGPT control-plane runtime | `unclear` | `active` |
| `mcp.justgpt.ru` | `/etc/nginx/sites-enabled/justgpt.ru.https` | `127.0.0.1:19001..19015` depending on `/p/*/mcp` path | local multi-upstream MCP runtime | `unclear` | `active` |
| `max.devee.ru` | `/etc/nginx/sites-enabled/max.devee.ru` | `127.0.0.1:8000` | no matching published docker port found during inspection | `unclear` | `unclear` |
| `b24-test.devee.ru` | `/etc/nginx/sites-enabled/b24-test.devee.ru` | `127.0.0.1:3010` | no matching published docker port found during inspection; protected by basic auth | `unclear` | `unclear` |
| `bot.devee.ru` | `/etc/nginx/sites-enabled/bot.devee.ru` | `/alice/ -> 127.0.0.1:3002`, `/gateway|/ -> 127.0.0.1:8000` | legacy OpenCrew-era endpoints; live runtime not revalidated | `unclear` | `legacy / unclear` |

Примечания к таблице:

- `project root = unclear` означает, что nginx и/или Docker contour удалось подтвердить, но однозначный filesystem root на хосте не был найден за текущий проход.
- `active / partial-unclear` означает, что домен и nginx-маршруты выглядят рабочими, но часть runtime-сопоставления ещё требует второго прохода.
- Для `jstun` внешний ingress (`127.0.0.1:18095`) и внутренний control API (`127.0.0.1:18110`) живут в одном `/opt/jstun` контуре, но nginx наружу отдаёт только порталный слой.

## 6. Найденные документы и runbook-источники

### 6.1. AdCrew

Самый оформленный ops-doc:

- `/home/opsadmin/adcrew/.docs/support-runbook-ru.md`

Что в нём есть:

- архитектура
- health/ready точки
- env-ключи
- ежедневная эксплуатация
- частые инциденты
- deploy/update/rollback

Вывод:

- Для AdCrew есть нормальный локальный runbook.

### 6.2. APUAI

Найдены:

- `/home/opsadmin/APUAI/docs/01_overview.md`
- `/home/opsadmin/APUAI/docs/02_architecture.md`

Это:

- обзор сервиса
- архитектурная схема пайплайна

Вывод:

- Для APUAI есть описание самого продукта/сервиса, но не общая схема всего хоста.

### 6.3. Jstun

Главный найденный источник по эксплуатации:

- `/home/opsadmin/jstun-deploy_msk.sh`

Ключевые факты из него:

- основной remote dir: `/opt/jstun`
- deploy идёт по commit SHA
- preflight проверяет `.env`
- миграции запускаются через `docker compose --profile migrate up migrate`
- сервисы поднимаются через `docker compose up -d --build portal control-api`
- есть post-deploy smoke и boundary smoke

Вывод:

- Для `jstun` роль runbook сейчас выполняет deploy script, а не отдельный markdown inventory.

## 7. Что выглядит как источник истины сейчас

Если нужен реальный operational source of truth по `msk`, то на текущий момент это:

1. `docker ps`
2. `/etc/nginx/sites-enabled/*`
3. project roots:
   - `/opt/jstun`
   - `/home/opsadmin/adcrew`
   - `/home/opsadmin/APUAI`
4. deploy/runbook files:
   - `/home/opsadmin/jstun-deploy_msk.sh`
   - `/home/opsadmin/adcrew/.docs/support-runbook-ru.md`
   - `/home/opsadmin/APUAI/docs/*`

## 8. Пробелы inventory

Что не найдено в виде одного готового документа:

- единый список “какой проект где деплоится и каким способом”
- единая маркировка исторических/неактуальных контуров вроде `bot.devee.ru`

## 9. Практические выводы

- `msk` — это мультисервисный ingress/runtime host
- `jstun` живёт отдельно в `/opt/jstun` и выглядит как отдельный основной продуктовый контур
- `adcrew` и `APUAI` живут в `/home/opsadmin/*`
- nginx на этом хосте — важнейший слой навигации по системе; без него инвентаризация неполна
- часть маршрутов (`wg.devee.ru`) ведёт не на локальный контейнерный `127.0.0.1`, а на внутренний адрес `10.200.0.4`, что важно для диагностики
- `bot.devee.ru` требует отдельной валидации на актуальность, потому что конфиг ещё жив, но пользовательский контур, по словам пользователя, уже снят

## 10. Что логично сделать дальше

1. Отдельно разобрать `jstun`:
   - как соотносятся `wg.devee.ru`, `jstun.com`, `127.0.0.1:18095`, `127.0.0.1:18110` и `10.200.0.4:18090`
2. Досопоставить filesystem roots для контуров с `project root = unclear`:
   - `ChatMarketAI`
   - `Domens`
   - `GridAI / hr.devee.ru`
   - `JustGPT`
3. Отдельно почистить legacy-контуры:
   - `bot.devee.ru`
   - возможно старые backup nginx-конфиги, если они уже не нужны как операционный reference
