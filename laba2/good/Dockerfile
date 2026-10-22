# Лаба 2: хороший образ приложения "Заметки"
# Этап 1. Устанавливаем зависимости в отдельное виртуальное окружение.
# Версия Python и дистрибутив указаны явно, без latest.
FROM python:3.13.15-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Сначала зависимости: правки app.py не сбрасывают кеш pip install.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Этап 2. Маленький образ для запуска — без файлов сборки.
FROM python:3.13.15-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Приложение не должно работать от root.
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

# Путь выбран с учётом static_folder="../frontend" в app.py.
WORKDIR /app/backend
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup app.py ./
COPY --chown=appuser:appgroup frontend/index.html /app/frontend/index.html

USER appuser
EXPOSE 5000

# Проверяем именно /api/health (этот маршрут также обращается к PostgreSQL).
# В slim-образе нет curl, поэтому используем стандартную библиотеку Python.
HEALTHCHECK --interval=30s --timeout=5s --start-period=75s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3).close()"

CMD ["python", "app.py"]
