# Локальная публикация DocFlowProject

Целевой первый вариант: доступ только из корпоративной локальной сети.

## Параметры

- Сервер приложения: `10.110.53.17`
- SQL Server: `10.110.53.17`
- База данных: `DocflowApplicationDB`
- SQL-пользователь: `DocFlowUser`
- Папка файлов: `S:\Договоры и соглашения\DocFlow\data\media`
- Порт веб-приложения: `8010`
- Адрес для пользователей: `http://10.110.53.17:8010/`

## Важное про диск S:

Если `S:` является подключенным сетевым диском, Windows-служба может его не увидеть. Для постоянного запуска лучше использовать локальный путь на сервере, например `D:\DocFlow\data\media`, или UNC-путь вида `\\server\share\DocFlow\data\media`.

## Что установить на сервер

1. Python x64.
2. Git.
3. Microsoft ODBC Driver 18 for SQL Server.
4. Python-зависимости проекта:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Создание базы

В SQL Server Management Studio выполнить `deployment/sqlserver-init.sql`, заменив `CHANGE_ME_STRONG_PASSWORD` на реальный пароль.

## Первый запуск

Из папки проекта:

```powershell
.\deployment\run-localcorp-waitress.ps1 `
  -DbPassword "ПАРОЛЬ_SQL_ПОЛЬЗОВАТЕЛЯ" `
  -SecretKey "ДЛИННАЯ_СЛУЧАЙНАЯ_СТРОКА" `
  -MediaRoot "S:\Договоры и соглашения\DocFlow\data\media" `
  -StaticRoot "S:\Договоры и соглашения\DocFlow\data\staticfiles"
```

После запуска открыть:

```text
http://10.110.53.17:8010/
```

## Если страница не открывается с другого компьютера

Проверить:

- Windows Firewall на сервере: входящий TCP-порт `8010`;
- что сервер доступен по IP `10.110.53.17`;
- что SQL Server принимает подключения на `1433`;
- что пароль `DocFlowUser` указан верно;
- что папка `DOCFLOW_MEDIA_ROOT` доступна учетной записи, от имени которой запущено приложение.
