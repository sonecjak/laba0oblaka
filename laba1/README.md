# Лаба 1 — nginx

# Вступление

<!-- СКРИН/КАРТИНКА В НАЧАЛО: images/00-intro.png -->

Задачей этой лабы было сделать из nginx точку входа и балансировщик перед нашим сервисом «Заметки» из Лабы 0, чтобы сайт жил, даже когда один из бэкендов упал.

# Что было сделано

Работаем с сервисом из Лабы 0 (Flask + PostgreSQL + HTML-страница) и ставим перед ним nginx. Он умеет следующее:

- работает по **HTTPS** с самоподписанным сертификатом, а **HTTP (80) перенаправляет на HTTPS (443)**;
- сам отдаёт статику фронтенда, а запросы на `/api` проксирует на бэкенд;
- **балансирует** `/api` между двумя копиями бэкенда (порты 5001 и 5002), а какой бэкенд ответил, видно по заголовку `X-Backend-Id`;
- отдаёт `/docs` из отдельной папки через **alias**;
- держит два **виртуальных хоста** (`localhost` и `project2.local`) и ничего не отдаёт на чужой `Host`;
- ограничивает частоту запросов на `/api` (**limit_req**);
- показывает **свою страницу 404**;
- закрывает `/admin` паролем (**auth_basic** + `htpasswd`).

Очень крутой милый nginx, который не боится, что у него отвалится бэкенд.

## Как устроено

```
браузер ──https──▶ nginx ──┬──▶ backend-1 (5001) ──┐
                           │                       ├──▶ PostgreSQL (5432)
                           └──▶ backend-2 (5002) ──┘
```

- запрос на `/` и другие страницы nginx обрабатывает сам (статика из `laba0/frontend`);
- запрос на `/api/...` nginx отправляет на один из двух бэкендов по очереди;
- если бэкенд не отвечает, nginx повторяет запрос на втором, и клиент ничего не замечает.

## Структура проекта

```
laba1/
├── nginx.conf        # главный конфиг
├── 404.html          # своя страница ошибки
├── check.sh          # скрипт проверок
├── .htpasswd         # логин/пароль для /admin (хеш)
├── ssl/
│   ├── nginx.crt     # самоподписанный сертификат
│   └── nginx.key
└── www/
    ├── admin/index.html   # то, что за паролем
    ├── docs/index.html    # отдаётся через alias
    └── site2/index.html   # второй виртуальный хост
```

## Как запустить

Прежде всего заходим в папку проекта!!

### 1. Поднять базу и два бэкенда

База из Лабы 0:

```bash
cd laba0
docker compose up -d
```

Дальше в **двух отдельных терминалах** запускаем бэкенды (в `app.py` уже были заготовлены переменные `PORT` и `INSTANCE_ID`, а также заголовок `X-Backend-Id`):

```bash
# терминал 1
cd laba0/backend
source venv/bin/activate      # на Windows: venv\Scripts\activate
export PORT=5001 INSTANCE_ID=backend-1
python app.py

# терминал 2 (запускаем, когда первый уже поднялся!)
cd laba0/backend
source venv/bin/activate
export PORT=5002 INSTANCE_ID=backend-2
python app.py
```

Почему второй запускаем позже, написано в «Граблях».

Проверяем, что оба живы:

```bash
curl http://localhost:5001/api/health   # {"backend":"backend-1","status":"ok"}
curl http://localhost:5002/api/health   # {"backend":"backend-2","status":"ok"}
```

<!-- СКРИН: images/01-health.png -->

### 2. Сертификат и пароль для админки

Самоподписанный сертификат (для локалки хватает):

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/nginx.key -out ssl/nginx.crt -subj "/CN=localhost"
```

> На Windows `openssl` нет в `cmd`/PowerShell, поэтому делали через Git Bash (крик единственного виндоус юзера в нашей звёздной компании). Там `-subj` нужно писать как `"//CN=localhost"`.

Пароль для `/admin`:

```bash
htpasswd -c -b .htpasswd admin admin123
```

`-c` создаёт новый файл, `-b` берёт пароль прямо из команды, а не спрашивает. В файл пароль ложится не текстом, а хешем. Пароль `admin123` учебный, в реальной жизни так делать не надо.

<!-- СКРИН: images/02-ssl-htpasswd.png -->

### 3. Запустить nginx

```bash
docker rm -f lab1_nginx

