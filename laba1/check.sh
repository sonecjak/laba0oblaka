#!/bin/bash

echo 'HTTP → HTTPS: ожидаем 301'
curl -sSI --max-time 10 http://localhost/

echo 'Фронтенд, docs, admin без пароля и своя 404'
for path in / /docs/ /admin/ /no-such-page; do
  echo "Путь: $path"
  curl -ksi --max-time 10 "https://localhost$path"
  echo
done

echo 'Второй проект: ожидаем 200 и его страницу'
curl -ksi --max-time 10 --resolve project2.local:443:127.0.0.1 \
  https://project2.local/

echo 'Неизвестный Host: ожидаем Empty reply'
curl -sSi --max-time 10 -H 'Host: unknown.local' http://127.0.0.1/

echo 'Балансировка: ожидаем 200 и оба идентификатора'
sleep 3
for i in {1..6}; do
  curl -ksS --max-time 10 -D - -o /dev/null https://localhost/api/notes |
    grep -Ei 'HTTP/|X-Backend-Id'
  sleep 1
done

echo 'Лимит запросов: ожидаем появление 429'
for i in {1..30}; do
  curl -ksS --max-time 10 -o /dev/null -w '%{http_code}\n' \
    https://localhost/api/notes
done

echo 'Останови backend-1 на 5001 через Control+C в его вкладке.'
read -r -p 'Вернись сюда и нажми Enter: '
sleep 3

echo 'Остановленный бэкенд: ожидаем ошибку подключения'
curl -sS --max-time 3 http://127.0.0.1:5001/api/notes

echo 'Отказоустойчивость: ожидаем 200 от backend-2'
for i in {1..6}; do
  curl -ksS --max-time 10 -D - -o /dev/null https://localhost/api/notes |
    grep -Ei 'HTTP/|X-Backend-Id'
  sleep 1
done
