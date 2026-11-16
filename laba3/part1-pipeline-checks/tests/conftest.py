"""Общие фикстуры для тестов.

app.py при импорте сразу подключается к PostgreSQL и создаёт таблицу notes,
поэтому для тестов нужна живая база. В CI её поднимает service-контейнер,
локально — `docker compose up -d` из папки laba0.
"""

import pytest

import app as app_module


@pytest.fixture
def client():
    # Каждый тест начинает с пустой таблицы и id с единицы.
    with app_module.db_cursor() as cur:
        cur.execute("TRUNCATE notes RESTART IDENTITY")
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client