docker run -d --name lab1_nginx -p 80:80 -p 443:443 \
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$PWD/ssl:/etc/nginx/ssl:ro" \
  -v "$PWD/.htpasswd:/etc/nginx/.htpasswd:ro" \
  -v "$PWD/404.html:/usr/share/nginx/errors/404.html:ro" \
  -v "$PWD/www:/var/www:ro" \
  -v "$PWD/../laba0/frontend:/usr/share/nginx/html:ro" \
  nginx:alpine
```

`--add-host=host.docker.internal:host-gateway` нужен, чтобы контейнер мог достучаться до бэкендов, которые крутятся на хосте. `:ro` значит «только чтение». На Windows в Git Bash пути пишутся как `"/$PWD/..."` (с лишним слэшем в начале), на маке и Linux слэш не нужен.

Проверяем конфиг:

```bash
docker exec lab1_nginx nginx -t
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful
```

<!-- СКРИН: images/03-docker-run.png -->

## Конфиг

```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Rate limit: не больше 5 запросов/сек с одного IP
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=5r/s;
    limit_req_status 429;

    upstream backend_nodes {
        server host.docker.internal:5001 max_fails=1 fail_timeout=5s;
        server host.docker.internal:5002 max_fails=1 fail_timeout=5s;
    }

    # Чужой домен на 80 — просто закрываем соединение
    server {
        listen 80 default_server;
        server_name _;
        return 444;
    }

    # Редирект HTTP -> HTTPS (301) для наших доменов
    server {
        listen 80;
        server_name localhost project2.local;
        return 301 https://$host$request_uri;
    }

    # Чужой домен на 443 — ничего не отдаём
    server {
        listen 443 ssl default_server;
        server_name _;
        ssl_certificate     /etc/nginx/ssl/nginx.crt;
        ssl_certificate_key /etc/nginx/ssl/nginx.key;
        return 444;
    }

    # Основной сайт
    server {
        listen 443 ssl;
        server_name localhost;

        ssl_certificate     /etc/nginx/ssl/nginx.crt;
        ssl_certificate_key /etc/nginx/ssl/nginx.key;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # Своя страница 404
        error_page 404 /404.html;
        location = /404.html {
            root /usr/share/nginx/errors;
            internal;
        }

        # Фронтенд
        location / {
            root /usr/share/nginx/html;
            index index.html;
            try_files $uri $uri/ =404;   # было /index.html, иначе 404 никогда не сработает
        }

        # Прокси на API
        location /api/ {
            limit_req zone=api_limit burst=10 nodelay;

            proxy_pass http://backend_nodes;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_connect_timeout 2s;
            proxy_read_timeout 5s;
            proxy_next_upstream error timeout http_502 http_503;
        }

        # alias: /docs/ отдаётся из отдельной папки
        location /docs/ {
            alias /var/www/docs/;
            index index.html;
        }

        # /admin закрыт паролем
        location = /admin { return 301 /admin/; }
        location /admin/ {
            auth_basic           "Admin area";
            auth_basic_user_file /etc/nginx/.htpasswd;
            alias /var/www/admin/;
            index index.html;
        }
    }

    # Второй виртуальный хост
    server {
        listen 443 ssl;
        server_name project2.local;

        ssl_certificate     /etc/nginx/ssl/nginx.crt;
        ssl_certificate_key /etc/nginx/ssl/nginx.key;

        root /var/www/site2;
        index index.html;
        location / {
            try_files $uri $uri/ =404;
        }
    }
}
```

### Что тут вообще происходит

**HTTPS и редирект.** Для HTTPS разрешены только `TLSv1.2` и `TLSv1.3`. На 80 порту сервер отвечает `301` на тот же адрес по HTTPS. В `server_name` указаны оба домена, чтобы второй проект тоже кидало на HTTPS.

**Фронт и бэк на одном хосте.** Всё, что не `/api`, nginx отдаёт сам из `/usr/share/nginx/html`. Запросы на `/api/` летят в `upstream backend_nodes`, а `proxy_set_header` передаёт бэкенду настоящий `Host`, IP клиента и протокол.

**Балансировка и отказоустойчивость.** В `upstream` два сервера, запросы между ними идут поочерёдно (round-robin). За отказоустойчивость отвечают три вещи:

- `max_fails=1 fail_timeout=5s` значит, что после одной неудачи сервер считается недоступным на 5 секунд, и nginx не тратит на него запросы;
- `proxy_connect_timeout 2s` и `proxy_read_timeout 5s` не дают клиенту висеть, если бэкенд лежит или завис;
- `proxy_next_upstream error timeout http_502 http_503` говорит: при ошибке, таймауте, `502` или `503` повторить запрос на другом бэкенде.

**alias.** `/docs/что-то` ищется в `/var/www/docs/что-то`, хотя корень сайта совсем в другом месте. Слэши на конце стоят и в `location`, и в `alias` **специально**: если сделать `location /docs` без слэша, а `alias` со слэшем, получится дыра *path traversal*, через которую можно вылезти в соседние папки.

**Виртуальные хосты.** nginx смотрит на заголовок `Host` и решает, какой `server` отдать: `localhost` получает основной проект, `project2.local` получает свой. Всё, что не подошло ни под один домен, попадает в `default_server` и получает `return 444`: nginx просто рвёт соединение и ничего не отдаёт.

**limit_req.** Зона `api_limit` считает запросы по IP клиента: не больше 5 в секунду, 10 МБ памяти под учёт. `burst=10` даёт запас на 10 запросов сверху, `nodelay` значит, что запасные запросы не ждут в очереди. Всё, что сверх, получает `429`. По умолчанию nginx на превышение отвечает `503`, поэтому статус переделан через `limit_req_status 429`.

**Своя 404.** `error_page 404 /404.html` подсовывает нашу страницу, а `internal` не даёт открыть её напрямую по адресу `/404.html`. Обратите внимание на `try_files $uri $uri/ =404;`: если на конце оставить `/index.html`, то при отсутствии файла будет отдаваться главная, и 404 никогда не сработает.

**Админка.** `location = /admin` докидывает слэш, если его не написали. `auth_basic` включает окошко логина, `"Admin area"` это подпись в окошке, а `auth_basic_user_file` указывает на файл с хешами.

# Как мы проверяли, что всё работает

Все проверки собраны в [`check.sh`](check.sh), а ниже то, что получилось по каждому пункту.

### HTTP → HTTPS

```
$ curl -I http://localhost
HTTP/1.1 301 Moved Permanently
Server: nginx/1.31.6
Content-Type: text/html
Content-Length: 169
Connection: keep-alive
Location: https://localhost/
```

<!-- СКРИН: images/04-redirect.png -->

### Балансировка

Дёргаем `/api/notes` несколько раз подряд и смотрим на заголовок `X-Backend-Id`:

```
$ curl -i -k https://localhost/api/notes   →   X-Backend-Id: backend-1
$ curl -i -k https://localhost/api/notes   →   X-Backend-Id: backend-2
$ curl -i -k https://localhost/api/notes   →   X-Backend-Id: backend-2
$ curl -i -k https://localhost/api/notes   →   X-Backend-Id: backend-1
```

Запросы реально уходят на оба инстанса: то первый, то второй, некий баланс.

<!-- СКРИН: images/05-balancing.png -->

### Отказоустойчивость (главное!)

Останавливаем первый бэкенд (порт 5001) и снова дёргаем `/api/notes`:

```
$ curl -i -k https://localhost/api/notes
HTTP/1.1 200 OK
X-Backend-Id: backend-2

