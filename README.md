# 💼 AI Финансовый Директор — Telegram Bot

Персональный финансовый трекер с AI-анализом трат, учётом целей и красивыми графиками.

---

## ✨ Возможности

| Функция | Описание |
|---|---|
| ➕ **Учёт транзакций** | Доходы и расходы по категориям |
| 💼 **Баланс** | Доходы/расходы за месяц + общий капитал |
| 📋 **История** | Последние 10 операций |
| 📊 **Графики** | Круговые и столбчатые диаграммы (тёмный стиль) |
| 🎯 **Цели** | Финансовые цели с прогресс-баром |
| 🤖 **AI-советник** | Анализ ситуации и советы от Claude |

---

## 🚀 Быстрый старт

### 1. Клонировать и установить зависимости

```bash
git clone <your-repo>
cd finance_bot
pip install -r requirements.txt
```

### 2. Создать `.env` файл

```bash
cp .env.example .env
```

Заполни переменные:

```env
BOT_TOKEN=токен от @BotFather
DATABASE_URL=postgresql://user:pass@host:5432/db
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Создать базу данных

```bash
# PostgreSQL должен быть запущен
createdb finance_bot
```

Таблицы создаются автоматически при первом запуске.

### 4. Запустить бота

```bash
python bot.py
```

---

## 📁 Структура проекта

```
finance_bot/
├── bot.py           # Основной файл, handlers
├── database.py      # Работа с PostgreSQL (asyncpg)
├── ai_advisor.py    # AI-анализ через Anthropic API
├── charts.py        # Генерация графиков (matplotlib)
├── keyboards.py     # Inline-клавиатуры
├── config.py        # Конфигурация
├── requirements.txt
└── .env.example
```

---

## 🔑 Где взять токены

### Telegram Bot Token
1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`
3. Следуй инструкциям, получи токен вида `123456789:AAF...`

### Anthropic API Key
1. Зайди на [console.anthropic.com](https://console.anthropic.com)
2. Settings → API Keys → Create Key

### PostgreSQL (бесплатные варианты)
- **Supabase**: [supabase.com](https://supabase.com) — бесплатный PostgreSQL в облаке
- **Railway**: [railway.app](https://railway.app) — $5 free credits
- **Neon**: [neon.tech](https://neon.tech) — бесплатный serverless PostgreSQL
- Локально: `postgresql://localhost/finance_bot`

---

## 📊 Категории расходов

🍕 Еда и рестораны · 🚗 Транспорт · 🏠 Жильё и ЖКХ · 💊 Здоровье · 👗 Одежда · 🎮 Развлечения · 📱 Связь и интернет · 📚 Образование · ✈️ Путешествия · 💪 Спорт · 🛒 Продукты · 💸 Другое

## 💰 Категории доходов

💼 Зарплата · 💻 Фриланс · 📈 Инвестиции · 🎁 Подарки · 🏦 Аренда · 💡 Бонусы · 🛍️ Продажи · 💰 Другое

---

## 🚀 Деплой на сервер

### Railway (рекомендуется)

```bash
# Установи Railway CLI
npm install -g @railway/cli

# Логин и деплой
railway login
railway init
railway up
```

Добавь переменные окружения в Railway Dashboard.

### VPS (systemd)

```ini
# /etc/systemd/system/finance-bot.service
[Unit]
Description=Finance Bot
After=network.target

[Service]
WorkingDirectory=/opt/finance_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
EnvironmentFile=/opt/finance_bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable finance-bot
systemctl start finance-bot
```

---

## 🛠 Расширение бота

**Добавить категорию** → отредактируй списки в `keyboards.py`

**Добавить новую команду** → создай handler в `bot.py`

**Изменить AI-промпт** → отредактируй функции в `ai_advisor.py`

**Добавить поля в БД** → добавь колонки в `database.py` → `_create_tables()`

---

## 📝 Лицензия

MIT — используй как хочешь.
