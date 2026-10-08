# EPG для Roku (GitHub Actions + GitHub Pages)

Каждые 3 часа скачивает XMLTV (по умолчанию `https://iptvx.one/epg/epg.xml.gz`), оставляет только каналы из вашего плейлиста и публикует компактный JSON:

- `epg/now.json` — что идёт сейчас и в ближайшие 6 часов, для всех каналов;
- `epg/c/<tvg-id>.json` — программа одного канала на всю глубину архива и на 2 дня вперёд.

## Настройка (один раз)

1. Создайте **публичный** репозиторий (например, `roku-epg`) и загрузите в него эти файлы.
2. *Settings → Secrets and variables → Actions → New repository secret*:
   `PLAYLIST_URL` = ссылка на ваш плейлист с токеном. Токен хранится только в секрете и в репозиторий не попадает.
3. (Необязательно) *Variables → New variable* `EPG_URLS` — другой источник XMLTV или несколько через запятую.
4. *Settings → Pages → Source: GitHub Actions*.
5. *Actions → Build EPG for Roku → Run workflow*. После успешного запуска гид доступен по адресу
   `https://<ваш-логин>.github.io/roku-epg/epg/now.json`.
6. В Roku-канале в `source/config.brs` укажите
   `epgBase: "https://<ваш-логин>.github.io/roku-epg/epg/"`.

Заметка: GitHub отключает запуски по расписанию в репозитории, где 60 дней не было коммитов. Если гид перестал обновляться, включите workflow снова на вкладке Actions.