$ curl -i -k https://localhost/api/notes
HTTP/1.1 200 OK
X-Backend-Id: backend-2
```

Половина бэкенда лежит, а сайт отвечает `200`: nginx увёл трафик на живой инстанс. Мы выжили!!!

<!-- СКРИН: images/06-failover.png -->

### Админка

Без пароля nginx не пускает:

```
$ curl -k -i https://localhost/admin/
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic realm="Admin area"
```

С паролем пускает:

```
$ curl -k -i -u admin:admin123 https://localhost/admin/
HTTP/1.1 200 OK
...
<body><h1>Админка</h1><p>Ты прошла auth_basic 🎉</p></body>
```

В браузере то же самое: окошко логина, а после ввода пароля страничка «Админка».

<!-- СКРИНЫ: images/07-admin-401.png, images/08-admin-200.png, images/09-admin-browser.png -->

### Лимит запросов

Флудим 30 запросов подряд на `/api/notes`:

```bash
for i in $(seq 1 30); do
  curl -sk -o /dev/null -w "%{http_code}\n" https://localhost/api/notes
done
```

Первые 11 проходят (`200`): это 1 обычный запрос плюс 10 запасных из `burst`. Всё остальное получает `429 Too Many Requests`. Лимит работает.

<!-- СКРИН: images/10-ratelimit.png -->

### Виртуальные хосты

```
$ curl -k --resolve project2.local:443:127.0.0.1 https://project2.local/
<h1>Это второй проект (project2.local)</h1>

