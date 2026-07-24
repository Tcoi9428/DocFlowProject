# Локальная публикация DocFlowProject

Целевой первый вариант: доступ только из корпоративной локальной сети.

## Параметры

- Сервер приложения: `10.110.53.17`
- SQL Server: `10.110.53.17`
- База данных: `DocflowApplicationDB`
- SQL-пользователь: `FlowUser`
- Папка файлов: `S:\Договоры и соглашения\DocFlow\data\media`
- Порт веб-приложения: `8010`
- Адрес для пользователей: `http://10.110.53.17:8010/`

## Важное про диск S:

Если `S:` является подключенным сетевым диском, Windows-служба может его не увидеть. Для постоянного запуска лучше использовать локальный путь на сервере, например `D:\DocFlow\data\media`, или UNC-путь вида `\\server\share\DocFlow\data\media`.

## Что установить на сервер

1. Python x64.
2. Git.
3. Microsoft ODBC Driver 18 for SQL Server или другой установленный ODBC-драйвер SQL Server.
4. Python-зависимости проекта:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Проверить установленные ODBC-драйверы:

```powershell
Get-OdbcDriver | Where-Object { $_.Name -like "*SQL*" } | Select-Object Name
```

## Создание базы

В SQL Server Management Studio выполнить `deployment/sqlserver-init.sql`, заменив `CHANGE_ME_STRONG_PASSWORD` на реальный пароль.

## Первый запуск

Из папки проекта:

```powershell
.\deployment\run-localcorp-waitress.ps1 `
  -DbPassword "ПАРОЛЬ_SQL_ПОЛЬЗОВАТЕЛЯ" `
  -SecretKey "ДЛИННАЯ_СЛУЧАЙНАЯ_СТРОКА" `
  -DbDriver "ODBC Driver 18 for SQL Server" `
  -MediaRoot "S:\Договоры и соглашения\DocFlow\data\media" `
  -StaticRoot "S:\Договоры и соглашения\DocFlow\data\staticfiles"
```

Если на сервере установлен не `ODBC Driver 18 for SQL Server`, а например `ODBC Driver 17 for SQL Server`, укажите его:

```powershell
.\deployment\run-localcorp-waitress.ps1 `
  -DbPassword "ПАРОЛЬ_SQL_ПОЛЬЗОВАТЕЛЯ" `
  -SecretKey "ДЛИННАЯ_СЛУЧАЙНАЯ_СТРОКА" `
  -DbDriver "ODBC Driver 17 for SQL Server" `
  -MediaRoot "S:\Договоры и соглашения\DocFlow\data\media" `
  -StaticRoot "S:\Договоры и соглашения\DocFlow\data\staticfiles"
```

После запуска открыть:

```text
http://10.110.53.17:8010/
```

## Email-уведомления через Яндекс

Для временной отправки используется отдельный ящик `docflow-notify@yandex.ru` и пароль приложения Яндекс.
Основной пароль от почтового ящика использовать нельзя.

Проверить доступность SMTP с Windows Server:

```powershell
Test-NetConnection smtp.yandex.ru -Port 465
```

Запуск приложения с включенной отправкой писем:

```powershell
.\deployment\run-localcorp-waitress.ps1 `
  -DbPassword "ПАРОЛЬ_SQL_ПОЛЬЗОВАТЕЛЯ" `
  -SecretKey "ДЛИННАЯ_СЛУЧАЙНАЯ_СТРОКА" `
  -DbDriver "ODBC Driver 18 for SQL Server" `
  -MediaRoot "E:\DocFlow\data\media" `
  -StaticRoot "E:\DocFlow\data\staticfiles" `
  -BaseUrl "http://10.110.53.17:8010" `
  -EmailHost "smtp.yandex.ru" `
  -EmailPort 465 `
  -EmailUser "docflow-notify@yandex.ru" `
  -EmailPassword "ПАРОЛЬ_ПРИЛОЖЕНИЯ_ЯНДЕКС" `
  -EmailSecurity "ssl" `
  -DefaultFromEmail "DocFlow <docflow-notify@yandex.ru>"
```

Если `EmailUser` или `EmailPassword` не переданы, приложение безопасно продолжит работу без реальной
отправки писем, а уведомления останутся в очереди.

Для отдельной проверки SMTP сначала загрузить параметры в текущую PowerShell-сессию:

```powershell
. .\deployment\set-localcorp-env.ps1 `
  -DbPassword "ПАРОЛЬ_SQL_ПОЛЬЗОВАТЕЛЯ" `
  -SecretKey "ДЛИННАЯ_СЛУЧАЙНАЯ_СТРОКА" `
  -DbDriver "ODBC Driver 18 for SQL Server" `
  -MediaRoot "E:\DocFlow\data\media" `
  -StaticRoot "E:\DocFlow\data\staticfiles" `
  -BaseUrl "http://10.110.53.17:8010" `
  -EmailHost "smtp.yandex.ru" `
  -EmailPort 465 `
  -EmailUser "docflow-notify@yandex.ru" `
  -EmailPassword "ПАРОЛЬ_ПРИЛОЖЕНИЯ_ЯНДЕКС" `
  -EmailSecurity "ssl"

E:\DocFlow\venv\Scripts\python.exe manage.py send_test_email "ПОЛУЧАТЕЛЬ@COMPANY.RU"
```

Ожидающие и не отправленные письма можно обработать вручную:

```powershell
.\deployment\run-email-queue.ps1 `
  -DbPassword "ПАРОЛЬ_SQL_ПОЛЬЗОВАТЕЛЯ" `
  -SecretKey "ДЛИННАЯ_СЛУЧАЙНАЯ_СТРОКА" `
  -EmailPassword "ПАРОЛЬ_ПРИЛОЖЕНИЯ_ЯНДЕКС"
```

Для автоматических повторных попыток этот скрипт следует запускать Планировщиком заданий Windows
каждые 5 минут. Новые письма при рабочем SMTP отправляются сразу, поэтому задача нужна прежде всего
для повторения временно неудачных отправок.

В службе NSSM откройте `nssm edit DocFlow` и добавьте в `Arguments` параметры от `-BaseUrl` до
`-DefaultFromEmail` из примера выше. После сохранения перезапустите службу:

```powershell
Restart-Service DocFlow
```

Email-адрес каждого получателя должен быть заполнен в Django Admin в карточке пользователя.
Журнал писем доступен в Django Admin в разделе `Отправки email`.

## Если страница не открывается с другого компьютера

Проверить:

- Windows Firewall на сервере: входящий TCP-порт `8010`;
- что сервер доступен по IP `10.110.53.17`;
- что SQL Server принимает подключения на `1433`;
- что пароль `FlowUser` указан верно;
- что папка `DOCFLOW_MEDIA_ROOT` доступна учетной записи, от имени которой запущено приложение.
