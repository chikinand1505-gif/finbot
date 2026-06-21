import os
import anthropic
from typing import List, Dict, Optional

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _format_transactions(transactions: List[Dict]) -> str:
    if not transactions:
        return "Транзакций нет."
    lines = []
    for t in transactions[:20]:
        sign = "+" if t["type"] == "income" else "-"
        date = t["created_at"].strftime("%d.%m.%Y")
        lines.append(f"{date} | {sign}{t['amount']:,.0f} ₽ | {t['category']} | {t.get('description', '')}")
    return "\n".join(lines)


def _format_goals(goals: List[Dict]) -> str:
    if not goals:
        return "Целей нет."
    lines = []
    for g in goals:
        progress = (g["current_amount"] / g["target_amount"]) * 100
        deadline = g["deadline"].strftime("%d.%m.%Y") if g.get("deadline") else "не указан"
        lines.append(
            f"- {g['name']}: {g['current_amount']:,.0f} / {g['target_amount']:,.0f} ₽ "
            f"({progress:.0f}%), дедлайн: {deadline}"
        )
    return "\n".join(lines)


async def get_ai_advice(
    transactions: List[Dict],
    goals: List[Dict],
    monthly_stats: Dict
) -> str:
    income = monthly_stats.get("income", 0)
    expense = monthly_stats.get("expense", 0)
    net = income - expense

    transactions_text = _format_transactions(transactions)
    goals_text = _format_goals(goals)

    prompt = f"""Ты — персональный AI-финансовый директор. Проанализируй финансовую ситуацию пользователя и дай конкретные советы.

ДАННЫЕ ЗА ТЕКУЩИЙ МЕСЯЦ:
- Доходы: {income:,.0f} ₽
- Расходы: {expense:,.0f} ₽
- Баланс месяца: {net:,.0f} ₽

ПОСЛЕДНИЕ ТРАНЗАКЦИИ:
{transactions_text}

ФИНАНСОВЫЕ ЦЕЛИ:
{goals_text}

Дай краткий анализ (3-4 абзаца) в формате для Telegram с HTML-тегами (<b> для жирного).
Структура:
1. <b>💡 Общая оценка</b> — как дела в целом
2. <b>⚠️ На что обратить внимание</b> — риски или проблемные паттерны
3. <b>🎯 Советы</b> — 2-3 конкретных действия для улучшения ситуации
4. <b>🚀 Прогноз по целям</b> — реалистично ли достичь целей при текущем темпе

Будь конкретным, используй цифры. Пиши на русском языке. Не используй *, только <b> теги."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


async def get_spending_analysis(category_breakdown: List[Dict]) -> str:
    if not category_breakdown:
        return "📭 Нет данных о расходах за этот месяц."

    total = sum(c["total"] for c in category_breakdown)
    breakdown_text = "\n".join(
        f"- {c['category']}: {c['total']:,.0f} ₽ ({c['total']/total*100:.1f}%)"
        for c in category_breakdown
    )

    prompt = f"""Ты — персональный AI-финансовый директор. Проанализируй структуру расходов.

РАСХОДЫ ПО КАТЕГОРИЯМ (текущий месяц):
{breakdown_text}
Итого: {total:,.0f} ₽

Дай краткий анализ (2-3 абзаца) в формате для Telegram с HTML-тегами (<b> для жирного).
Структура:
1. <b>📊 Структура расходов</b> — оцени распределение, что бросается в глаза
2. <b>✂️ Где можно сократить</b> — конкретные категории и суммы
3. <b>💡 Рекомендация</b> — один главный совет по оптимизации

Будь конкретным с цифрами. Пиши на русском языке. Не используй *, только <b> теги."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text