$ curl -k --resolve project2.local:443:127.0.0.1 https://project2.local/api/notes
404 Not Found                         ← API основного сайта тут нет

$ curl -k -H "Host: evil.com" https://localhost/
curl: (52) Empty reply from server    ← default_server рвёт соединение (444)
```

Домены друг другу ничего не сливают, а чужой `Host` не получает вообще ничего. `--resolve` нужен, чтобы сказать curl, что `project2.local` это наш `127.0.0.1` (такого домена в интернете нет).

<!-- СКРИН: images/11-vhosts.png -->

### Своя 404

```
$ curl -k -i https://localhost/nesuschestvuet
HTTP/1.1 404 Not Found
...
<h1>404 — такой страницы нет 🙃</h1>
<p>Кастомная страница ошибки Лабы 1</p>
```

Вместо стандартной страницы nginx отдаётся наша.

<!-- СКРИНЫ: images/12-404-curl.png, images/13-404-browser.png -->

### alias

```
$ curl -k https://localhost/docs/
<h1>Документация</h1><p>Отдаётся через alias из /var/www/docs</p>
```

<!-- СКРИН: images/14-docs.png -->

Чтобы прогнать всё разом:

```bash
chmod +x check.sh
./check.sh
```

На шаге с отказоустойчивостью скрипт остановится и попросит вручную погасить один из бэкендов.

# Грабли

> *Опять не тот порт...*

**«Порт 5432 уже занят».** `docker compose up` падал с `port is already allocated`. Оказалось, что с прошлой лабы продолжал крутиться контейнер `laba0oblaka-db-1`, который порт и держал. Ну и отлично, значит, его и используем.

**Порт 5000 на маке.** Его занимает AirPlay, поэтому бэкенды у нас на 5001 и 5002. Сначала на Windows поднимали на 5000 и 5001, а потом поменяли в nginx на 5001 и 5002 и перезапустили.

**Порт 80 на маке.** `docker run` ругался `address already in use`. Смотрим, кто занял:

```bash
sudo lsof -iTCP:80 -sTCP:LISTEN
```

`sudo` нужен, потому что процесс запущен от root. Порт держал `httpd`, то есть встроенный в мак Apache. Останавливаем (`sudo apachectl stop`) и всё взлетает. Настя наступила на эти же грабли при независимой проверке: контейнер `lab1_nginx` собрался, но не смог стартовать (`ports are not available ... bind: address already in use`), и `docker exec lab1_nginx nginx -t` отвечал `container ... is not running`. `lsof` снова показал `httpd`, после `sudo apachectl stop` и `docker start lab1_nginx` всё поднялось, а `nginx -t` подтвердил, что конфиг рабочий.

**`docker: command not found` (PATH).** У Насти при попытке поднять базу через `docker compose` терминал внезапно перестал видеть команду `docker`, хотя Docker Desktop был установлен. Проверка показала, что дело не в самом Docker: команда работала, если вызывать её по полному пути (`/Applications/Docker.app/Contents/Resources/bin/docker`). Значит, бинарник просто не попал в `PATH`. Починили одной строкой:

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

После этого `docker --version` заработал, но `docker info` всё ещё ругался на `dial unix /var/run/docker.sock: connect: no such file or directory` — сам демон Docker ещё не был запущен. Открыли Docker Desktop, дождались старта, и `docker compose -f laba0/docker-compose.yml up -d` поднял `postgres:16` на порту 5432 без проблем.

**`.venv` не создавалось на Python 3.14.** При настройке окружения для бэкенда `python -m venv venv` падал с ошибкой на Python 3.14 (слишком свежая версия, часть пакетов под неё ещё не собрана). Решение — создать окружение явно на Python 3.13 и поставить туда зависимости из `requirements.txt`, дальше всё встало на свои места.

**Гонка бэкендов (502 Bad Gateway).** При старте каждый бэкенд вызывает `init_db()` и создаёт таблицы в PostgreSQL. Когда оба запустились одновременно (через `docker compose up`), они в одну миллисекунду полезли создавать одно и то же, один получил `UniqueViolation` и упал, а nginx честно показал `502 Bad Gateway`. Лечится перезапуском:

```bash
docker compose restart backend-1 backend-2
```

При ручном запуске мы просто стартовали второй бэкенд после первого.

**404, которая не работала.** Сначала в `try_files` на конце стоял `/index.html`, и вместо 404 для любой несуществующей страницы отдавалась главная. Поменяли на `=404`, и теперь ненайденное честно 404.

**Самоподписанный сертификат.** Safari ругается «Это подключение не защищено», потому что сертификат мы сделали сами. Для локалки это нормально: жмём «Подробнее» и заходим.

<!-- СКРИН: images/15-safari-cert.png -->

# Независимая перепроверка

Чтобы проверки не мешались в общей ветке, Настя скачала репозиторий отдельно и завела свою ветку `lab1-checks`, прогнала всё заново с нуля (от поднятия базы и бэкендов до nginx) и сохранила команды с результатами в `laba1/check.sh` и `laba1/check-output.txt`.

Прогнала те же проверки, что и выше, только своими руками и в своём терминале:

- `curl -I http://localhost` → `301 Moved Permanently`, `Location: https://localhost/`;
- `curl -ki https://localhost/api/notes` → `200 OK`, `X-Backend-Id: backend-1`;
- шесть запросов подряд с паузой в секунду → все `200`, а среди `X-Backend-Id` встретились и `backend-1`, и `backend-2` — балансировка работает;
- остановила `backend-1` (порт 5001) и повторила те же шесть запросов → все шесть получили `200` от `backend-2`. Это и стало самым понятным доказательством отказоустойчивости: половина бэкенда лежит, а API продолжает отвечать;
- `curl -ki https://localhost/admin/` без пароля → `401 Unauthorized`;
- тот же запрос с `-u admin` и правильным паролем → `200 OK`, «Админка», «Ты прошла auth_basic»;
- запрос несуществующей страницы → `404` с нашим текстом «Кастомная страница ошибки Лабы 1»;
- `curl -ki https://localhost/docs/` → `200`, «Документация», отдаётся через `alias`;
- `curl --resolve project2.local:443:127.0.0.1 https://project2.local/` → `200` и страница второго проекта, без правки `/etc/hosts`;
- `curl -H "Host: unknown.local" http://127.0.0.1/` → `curl: (52) Empty reply from server`, то есть сработал `return 444` и чужому домену ничего не досталось;
- 30 запросов к `/api/notes` без пауз → сначала `200`, потом пошли `429` — лимит сработал.

