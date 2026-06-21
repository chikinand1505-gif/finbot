import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

INCOME_CATEGORIES = ["зарплата", "бизнес", "инвестиции", "прочее"]
EXPENSE_CATEGORIES = ["продукты", "кафе", "транспорт", "автомобиль", "стройка", "развлечения", "здоровье", "путешествия", "прочее"]


def parse_transaction(text: str) -> dict | None:
    prompt = f"""Ты парсер финансовых записей. Пользователь написал: "{text}"

Определи является ли это финансовой записью о доходе или расходе.

Категории доходов: {INCOME_CATEGORIES}
Категории расходов: {EXPENSE_CATEGORIES}

Правила выбора категории:
- бетон, кирпич, цемент, стройматериалы, ремонт, плитка → стройка
- еда, продукты, магазин, супермаркет, овощи → продукты
- ресторан, кафе, кофе, обед, ужин, пицца → кафе
- бензин, такси, метро, автобус, парковка → транспорт
- машина, авто, техосмотр, страховка авто → автомобиль
- кино, игры, концерт, подписка → развлечения
- врач, аптека, лекарства, больница → здоровье
- отпуск, билеты, отель, тур → путешествия
- зарплата, аванс, получил зп → зарплата (income)
- фриланс, проект, клиент, продал → бизнес (income)
- дивиденды, акции, вклад → инвестиции (income)

Ответь ТОЛЬКО валидным JSON без пояснений и без markdown:
{{"type": "income или expense", "amount": число, "category": "категория из списка", "description": "краткое описание"}}

Если это НЕ финансовая запись — ответь только словом: null"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.lower() == "null":
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def parse_query(text: str) -> dict | None:
    prompt = f"""Пользователь написал финансовому боту: "{text}"

Это запрос на просмотр финансовых данных? 

Верни ТОЛЬКО JSON без markdown:
{{
  "is_query": true или false,
  "query_type": "expenses_by_period" | "income_by_period" | "category_total" | "balance" | "top_categories",
  "category": "название категории из списка или null",
  "period": "month" | "year" | "week" | "all" | "january".."december"
}}

Категории: продукты, кафе, транспорт, автомобиль, стройка, развлечения, здоровье, путешествия, зарплата, бизнес, инвестиции

Примеры:
- "покажи расходы за июнь" → {{"is_query":true,"query_type":"expenses_by_period","category":null,"period":"june"}}
- "сколько потратил на стройку" → {{"is_query":true,"query_type":"category_total","category":"стройка","period":"all"}}
- "сколько ушло на машину за год" → {{"is_query":true,"query_type":"category_total","category":"автомобиль","period":"year"}}
- "мой баланс" → {{"is_query":true,"query_type":"balance","category":null,"period":"month"}}
- "топ расходов" → {{"is_query":true,"query_type":"top_categories","category":null,"period":"month"}}

Если НЕ запрос данных — верни {{"is_query":false}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except Exception:
        return None


async def get_full_analysis(stats: dict) -> str:
    income = stats.get("income", 0)
    expense = stats.get("expense", 0)
    savings = income - expense
    avg_per_day = expense / 30 if expense > 0 else 0
    categories = stats.get("categories", {})

    top_category = ""
    top_pct = 0
    if categories and expense > 0:
        top_cat_name = max(categories, key=categories.get)
        top_pct = round(categories[top_cat_name] / expense * 100)
        top_category = f"{top_cat_name} — {top_pct}%"

    prompt = f"""Ты персональный финансовый директор. Составь аналитический отчёт за последние 30 дней.

ДАННЫЕ:
- Доходы: {income:,.0f} ₽
- Расходы: {expense:,.0f} ₽
- Накопления: {savings:,.0f} ₽
- Средний расход в день: {avg_per_day:,.0f} ₽
- Топ категория расходов: {top_category}
- Все категории расходов: {categories}

Напиши отчёт ПО ЭТОМУ ШАБЛОНУ (подставь реальные цифры):

За последние 30 дней вы заработали [доходы] ₽.
Потратили [расходы] ₽.
Больше всего денег ушло на [топ категория и процент].
Средний расход в день — [среднее] ₽.
Накопления [увеличились/уменьшились] на [накопления] ₽.

[Пустая строка]
💡 [Один конкретный совет исходя из данных]

Пиши живым языком на русском. Без HTML тегов. Только текст."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
