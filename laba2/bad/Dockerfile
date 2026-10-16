# ПЛОХОЙ Dockerfile: ошибки сделаны специально, для сравнения с хорошим (лаба 2)

# [BAD 1] Нет тега, берётся python:latest. Полный образ где-то 1 ГБ, и завтра под latest может оказаться другая версия Python.
FROM python

WORKDIR /app

# [BAD 2] Нет .dockerignore, COPY . . тащит в образ всё подряд, включая venv.
# [BAD 3] Код копируется ДО установки библиотек -> любая правка app.py ломает кеш, и pip install выполняется заново.
COPY . .

RUN pip install -r requirements.txt

# [BAD 4] Нет USER, приложение работает от root.
CMD ["python", "app.py"]
