# Лаба 2 — хороший Docker-образ (наша часть)

Этот каталог добавляется **рядом с `laba2/bad`**; плохой образ не изменяется.
Весь исходный код взят из `laba0`: `app.py` (Flask) и `frontend/index.html`.
В `requirements.txt` зафиксированы прямые зависимости.

## Что исправлено

1. **База:** `python:3.13.15-slim-bookworm` вместо `python` без версии.
2. **Multi-stage:** зависимости устанавливаются в отдельном `builder`, затем копируются в `runtime`.
3. **Кеш:** сначала `COPY requirements.txt`, затем `pip install`, а `app.py` копируется только в финальном этапе.
4. **Безопасность:** `.dockerignore` исключает venv, кеши, `.env` и Git. Копируются только необходимые файлы.
5. **Права:** процесс запускается от `appuser`, а не от `root`.
6. **Надёжность:** `HEALTHCHECK` обращается к `/api/health` стандартной библиотекой Python, без `curl`.
7. **Полнота сервиса:** сохранён HTML-фронтенд: путь `/app/frontend/index.html` совместим с `static_folder="../frontend"` в `app.py`.

## 1. Поднять PostgreSQL

Из **корня репозитория**:

```powershell
cd laba0
docker compose up -d
cd ..
```

Для связи контейнера с PostgreSQL на Docker Desktop используется `host.docker.internal`. На обычном Linux для `docker run` дополнительно потребуется `--add-host=host.docker.internal:host-gateway`.

## 2. Собрать хороший образ

Из **корня репозитория**:

```powershell
cd laba2/good
docker build -t notes-good .
docker images notes-good
```

## 3. Запустить и проверить

```powershell
docker run -d --name notes-good -p 5001:5000 -e DB_HOST=host.docker.internal notes-good
docker ps
docker exec notes-good whoami
docker exec notes-good ls -la /app/backend
docker inspect --format '{{.State.Health.Status}}' notes-good
```

Ожидаемое имя пользователя — **appuser**; каталог приложения не должен содержать `venv` и `Dockerfile`. Healthcheck станет `healthy`, когда запустится Flask и будет доступна БД (в первое время может быть `starting`).

**В PowerShell** проверить API:

```powershell
curl.exe http://localhost:5001/api/health
```

**В macOS/Linux**:

```bash
curl http://localhost:5001/api/health
```

Открыть http://localhost:5001/ — должна появиться форма «Заметки».

Если порт 5001 занят, заменить только левую часть `-p`, например `-p 5002:5000`.

## 4. Замерить пересборку после изменения кода

Из каталога `laba2/good`.

**PowerShell (Windows)**, сначала без изменений:

```powershell
Measure-Command { docker build --progress=plain -t notes-good . | Out-Default }
```

Добавить в конец `app.py` комментарий, затем запустить **ту же** команду снова:

```powershell
Add-Content app.py '# правка для замера кеша'
Measure-Command { docker build --progress=plain -t notes-good . | Out-Default }
```

**macOS / Linux**:

```bash
time docker build --progress=plain -t notes-good .
echo '# правка для замера кеша' >> app.py
time docker build --progress=plain -t notes-good .
```

В выводе `RUN pip install -r requirements.txt` должен быть **CACHED** после правки кода, потому что зависимости не менялись. Сопоставить длительность с измерением плохого образа, выполненным на **том же компьютере** по возможности при одинаковых условиях. Восстановить исходный `app.py` после теста, удалив добавленный комментарий.

## 5. Что сдавать (наша часть)

- `Dockerfile` хорошего образа;
- `.dockerignore`;
- снимок размера из `docker images notes-good` (или аналогичного вывода Docker Desktop);
- `docker exec notes-good whoami` (`appuser`);
- скрин `docker inspect ...Health.Status` (`healthy`) и успешный `/api/health`;
- время пересборки после правки одной строки, где `pip install` остаётся в кеше;
- короткое объяснение каждой исправленной плохой практики.

**Важно:** здесь нет фактических результатов размера/скорости: их необходимо измерить в Docker на вашей машине. В среде подготовки файлов Docker Engine недоступен.
