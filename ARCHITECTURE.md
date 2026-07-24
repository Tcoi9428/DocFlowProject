# Architecture

## Стек

- Python.
- Django 5.
- SQLite для прототипа.
- Планируемая БД для эксплуатации: Microsoft SQL Server 2019.
- HTML-шаблоны Django.
- CSS в `static/css/app.css`.

## Django-Приложения

Основное приложение:

```text
documents/
```

Ключевые модули:

```text
models.py            модели данных
forms.py             формы создания, редактирования и согласования
views.py             экраны и обработчики запросов
services.py          бизнес-логика согласования, уведомлений и аудита
admin.py             настройка Django Admin
context_processors.py данные уведомлений и счетчиков для всех шаблонов
user_display.py      единый формат отображения пользователей
templatetags/        template-фильтры
tests.py             автотесты
```

## Основные Модели

- `Department` - подразделения.
- `UserProfile` - профиль пользователя: подразделение, отчество, должность, телефон.
- `DocumentType` - тип документа.
- `ContractKind` - вид договора.
- `DocumentPurpose` - назначение документа.
- `CustomFieldDefinition` - пользовательские поля по типам документов.
- `ApprovalRoute` - шаблон маршрута согласования.
- `ApprovalStep` - этап шаблонного маршрута.
- `Document` - документ.
- `DocumentApprover` - пользовательские согласующие конкретного документа.
- `Attachment` - вложение.
- `ApprovalTask` - задача согласования.
- `DocumentComment` - комментарий к документу.
- `Notification` - внутреннее уведомление.
- `EmailDelivery` - очередь и журнал отправки email-уведомлений.
- `AuditLog` - журнал действий.

## Нумерация

Системный номер генерируется в `Document.generate_system_number()`.

Формат:

```text
КОДТИПА-ГОД-00001
```

Примеры:

```text
DOG-2026-00001
SZ-2026-00001
PRK-2026-00001
VND-2026-00001
PAY-2026-00001
```

## Согласование

Логика согласования находится в `documents/services.py`.

Основные функции:

- `start_approval`
- `approve_task`
- `reject_task`
- `return_for_revision`
- `delegate_task`
- `notify_approval_required`
- `notify_status_change`
- `log_action`

Если у документа есть пользовательские согласующие `DocumentApprover`, они используются приоритетно.

Если пользовательские согласующие не заданы, используется шаблонный маршрут `ApprovalRoute`.

## Уведомления

Уведомления хранятся в модели `Notification`.

Глобальные счетчики и последние уведомления передаются в шаблоны через:

```text
documents/context_processors.py
```

Открытие уведомления помечает его прочитанным и переводит пользователя по ссылке уведомления.

Для пользователя с заполненным email при создании уведомления формируется `EmailDelivery`.
Письмо отправляется после фиксации транзакции и содержит абсолютную ссылку на DocFlow.
Неудачная отправка сохраняется со статусом и повторяется командой:

```text
python manage.py send_notification_emails
```

## Отображение Пользователей

Единый формат:

```text
Фамилия Имя Отчество
(Должность)
```

Логика:

```text
documents/user_display.py
documents/templatetags/user_display.py
templates/documents/partials/user_display.html
```

В выпадающих списках используется однострочный вариант:

```text
Фамилия Имя Отчество (Должность)
```

## Вложения

Файлы сохраняются на диске в `media/`.

В базе хранятся:

- путь к файлу;
- исходное имя;
- размер;
- SHA-256 hash.

Максимальный размер файла задается в настройках через `MAX_UPLOAD_SIZE`.

## Переход На SQL Server

Для перехода на Microsoft SQL Server 2019 потребуется:

- установить ODBC Driver for SQL Server;
- установить `mssql-django` и `pyodbc`;
- изменить `DATABASES` в `docflow_project/settings.py`;
- выполнить миграции;
- настроить хранение `media/` на серверном диске;
- настроить бэкапы БД и файлов.
