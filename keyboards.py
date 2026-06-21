from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

EXPENSE_CATEGORIES = [
    "🍕 Еда и рестораны",
    "🚗 Транспорт",
    "🏠 Жильё и ЖКХ",
    "💊 Здоровье",
    "👗 Одежда",
    "🎮 Развлечения",
    "📱 Связь и интернет",
    "📚 Образование",
    "✈️ Путешествия",
    "💪 Спорт",
    "🛒 Продукты",
    "💸 Другое",
]

INCOME_CATEGORIES = [
    "💼 Зарплата",
    "💻 Фриланс",
    "📈 Инвестиции",
    "🎁 Подарки",
    "🏦 Аренда",
    "💡 Бонусы",
    "🛍️ Продажи",
    "💰 Другое",
]


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить запись", callback_data="add_transaction")
    builder.button(text="💼 Мой баланс", callback_data="balance")
    builder.button(text="📋 История", callback_data="history")
    builder.button(text="📊 Отчёты", callback_data="reports")
    builder.button(text="🎯 Цели", callback_data="goals")
    builder.button(text="🤖 AI-советник", callback_data="ai_advisor")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def transaction_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Доход", callback_data="type_income")
    builder.button(text="💸 Расход", callback_data="type_expense")
    builder.button(text="◀️ Назад", callback_data="main_menu")
    builder.adjust(2, 1)
    return builder.as_markup()


def category_kb(t_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    categories = INCOME_CATEGORIES if t_type == "income" else EXPENSE_CATEGORIES
    for cat in categories:
        builder.button(text=cat, callback_data=f"cat_{cat}")
    builder.button(text="◀️ Назад", callback_data="add_transaction")
    builder.adjust(2)
    return builder.as_markup()


def reports_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Расходы по категориям", callback_data="report_expenses")
    builder.button(text="💰 Доходы по категориям", callback_data="report_income")
    builder.button(text="📈 История доходов/расходов", callback_data="report_balance_history")
    builder.button(text="🔍 Анализ расходов AI", callback_data="spending_analysis")
    builder.button(text="◀️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def goals_menu_kb(goals: List[Dict] = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Новая цель", callback_data="add_goal")
    if goals:
        builder.button(text="📊 График целей", callback_data="goals_chart")
        builder.button(text="💰 Пополнить цель", callback_data="update_goal_progress")
    builder.button(text="◀️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel")
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()
