# ☕️ Coffee Bot - Управление чисткой оборудования

Telegram бот для управления задачами по чистке оборудования в кофейне с интеграцией Google Sheets.

## 📋 Возможности

- ✅ Автоматическая отправка задач сотрудникам по расписанию
- ✅ Интеграция с Google Sheets для хранения данных
- ✅ Интерактивные кнопки для отметки выполненных задач
- ✅ История выполненных задач
- ✅ Уведомления о просроченных задачах
- ✅ Docker-ready для простого деплоя

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose установлены
- Google аккаунт для создания Google Sheets
- Telegram аккаунт для создания бота

---

## 📝 Шаг 1: Создание Telegram бота

1. Открой Telegram и найди бота [@BotFather](https://t.me/BotFather)
2. Отправь команду `/newbot`
3. Введи имя бота (например, "Coffee Cleaning Bot")
4. Введи username бота (например, `coffee_cleaning_bot`)
5. BotFather отправит тебе токен в формате: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
6. **Сохрани этот токен** - он понадобится для `.env` файла

---

## 🔑 Шаг 2: Настройка Google Sheets API

### 2.1 Создание проекта в Google Cloud

1. Перейди в [Google Cloud Console](https://console.cloud.google.com/)
2. Нажми **"Select a project"** → **"New Project"**
3. Введи название проекта (например, "Coffee Bot")
4. Нажми **"Create"**

### 2.2 Включение Google Sheets API

1. В меню слева выбери **"APIs & Services"** → **"Library"**
2. Найди **"Google Sheets API"**
3. Нажми на него и нажми **"Enable"**
4. Также найди и включи **"Google Drive API"**

### 2.3 Создание Service Account

1. Перейди в **"APIs & Services"** → **"Credentials"**
2. Нажми **"Create Credentials"** → **"Service Account"**
3. Введи:
   - Service account name: `coffee-bot`
   - Service account ID: `coffee-bot` (заполнится автоматически)
4. Нажми **"Create and Continue"**
5. В разделе "Grant this service account access to project" можно пропустить
6. Нажми **"Done"**

### 2.4 Создание ключа (credentials.json)

1. В списке Service Accounts найди созданный аккаунт `coffee-bot`
2. Нажми на него (на email адрес)
3. Перейди на вкладку **"Keys"**
4. Нажми **"Add Key"** → **"Create new key"**
5. Выбери формат **JSON**
6. Нажми **"Create"**
7. Файл `credentials.json` автоматически скачается
8. **Переименуй его в `credentials.json`** и **сохрани в корневой папке проекта**

---

## 📊 Шаг 3: Создание Google Таблицы

### 3.1 Создание таблицы

1. Перейди на [Google Sheets](https://sheets.google.com)
2. Создай новую таблицу (нажми **+** или "Blank")
3. Назови таблицу, например: **"Coffee Cleaning Tasks"**

### 3.2 Настройка листа "Оборудование"

1. Создай первый лист с названием **"Оборудование"**
2. Создай заголовки в первой строке:

| A | B | C | D | E |
|---|---|---|---|---|
| Название | Периодичность | Последняя чистка | Выполнил | Статус |

3. Заполни примерные данные:

| Название | Периодичность | Последняя чистка | Выполнил | Статус |
|----------|---------------|------------------|----------|--------|
| ЕК 43S | ежедневно | 25.09.2025 | - | ⏳ |
| ЕК 65 | ежедневно | 20.09.2025 | - | ⏳ |
| Гриль | еженедельно | 24.09.2025 | - | ⏳ |
| Витрина холодная | ежедневно | 30.09.2025 | - | ⏳ |

**Важно:**
- Периодичность должна быть: `ежедневно`, `еженедельно` или `ежемесячно`
- Формат даты: `дд.мм.гггг` (например, `01.10.2025`)

### 3.3 Настройка листа "Смены"

1. Создай второй лист с названием **"Смены"**
2. Создай заголовки:

| A | B | C | D |
|---|---|---|---|
| Дата | ФИО | Telegram Username | Время начала |

3. Заполни расписание смен:

| Дата | ФИО | Telegram Username | Время начала |
|------|-----|-------------------|--------------|
| 01.10.2025 | Иван Петров | ivan_barista | 08:00 |
| 01.10.2025 | Мария Сидорова | maria_barista | 14:00 |
| 02.10.2025 | Иван Петров | ivan_barista | 08:00 |

**Важно:**
- Telegram Username БЕЗ символа `@` (просто `ivan_barista`)
- Формат даты: `дд.мм.гггг`
- Сотрудники должны иметь установленный username в Telegram

### 3.4 Открытие доступа для Service Account

1. В открытой Google Таблице нажми кнопку **"Share"** (Поделиться) в правом верхнем углу
2. В поле "Add people and groups" вставь **email адрес Service Account**
   - Его можно найти в файле `credentials.json` в поле `"client_email"`
   - Или в Google Cloud Console → Service Accounts
   - Выглядит как: `coffee-bot@project-name.iam.gserviceaccount.com`
3. Выбери права **"Editor"** (Редактор)
4. Нажми **"Send"**

### 3.5 Получение ID таблицы

1. Посмотри на URL твоей Google Таблицы:
   ```
   https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
   ```
2. ID таблицы - это часть между `/d/` и `/edit`:
   ```
   1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
   ```
3. **Скопируй этот ID** - он понадобится для `.env` файла

---

## ⚙️ Шаг 4: Настройка проекта

### 4.1 Клонирование и структура

Создай следующую структуру папок:

```
coffee-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py
│   ├── handlers.py
│   ├── scheduler.py
│   ├── sheets_manager.py
│   └── config.py
├── credentials.json          ← Скачанный файл из Google Cloud
├── .env                      ← Создай на основе .env.example
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### 4.2 Создание .env файла

1. Скопируй файл `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```

2. Открой `.env` и заполни данные:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
GOOGLE_SHEETS_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
GOOGLE_CREDENTIALS_FILE=credentials.json
NOTIFICATION_TIME=07:30
TIMEZONE=Europe/Moscow
MANAGER_CHAT_ID=123456789
```

**Где взять каждое значение:**
- `TELEGRAM_BOT_TOKEN` - токен от BotFather (Шаг 1)
- `GOOGLE_SHEETS_ID` - ID таблицы (Шаг 3.5)
- `GOOGLE_CREDENTIALS_FILE` - имя файла (обычно `credentials.json`)
- `NOTIFICATION_TIME` - время отправки уведомлений (формат ЧЧ:ММ)
- `TIMEZONE` - часовой пояс (список: [IANA Time Zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones))
- `MANAGER_CHAT_ID` - (опционально) Telegram ID менеджера для уведомлений

---

## 🐳 Шаг 5: Запуск через Docker

### 5.1 Сборка и запуск

```bash
docker-compose up -d --build
```

### 5.2 Проверка логов

```bash
docker-compose logs -f
```

Должны увидеть:
```
coffee-cleaning-bot  | 2025-10-01 07:28:00 - Bot initialized successfully
coffee-cleaning-bot  | 2025-10-01 07:28:00 - Scheduler started. Notifications will be sent at 07:30 Europe/Moscow
coffee-cleaning-bot  | 2025-10-01 07:28:00 - Starting bot...
```

### 5.3 Остановка бота

```bash
docker-compose down
```

### 5.4 Перезапуск после изменений

```bash
docker-compose down
docker-compose up -d --build
```

---

## 📱 Шаг 6: Тестирование бота

### 6.1 Первый запуск

1. Найди своего бота в Telegram по username (например, `@coffee_cleaning_bot`)
2. Нажми **"Start"** или отправь `/start`
3. Бот должен ответить приветственным сообщением

### 6.2 Тестирование команд

```
/start   - Приветствие
/tasks   - Показать задачи на сегодня
/history - История за 7 дней
/help    - Справка
```

### 6.3 Проверка уведомлений

1. Убедись что твой username добавлен в лист "Смены" на сегодняшний день
2. Дождись времени из `NOTIFICATION_TIME` или измени время на ближайшее
3. Бот должен автоматически отправить список задач
4. Нажми на кнопку "✅ Выполнено"
5. Проверь Google Таблицу - данные должны обновиться

---

## 🛠 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и инструкция по использованию |
| `/tasks` | Показать задачи на сегодня |
| `/history` | История выполненных задач (последние 7 дней) |
| `/help` | Справка по всем командам |

---

## 📊 Структура данных Google Sheets

### Лист "Оборудование"

| Колонка | Описание | Формат |
|---------|----------|--------|
| Название | Название оборудования | Текст |
| Периодичность | Частота чистки | `ежедневно` / `еженедельно` / `ежемесячно` |
| Последняя чистка | Дата последней чистки | `дд.мм.гггг` |
| Выполнил | ФИО сотрудника | Текст (автоматически) |
| Статус | Статус задачи | `✅` или `⏳` (автоматически) |

### Лист "Смены"

| Колонка | Описание | Формат |
|---------|----------|--------|
| Дата | Дата смены | `дд.мм.гггг` |
| ФИО | Полное имя сотрудника | Текст |
| Telegram Username | Username в Telegram БЕЗ @ | Текст |
| Время начала | Время начала смены | `ЧЧ:ММ` |

---

## ⚠️ Решение проблем

### Бот не отправляет уведомления

1. Проверь логи: `docker-compose logs -f`
2. Убедись что в листе "Смены" есть записи на сегодня
3. Проверь что username в таблице совпадает с Telegram username
4. Убедись что время `NOTIFICATION_TIME` настроено правильно

### Ошибка подключения к Google Sheets

1. Проверь что `credentials.json` находится в корне проекта
2. Убедись что Service Account имеет доступ к таблице (Editor)
3. Проверь что Google Sheets API и Google Drive API включены

### Бот не обновляет таблицу

1. Проверь права Service Account (должен быть Editor, а не Viewer)
2. Проверь формат дат в таблице (`дд.мм.гггг`)
3. Посмотри логи на ошибки: `docker-compose logs -f`

### Сотрудник не получает уведомления

1. Убедись что у сотрудника установлен username в Telegram
2. Сотрудник должен первым написать боту `/start`
3. Username в таблице должен быть БЕЗ символа `@`

---

## 🔧 Разработка

### Локальный запуск (без Docker)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m bot.main
```

### Просмотр логов в реальном времени

```bash
docker-compose logs -f coffee-bot
```

---

## 📦 Обновление бота

```bash
git pull
docker-compose down
docker-compose up -d --build
```

---

## 📄 Лицензия

MIT License

---

## 👨‍💻 Поддержка

Если возникли проблемы:
1. Проверь логи: `docker-compose logs -f`
2. Убедись что все конфигурации заполнены правильно
3. Проверь что Google Sheets имеет правильную структуру

Удачи! ☕️