<!-- СКРИН: images/17-nastya-checks.png -->

Независимая перепроверка на отдельной копии репозитория подтвердила все те же результаты, что и в основном прогоне: значит, дело не в случайности или особенностях одной машины, а в том, что конфиг действительно работает как надо.

> По пути в выводе проверок всплыли конфликтные маркеры и задублированный `index.html` фронтенда — пришлось руками подчистить перед коммитом. Так иногда бывает, когда несколько человек трогают одни и те же файлы.

Ветка `lab1-checks` закоммичена и запушена в GitHub, после чего GitHub сам предложил открыть Pull Request.

# Со звёздочкой

Задание: «взломать» (на самом деле — найти уязвимость в конфигурации) любого доступного небольшого сайта на nginx. Взлом засчитывается, даже если получилось попасть туда, куда не планировалось пускать пользователя.

**Выбор цели.** Сначала присматривались к `smgrf.ru`, но заголовки ответа показали `Server: Apache`, а задание именно про nginx — пришлось поискать другой сайт.

```
$ curl -sS -I --connect-timeout 5 --max-time 15 https://smgrf.ru/
HTTP/2 200
server: Apache
```

Остановились на сайте Федерации танцевального спорта Омской области — `https://ftsoo.ru/`. В заголовках у него честно значится `server: nginx`, плюс видно `x-powered-by: PHP/8.1.21` — сайт на WordPress.

```
$ curl -sS -I --connect-timeout 5 --max-time 15 https://ftsoo.ru/
HTTP/2 200
server: nginx
x-powered-by: PHP/8.1.21
```

