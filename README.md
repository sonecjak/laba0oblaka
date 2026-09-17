# Лаба 0 — свой сервис

Простое приложение "Заметки":
- **Backend**: Python (Flask) — `backend/app.py`
- **Frontend**: одна HTML-страница с формой и списком — `frontend/index.html`
- **DB**: PostgreSQL (отдельный сервис, поднимается через Docker)

## Как устроено

Фронтенд ходит в бэкенд по адресам:
- `GET /api/notes` — получить список заметок из базы
- `POST /api/notes` — сохранить новую заметку в базу

Бэкенд подключается к PostgreSQL по сети (хост/порт из переменных окружения) и делает обычные SQL-запросы через `psycopg2`.

## Как запустить

### 1. Поднять базу данных

Нужен установленный Docker.

```bash
docker compose up -d
```

Это поднимет PostgreSQL на `localhost:5432` с базой `lab0`, пользователем `lab0` и паролем `lab0`.

### 2. Установить зависимости бэкенда

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # на Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Запустить бэкенд

```bash
python app.py
```

Приложение поднимется на **http://localhost:5000** и само отдаёт фронтенд.

### 4. Проверка работоспособности

1. Открыть http://localhost:5000
2. Ввести текст в поле и нажать "Добавить"
3. Заметка появится в списке
4. Перезагрузить страницу (F5) — заметка должна остаться на месте, потому что она реально сохранена в PostgreSQL

## Остановка

```bash
docker compose down       # остановить базу (данные сохранятся в volume)
```

## Структура проекта

```
lab0-service/
├── backend/
│   ├── app.py            # Flask-приложение
│   └── requirements.txt
├── frontend/
│   └── index.html        # форма + список
├── docker-compose.yml     # PostgreSQL
└── README.md
```
