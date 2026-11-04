# hosts-merger

Склеивает hosts-файлы нескольких издателей + локальные фиксы из сообщества
в один чистый файл, сгруппированный по сервисам и IP (секции `# === OpenAI (malw.link) ===`,
`# === GeoHideDNS RU: 159.194.200.33 (1023 domains) ===` и т.д.).

Дубликаты убираются, конфликты (один домен → разные IP у издателей) решаются
в пользу источника выше по списку.

## Источники (по приоритету, `sources.txt`)

1. `spotify_hosts.txt` — Spotify-фикс из треда Flowseal/zapret-discord-youtube#5552 (→ GeoHide EU 5.175.161.3)
2. `roblox_hosts.txt` — иконки/картинки Roblox (треды #16296, #16332, 15 запасных IP в комментах)
3. `supercell_hosts.txt` — Supercell-игры (Clash, Brawl Stars, Hay Day, Squad Busters) из списков панели GeoHideDNS (→ GeoHide RU)
4. malw.link — реальные IP сервисов (OpenAI, Instagram, Microsoft/Copilot/Xbox, TikTok...) + блокировка рекламы
5. GeoHideDNS (RU регион) — ~1000 доменов через их прокси-серверы

## Файлы

| Файл | Что делает |
|---|---|
| `merge_hosts.py` | Скачивает источники, склеивает, дедуплицирует, группирует → `hosts` |
| `sources.txt` | Список источников, один в строке, сверху = высший приоритет |
| `spotify_hosts.txt` / `roblox_hosts.txt` / `supercell_hosts.txt` | Локальные фиксы сообщества |
| `apply_hosts.ps1` | Вставляет `hosts` в системный файл (маркерный блок или `-Replace` — полная замена), бэкап + очистка DNS |
| `update-hosts.bat` | merge + apply одной кнопкой (правый клик → Run as administrator) |
| `.github/workflows/merge-hosts.yml` | GitHub Actions: пересборка каждые 6 часов |

## Автообновление на GitHub

1. Пустой публичный репозиторий (например `hosts-merged`).
2. Загрузить все файлы этой папки, включая `.github/workflows/merge-hosts.yml`.
3. Actions включится сам → каждые 6 часов свежий `hosts` коммитится в репо.
4. Постоянная ссылка на файл: `https://raw.githubusercontent.com/USER/REPO/main/hosts`

## Локально на Windows

`update-hosts.bat` от администратора. Расписание (по желанию):

```
schtasks /Create /TN "UpdateHosts" /SC HOURLY /RL HIGHEST /TR "cmd /c cd /d C:\Users\koski\ZCodeProject\hosts-merger && update-hosts.bat"
```

Откат: бэкапы `hosts.bak.<дата>` рядом с системным hosts (хранятся последние 5).