<!-- СКРИН: images/18-target-choice.png -->

Проверили три типа слабых мест в конфигурации:

**1. Открытый список файлов в `/wp-content/uploads/`.** Если на сервере включена выдача списка каталогов, через такой урл можно увидеть файлы и папки, которых нет на страницах сайта.

```
$ curl -sS --connect-timeout 5 --max-time 15 -D - https://ftsoo.ru/wp-content/uploads/
HTTP/2 403
server: nginx
<H1>403 Forbidden</H1>
```

Результат: `403 Forbidden`, listing директории закрыт. Доступа не получили.

**2. Служебные файлы `/.git/HEAD` и `/.env`.** Если такие файлы случайно остаются доступны снаружи, через них можно узнать структуру репозитория или настройки приложения (пароли от базы, ключи и т.д.).

```
$ for test_uri in '/.git/HEAD' '/.env'; do
    curl -sS -I --connect-timeout 5 --max-time 15 "https://ftsoo.ru$test_uri"
  done
```

Оба запроса вернули `404`. Это не стопроцентное доказательство, что файлов нет (сервер может просто не отдавать их по правилам конфига), но доступа к ним снаружи нет в любом случае.

**3. Path traversal через `alias`.** Самая интересная проверка — та самая дыра, о которой мы писали в разборе своего конфига (`location` без слэша + `alias` со слэшем). Попробовали выйти за пределы каталога `uploads` двумя способами:

```
$ curl -sS -I --path-as-is --connect-timeout 5 --max-time 15 \
  "https://ftsoo.ru/wp-content/uploads/../../.git/HEAD"
HTTP/2 404

$ curl -sS -I --path-as-is --connect-timeout 5 --max-time 15 \
  "https://ftsoo.ru/wp-content/uploads../.git/HEAD"
HTTP/2 404
```

Флаг `--path-as-is` обязателен, иначе curl сам нормализует `../` в пути ещё до отправки запроса. Оба варианта вернули `404` — ни обычный `../`, ни заход через вариацию пути без слэша (имитация неправильного `alias`) не сработали.

<!-- СКРИН: images/19-pentest-results.png -->

**Итог звёздочки:** взлом не удался. Все три проверенные уязвимости (листинг каталога, служебные файлы, path traversal) закрыты правильной настройкой nginx на `ftsoo.ru`. Отрицательный результат — тоже результат: он показывает, что сайт настроен аккуратнее, чем мог бы быть, а заодно подтверждает на практике, зачем в своём конфиге мы сами закрывали ровно эти же дыры (`internal` для 404, правильные слэши в `alias`, `default_server` с `444`).

# Бонус: всё одной командой через Docker Compose

Не дожидаясь Лабы 2, мы не удержались и автоматизировали запуск. Что добавили:

- `laba0/backend/Dockerfile`: берёт `python:3.10-slim`, ставит зависимости из `requirements.txt`, копирует код и запускает `app.py`;
- `laba1/docker-compose.yml`: описывает 4 контейнера: `postgres`, `backend-1` (5001), `backend-2` (5002) и `nginx`.

Теперь всё поднимается так:

```bash
docker compose up --build -d
```

Не нужны ни `venv`, ни локальный Python, оба бэкенда запускаются сразу в изолированной сети, а одногруппник скачивает проект из Git и получает рабочую систему одной командой. Минус тот же: гонка бэкендов при первом старте (см. «Грабли»).

<!-- СКРИН: images/16-compose.png -->

# Итог

Мы поставили перед сервисом «Заметки» nginx, и он стал точкой входа для всего:

- **TLS и редирект.** HTTPS с самоподписанным сертификатом, HTTP уходит на HTTPS (301).
- **Фронт и бэк.** Статику nginx отдаёт сам, `/api` проксирует на бэкенд.
- **Балансировка.** Запросы чередуются между `backend-1` и `backend-2`, это видно по `X-Backend-Id`.
- **Отказоустойчивость.** Если один бэкенд упал, `/api` всё равно отвечает `200`.
- **Защита и порядок.** `/admin` под паролем (401 без него), `limit_req` даёт 429 при флуде, чужой `Host` не получает ничего (444), есть своя 404.
- **Мелочи, которые решают.** Слэши в `alias`, `=404` в `try_files` и `default_server` с `return 444` отличают нормальную настройку от дырявой.

