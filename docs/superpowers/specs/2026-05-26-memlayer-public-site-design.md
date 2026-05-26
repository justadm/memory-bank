# MemLayer Public Site Design

Дата: 2026-05-26

## Goal

Подготовить публичную статическую витрину для:

- `https://memlayer.ru`
- `https://memlayer.ru/api`

Сайт должен кратко объяснять, что такое MemLayer, показывать curated sections из `README.md`, давать статические API examples с one-click copy и не светить приватные operational endpoints вроде `adm.memlayer.ru`.

## Scope

### `memlayer.ru`

Главная страница:

- hero с коротким positioning MemLayer
- несколько curated documentation sections, основанных на текущем `README.md`
- code blocks с кнопкой copy
- шапка с публичными ссылками:
  - `Docs`
  - `API`
  - `GitHub`

Ссылка на `adm.memlayer.ru` на этом этапе не показывается.

### `memlayer.ru/api`

Отдельная статическая docs-страница:

- набор безопасных примеров вызова API
- placeholders вроде `YOUR_API_KEY`
- без live OpenAPI
- без ссылок на production `/openapi.json`
- без operational/admin-only примеров, которые не должны светиться наружу

## UX

### Code Blocks

Каждый ключевой snippet получает copy button по аналогии с GitHub-like docs UX:

- один клик копирует весь command block
- краткий visual feedback (`Copied`)

### Theme

Theme switcher не является обязательной самостоятельной фичей, но допускается, если:

- реализуется лёгким JS
- поддерживает `Auto / Light / Dark`
- не усложняет runtime

### Navigation

Публичная навигация:

- `memlayer.ru/`
- `memlayer.ru/api`
- GitHub repo

Закрытые internal links не публикуются.

## Content Strategy

Страница не должна быть mechanical dump всего `README.md`.

Нужно взять и перепаковать только полезные публичные блоки:

- что такое MemLayer
- key capabilities
- retrieval / quality / imports / operator workflows в краткой форме
- quick start examples

Нужно убрать или не выносить в hero-level:

- локальные `memlayer.loc` детали
- внутренние rollout-хвосты
- host-specific `/Users/...` примеры
- admin-only operational surface

## Technical Shape

Рекомендуемый shape:

- отдельные статические assets в репозитории
- отдельный nginx vhost для `memlayer.ru`
- статическая раздача с host nginx на `msk`
- не смешивать landing с `adm.memlayer.ru` runtime

Рекомендованная файловая структура:

```text
deploy/msk/site/
  index.html
  api/index.html
  styles.css
  site.js
```

Дополнительно:

- отдельный nginx sample config для `memlayer.ru`

## Security

Публичная страница не должна:

- показывать `adm.memlayer.ru`
- ссылаться на live production OpenAPI
- подставлять реальные API keys
- содержать admin runtime commands

Допустимы только безопасные публичные examples с placeholder secret values.

## Recommendation

Делать простой статический сайт с:

- curated docs content
- copyable command blocks
- отдельной `/api` страницей
- лёгким theme switcher `Auto / Light / Dark`, если он не вносит лишнюю сложность

Это даст нормальную публичную витрину для `memlayer.ru` без смешивания с private console/runtime.
