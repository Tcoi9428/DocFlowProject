# Публикация На Windows Server 2019

Инструкция описывает первый рабочий вариант публикации DocFlowProject на корпоративном Windows Server 2019 с базой Microsoft SQL Server 2019.

## Целевая Схема

Рекомендуемая структура папок на сервере:

```text
D:\DocFlow\app              код приложения
D:\DocFlow\venv             виртуальное окружение Python
D:\DocFlow\data\media       загруженные файлы документов
D:\DocFlow\data\staticfiles статические файлы интерфейса
D:\DocFlow\logs             журналы сервиса
```

База данных хранится в SQL Server. Загруженные пользователями файлы хранятся на диске в папке `DOCFLOW_MEDIA_ROOT`.

## Что Нужно Установить На Сервер

1. Python 3.12 x64.
2. Git.
3. Microsoft ODBC Driver 18 for SQL Server.
4. Доступ к SQL Server 2019.
5. Открытый входящий порт Windows Firewall, например `8000` для первого теста.

## Подготовка SQL Server

Пример SQL-скрипта:

```sql
CREATE DATABASE DocFlow;
GO

CREATE LOGIN docflow_user WITH PASSWORD = 'CHANGE_ME_STRONG_PASSWORD';
GO

USE DocFlow;
GO

CREATE USER docflow_user FOR LOGIN docflow_user;
ALTER ROLE db_owner ADD MEMBER docflow_user;
GO
```

Для первого запуска `db_owner` проще. После стабилизации можно заменить на более строгие права.

## Установка Проекта

```powershell
mkdir D:\DocFlow
cd D:\DocFlow
git clone https://github.com/Tcoi9428/DocFlowProject.git app
cd D:\DocFlow\app
```

Создать виртуальное окружение:

```powershell
python -m venv D:\DocFlow\venv
D:\DocFlow\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Создать папки для данных:

```powershell
mkdir D:\DocFlow\data\media
mkdir D:\DocFlow\data\staticfiles
mkdir D:\DocFlow\logs
```

## Переменные Среды

Для тестового запуска можно задать переменные в текущем PowerShell:

```powershell
$env:DOCFLOW_DEBUG="false"
$env:DOCFLOW_SECRET_KEY="CHANGE_ME_TO_LONG_RANDOM_SECRET"
$env:DOCFLOW_ALLOWED_HOSTS="127.0.0.1,localhost,SERVER_NAME_OR_IP"
$env:DOCFLOW_CSRF_TRUSTED_ORIGINS="http://SERVER_NAME_OR_IP"

$env:DOCFLOW_DB_ENGINE="mssql"
$env:DOCFLOW_DB_NAME="DocFlow"
$env:DOCFLOW_DB_USER="docflow_user"
$env:DOCFLOW_DB_PASSWORD="CHANGE_ME"
$env:DOCFLOW_DB_HOST="SQL_SERVER_HOST_OR_IP"
$env:DOCFLOW_DB_PORT="1433"
$env:DOCFLOW_DB_DRIVER="ODBC Driver 18 for SQL Server"
$env:DOCFLOW_DB_EXTRA_PARAMS="TrustServerCertificate=yes"

$env:DOCFLOW_MEDIA_ROOT="D:\DocFlow\data\media"
$env:DOCFLOW_STATIC_ROOT="D:\DocFlow\data\staticfiles"
```

Значения также есть в файле `.env.production.example`. Сам Django этот файл автоматически не читает, поэтому переменные нужно задать в системе, в службе Windows или в скрипте запуска.

## Инициализация Базы И Статики

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

Для тестового стенда можно создать демо-данные:

```powershell
python manage.py seed_demo
```

На рабочей базе с реальными документами `seed_demo` запускать не нужно.

## Первый Запуск В Локальной Сети

```powershell
waitress-serve --listen=0.0.0.0:8000 docflow_project.wsgi:application
```

После запуска открыть с другого компьютера:

```text
http://SERVER_NAME_OR_IP:8000/
```

Если страница не открывается, проверить:

- Windows Firewall на сервере;
- доступность порта `8000`;
- правильность `DOCFLOW_ALLOWED_HOSTS`;
- подключение к SQL Server;
- папки `DOCFLOW_MEDIA_ROOT` и `DOCFLOW_STATIC_ROOT`.

## Запуск Как Служба Windows

Для постоянной работы лучше использовать NSSM или Планировщик заданий Windows.

Команда службы:

```text
D:\DocFlow\venv\Scripts\waitress-serve.exe --listen=0.0.0.0:8000 docflow_project.wsgi:application
```

Рабочая папка:

```text
D:\DocFlow\app
```

Переменные среды должны быть доступны учетной записи, от имени которой работает служба.

## Миграция Данных Из SQLite В SQL Server

Если нужно перенести текущие данные из локального `db.sqlite3`:

1. Остановить локальный сервер разработки.
2. Сделать копию `db.sqlite3` и папки `media`.
3. Экспортировать данные:

```powershell
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 -o D:\DocFlow\backup\docflow-data.json
```

4. На сервере включить переменные среды SQL Server.
5. Выполнить:

```powershell
python manage.py migrate
python manage.py loaddata D:\DocFlow\backup\docflow-data.json
```

6. Скопировать файлы из локальной `media` в серверную папку `DOCFLOW_MEDIA_ROOT`.
7. Проверить документы, вложения, пользователей и маршруты согласования в браузере.

Для первого промышленного запуска может быть проще начать с пустой SQL Server базы и создать пользователей/справочники заново.

## Резервное Копирование

Минимально нужно резервировать:

- базу SQL Server `DocFlow`;
- папку `D:\DocFlow\data\media`;
- конфигурацию переменных среды;
- код приложения или GitHub-репозиторий.

## Перед Доступом Из Интернета

Для публикации не только в локальной сети, а наружу, дополнительно нужны:

- HTTPS-сертификат;
- reverse proxy через IIS или другой веб-сервер;
- `DOCFLOW_DEBUG=false`;
- строгий `DOCFLOW_ALLOWED_HOSTS`;
- надежный `DOCFLOW_SECRET_KEY`;
- регламент резервного копирования;
- настройка SMTP для реальных email-уведомлений.
