import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_TOKEN
from database import db
from ai_parser import parse_transaction, parse_query, get_full_analysis
from charts import generate_expense_chart, generate_balance_chart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

PERIOD_RU = {
    "month": "текущий месяц", "year": "текущий год",
    "week": "последние 7 дней", "all": "всё время",
    "january": "январь", "february": "февраль", "march": "март",
    "april": "апрель", "may": "май", "june": "июнь",
    "july": "июль", "august": "август", "september": "сентябрь",
    "october": "октябрь", "november": "ноябрь", "december": "декабрь",
}

CURRENCY_SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€", "USDT": "₮", "BTC": "₿"}
ASSET_TYPES = {
    "bank": "🏦 Банковский счёт",
    "cash": "💵 Наличные",
    "stablecoin": "🔵 Стейблкоин",
    "crypto": "₿ Крипто",
    "realty": "🏠 Недвижимость",
    "car": "🚗 Авто/Имущество",
    "invest": "📈 Инвестиции",
    "debt_in": "📥 Мне должны",
    "debt_out": "📤 Я должен",
}

class AddAsset(StatesGroup):
    choosing_type = State()
    entering_custom_type = State()
    entering_name = State()
    entering_amount = State()
    entering_currency = State()

class AddCrypto(StatesGroup):
    entering_ticker = State()
    confirming_coin = State()
    entering_amount = State()

class EditAsset(StatesGroup):
    choosing_asset = State()
    entering_amount = State()

def main_kb():
    b = InlineKeyboardBuilder()
    b.button(text="💸 Учёт финансов", callback_data="section_finance")
    b.button(text="🏦 Мой капитал", callback_data="section_capital")
    b.adjust(1)
    return b.as_markup()

def finance_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📋 История", callback_data="fin_history")
    b.button(text="💼 Баланс месяца", callback_data="fin_balance")
    b.button(text="📊 Графики", callback_data="fin_charts")
    b.button(text="🤖 AI-анализ", callback_data="fin_analysis")
    b.button(text="🎯 Цели", callback_data="fin_goals")
    b.button(text="◀️ Главное меню", callback_data="main_menu")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()

def capital_kb():
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить актив", callback_data="cap_add")
    b.button(text="✏️ Обновить сумму", callback_data="cap_edit")
    b.button(text="🗑 Удалить актив", callback_data="cap_delete")
    b.button(text="📊 Сводка", callback_data="cap_summary")
    b.button(text="◀️ Главное меню", callback_data="main_menu")
    b.adjust(2, 1, 1, 1)
    return b.as_markup()

def asset_type_kb():
    b = InlineKeyboardBuilder()
    for key, label in ASSET_TYPES.items():
        if key == "crypto":
            b.button(text=label, callback_data="cap_add_crypto")
        elif key == "stablecoin":
            b.button(text=label, callback_data="cap_add_stablecoin")
        else:
            b.button(text=label, callback_data=f"asset_type_{key}")
    b.button(text="✏️ Свой тип", callback_data="asset_type_custom")
    b.button(text="◀️ Назад", callback_data="section_capital")
    b.adjust(2)
    return b.as_markup()

def currency_kb():
    b = InlineKeyboardBuilder()
    for c in ["RUB", "USD", "EUR", "USDT", "BTC"]:
        b.button(text=c, callback_data=f"currency_{c}")
    b.adjust(3)
    return b.as_markup()

def cancel_kb(back="main_menu"):
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data=back)
    return b.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await db.create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Я твой <b>персональный финансовый директор</b> 💼\n\n"
        "Просто пиши мне о тратах:\n"
        "• <i>Потратил 3500 на бетон</i>\n"
        "• <i>Получил зарплату 80000</i>\n\n"
        "Или выбери раздел 👇",
        parse_mode="HTML",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data == "main_menu")
async def back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📋 Главное меню:", reply_markup=main_kb())

@dp.callback_query(F.data == "section_finance")
async def section_finance(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💸 <b>Учёт финансов</b>\n\n"
        "Просто напиши мне о трате или доходе:\n"
        "• <i>Потратил 3500 на бетон</i>\n"
        "• <i>Купил продукты на 2400</i>\n"
        "• <i>Получил зарплату 80000</i>\n"
        "• <i>Сколько потратил на стройку</i>\n\n"
        "Или выбери действие:",
        parse_mode="HTML",
        reply_markup=finance_kb()
    )

@dp.callback_query(F.data == "fin_balance")
async def fin_balance(callback: types.CallbackQuery):
    stats = await db.get_monthly_stats(callback.from_user.id)
    total = await db.get_total_balance(callback.from_user.id)
    income = stats.get("income", 0)
    expense = stats.get("expense", 0)
    net = income - expense
    await callback.message.edit_text(
        f"💼 <b>Баланс за текущий месяц</b>\n\n"
        f"💰 Доходы: <b>+{income:,.0f} ₽</b>\n"
        f"💸 Расходы: <b>-{expense:,.0f} ₽</b>\n"
        f"{'📈' if net >= 0 else '📉'} Итого: <b>{'+' if net >= 0 else ''}{net:,.0f} ₽</b>\n\n"
        f"🏦 Общий баланс трат: <b>{total:,.0f} ₽</b>",
        parse_mode="HTML", reply_markup=finance_kb()
    )

@dp.callback_query(F.data == "fin_history")
async def fin_history(callback: types.CallbackQuery):
    txs = await db.get_recent_transactions(callback.from_user.id, 10)
    if not txs:
        await callback.message.edit_text("📭 Нет записей.", reply_markup=finance_kb())
        return
    text = "📋 <b>Последние записи</b>\n\nНажми 🗑 рядом с записью чтобы удалить:\n\n"
    b = InlineKeyboardBuilder()
    for t in txs:
        emoji = "💰" if t["type"] == "income" else "💸"
        sign = "+" if t["type"] == "income" else "-"
        date = t["created_at"].strftime("%d.%m")
        desc = f" · {t['description']}" if t["description"] else ""
        label = f"{emoji} {date} | {sign}{t['amount']:,.0f} ₽ | {t['category']}{desc}"
        text += f"{label}\n"
        b.button(text=f"🗑 {date} | {sign}{t['amount']:,.0f} ₽ | {t['category']}", callback_data=f"del_tx_{t['id']}")
    b.button(text="◀️ Назад", callback_data="section_finance")
    b.adjust(1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())


@dp.callback_query(F.data.startswith("del_tx_"))
async def delete_transaction(callback: types.CallbackQuery):
    tx_id = int(callback.data.replace("del_tx_", ""))
    deleted = await db.delete_transaction(tx_id, callback.from_user.id)
    if deleted:
        await callback.answer("✅ Запись удалена!", show_alert=False)
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)
        return
    # Refresh history
    txs = await db.get_recent_transactions(callback.from_user.id, 10)
    if not txs:
        await callback.message.edit_text("📭 Нет записей.", reply_markup=finance_kb())
        return
    text = "📋 <b>Последние записи</b>\n\nНажми 🗑 рядом с записью чтобы удалить:\n\n"
    b = InlineKeyboardBuilder()
    for t in txs:
        emoji = "💰" if t["type"] == "income" else "💸"
        sign = "+" if t["type"] == "income" else "-"
        date = t["created_at"].strftime("%d.%m")
        desc = f" · {t['description']}" if t["description"] else ""
        text += f"{emoji} {date} | {sign}{t['amount']:,.0f} ₽ | {t['category']}{desc}\n"
        b.button(text=f"🗑 {date} | {sign}{t['amount']:,.0f} ₽ | {t['category']}", callback_data=f"del_tx_{t['id']}")
    b.button(text="◀️ Назад", callback_data="section_finance")
    b.adjust(1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=b.as_markup())

@dp.callback_query(F.data == "fin_charts")
async def fin_charts(callback: types.CallbackQuery):
    data = await db.get_category_breakdown(callback.from_user.id, "expense")
    if not data:
        await callback.message.edit_text("📭 Нет расходов за текущий месяц.", reply_markup=finance_kb())
        return
    await callback.answer("Генерирую график...")
    chart = generate_expense_chart(data, "Расходы по категориям")
    await bot.send_photo(
        callback.from_user.id,
        BufferedInputFile(chart.getvalue(), "chart.png"),
        caption="📊 <b>Расходы по категориям</b> (текущий месяц)",
        parse_mode="HTML"
    )
    history = await db.get_monthly_history(callback.from_user.id)
    if len(history) >= 2:
        chart2 = generate_balance_chart(history)
        await bot.send_photo(
            callback.from_user.id,
            BufferedInputFile(chart2.getvalue(), "history.png"),
            caption="📈 <b>История доходов и расходов</b>",
            parse_mode="HTML"
        )
    await callback.message.edit_reply_markup(reply_markup=finance_kb())

@dp.callback_query(F.data == "fin_analysis")
async def fin_analysis(callback: types.CallbackQuery):
    await callback.message.edit_text("🤖 <b>AI-анализ</b>\n\n⏳ Анализирую...", parse_mode="HTML")
    stats = await db.get_last_30_days_stats(callback.from_user.id)
    if stats["income"] == 0 and stats["expense"] == 0:
        await callback.message.edit_text("📭 Нет данных за 30 дней.", reply_markup=finance_kb())
        return
    try:
        analysis = await get_full_analysis(stats)
        await callback.message.edit_text(
            f"🤖 <b>AI-анализ за 30 дней</b>\n\n{analysis}",
            parse_mode="HTML", reply_markup=finance_kb()
        )
    except Exception:
        await callback.message.edit_text(
            "⚠️ AI-анализ недоступен — пополни баланс на console.anthropic.com",
            reply_markup=finance_kb()
        )

@dp.callback_query(F.data == "fin_goals")
async def fin_goals(callback: types.CallbackQuery):
    goals = await db.get_goals(callback.from_user.id)
    if not goals:
        await callback.message.edit_text(
            "🎯 Нет целей.\n\nДобавь командой:\n<b>/новаяцель Отпуск 150000</b>",
            parse_mode="HTML", reply_markup=finance_kb()
        )
        return
    text = "🎯 <b>Финансовые цели</b>\n\n"
    for g in goals:
        pct = min(float(g["current_amount"]) / float(g["target_amount"]) * 100, 100)
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        dl = g["deadline"].strftime("%d.%m.%Y") if g["deadline"] else "без срока"
        text += f"<b>{g['name']}</b>\n{bar} {pct:.0f}%\n💰 {float(g['current_amount']):,.0f} / {float(g['target_amount']):,.0f} ₽ | {dl}\n\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=finance_kb())

# ── CAPITAL ───────────────────────────────────────────────────────────────────

def get_asset_label(asset_type: str) -> str:
    if asset_type in ASSET_TYPES:
        return ASSET_TYPES[asset_type]
    if asset_type.startswith("custom_"):
        return f"🔷 {asset_type.replace('custom_', '')}"
    return f"🔷 {asset_type}"


async def get_exchange_rates() -> dict:
    """Fetch live exchange rates. USDT from P2P sources, BTC from CoinGecko, USD/EUR from CBR."""
    import aiohttp
    rates = {"RUB": 1.0}

    async with aiohttp.ClientSession() as session:

        # USDT/RUB — пробуем несколько источников по порядку
        usdt_rub = None

        # 1. Garantex (российская P2P биржа, реальный рыночный курс)
        try:
            async with session.get(
                "https://garantex.org/api/v2/depth?market=usdtrub",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    bids = data.get("bids", [])
                    if bids:
                        usdt_rub = float(bids[0]["price"])
        except Exception:
            pass

        # 2. Binance P2P через их API (если Garantex недоступен)
        if not usdt_rub:
            try:
                async with session.post(
                    "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
                    json={
                        "asset": "USDT",
                        "fiat": "RUB",
                        "merchantCheck": False,
                        "page": 1,
                        "payTypes": [],
                        "rows": 3,
                        "tradeType": "BUY"
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        ads = data.get("data", [])
                        if ads:
                            prices = [float(ad["adv"]["price"]) for ad in ads[:3]]
                            usdt_rub = sum(prices) / len(prices)
            except Exception:
                pass

        # 3. CoinGecko как запасной (менее точный)
        if not usdt_rub:
            try:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        usdt_rub = data["tether"]["rub"]
            except Exception:
                pass

        rates["USDT"] = usdt_rub or 77.0

        # BTC/RUB через USDT (BTC/USDT * USDT/RUB)
        try:
            async with session.get(
                "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    rates["BTC"] = float(data["price"]) * rates["USDT"]
        except Exception:
            rates["BTC"] = 9_000_000.0

        # USD и EUR от ЦБ
        try:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    rates["USD"] = data["Valute"]["USD"]["Value"]
                    rates["EUR"] = data["Valute"]["EUR"]["Value"]
        except Exception:
            rates["USD"] = rates["USDT"]
            rates["EUR"] = rates["USDT"] * 1.08

    return rates


def rub_to_usd(rub: float, rates: dict) -> float:
    usd_rate = rates.get("USD", 77.0)
    return rub / usd_rate if usd_rate else 0


def build_capital_totals(assets: list, rates: dict) -> tuple[dict, dict, float, float]:
    """
    Returns:
      currency_totals_assets  — {currency: amount} for non-debt assets
      currency_totals_debts   — {currency: amount} for debt_out
      total_rub_assets        — all assets converted to RUB
      total_rub_debts         — all debts converted to RUB
    """
    cur_assets: dict = {}
    cur_debts: dict = {}
    total_rub_assets = 0.0
    total_rub_debts = 0.0

    for a in assets:
        amt = float(a["amount"])
        cur = a["currency"]
        rate = rates.get(cur, 1.0)
        rub_val = amt * rate

        if a["asset_type"] == "debt_out":
            cur_debts[cur] = cur_debts.get(cur, 0.0) + amt
            total_rub_debts += rub_val
        else:
            cur_assets[cur] = cur_assets.get(cur, 0.0) + amt
            total_rub_assets += rub_val

    return cur_assets, cur_debts, total_rub_assets, total_rub_debts


@dp.callback_query(F.data == "section_capital")
async def section_capital(callback: types.CallbackQuery):
    assets = await db.get_assets(callback.from_user.id)
    crypto_assets = await db.get_crypto_assets(callback.from_user.id)

    if not assets and not crypto_assets:
        await callback.message.edit_text(
            "🏦 <b>Мой капитал</b>\n\n"
            "Отслеживай всё своё имущество:\n"
            "🏦 Банковские счета\n🏠 Недвижимость\n"
            "🚗 Авто и имущество\n₿ Крипто-портфель\n"
            "📥 Долги (тебе и твои)\n\nДобавь первый актив 👇",
            parse_mode="HTML", reply_markup=capital_kb()
        )
        return

    rates = await get_exchange_rates()
    usdt_rate = rates.get("USDT", 72.5)
    cur_assets, cur_debts, total_rub_assets, total_rub_debts = build_capital_totals(assets, rates)

    # Crypto — split into stablecoins and coins by is_stablecoin flag
    crypto_total_rub = 0.0
    crypto_total_usdt = 0.0
    stable_total_usdt = 0.0
    stable_total_rub = 0.0
    crypto_text = ""
    stable_text = ""

    if crypto_assets:
        import aiohttp
        coin_ids = list({c["coin_id"] for c in crypto_assets})
        prices = {}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coin_ids)}&vs_currencies=rub,usd",
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as r:
                    if r.status == 200:
                        prices = await r.json()
        except Exception:
            pass

        stablecoins = [c for c in crypto_assets if c.get("is_stablecoin")]
        coins = [c for c in crypto_assets if not c.get("is_stablecoin")]

        if stablecoins:
            stable_text = "🔵 <b>Стейблкоины</b>\n"
            for c in stablecoins:
                price_usd = prices.get(c["coin_id"], {}).get("usd", 1.0)
                price_rub = prices.get(c["coin_id"], {}).get("rub", usdt_rate)
                val_usdt = float(c["amount"]) * price_usd
                val_rub = float(c["amount"]) * price_rub
                stable_total_usdt += val_usdt
                stable_total_rub += val_rub
                stable_text += f"  • <b>{c['coin_symbol']}</b> {float(c['amount']):,.2f} → <b>{val_usdt:,.2f} ₮</b> / <b>{val_rub:,.0f} ₽</b>\n"
            stable_text += "\n"

        if coins:
            crypto_text = "₿ <b>Крипто-портфель</b>\n"
            for c in coins:
                price_rub = prices.get(c["coin_id"], {}).get("rub", 0)
                val_rub = float(c["amount"]) * price_rub
                val_usdt = val_rub / usdt_rate if usdt_rate else 0
                crypto_total_rub += val_rub
                crypto_total_usdt += val_usdt
                crypto_text += f"  • <b>{c['coin_symbol']}</b> {float(c['amount']):,.4f} → <b>{val_rub:,.0f} ₽</b> / <b>{val_usdt:,.0f} ₮</b>\n"
            crypto_text += "  <i>/крипто — подробности</i>\n\n"


    # Regular assets
    text = "🏦 <b>Мой капитал</b>\n\n"
    groups = {}
    for a in assets:
        groups.setdefault(a["asset_type"], []).append(a)
    for asset_type, items in groups.items():
        text += f"{get_asset_label(asset_type)}\n"
        for a in items:
            cur = a["currency"]
            sym = CURRENCY_SYMBOLS.get(cur, cur)
            orig = float(a["amount"])
            rub_val = orig * rates.get(cur, 1.0)
            usdt_val = rub_val / usdt_rate if usdt_rate else 0
            if cur == "RUB":
                text += f"  • {a['name']}: <b>{orig:,.0f} ₽</b> / <b>{orig/usdt_rate:,.0f} ₮</b>\n"
            elif cur == "USDT":
                text += f"  • {a['name']}: <b>{orig:,.2f} ₮</b> / <b>{rub_val:,.0f} ₽</b>\n"
            else:
                text += f"  • {a['name']}: <b>{orig:,.2f} {sym}</b> / <b>{rub_val:,.0f} ₽</b> / <b>{usdt_val:,.0f} ₮</b>\n"
        text += "\n"

    text += stable_text
    text += crypto_text
    total_all_rub = total_rub_assets + crypto_total_rub + stable_total_rub
    net_rub = total_all_rub - total_rub_debts
    net_usdt = net_rub / usdt_rate if usdt_rate else 0

    text += "━━━━━━━━━━━━━━━\n"
    if total_rub_assets > 0:
        text += f"📦 Активы: <b>{total_rub_assets:,.0f} ₽</b> / <b>{total_rub_assets/usdt_rate:,.0f} ₮</b>\n"
    if stable_total_usdt > 0:
        text += f"🔵 Стейблкоины: <b>{stable_total_usdt:,.2f} ₮</b> / <b>{stable_total_rub:,.0f} ₽</b>\n"
    if crypto_total_rub > 0:
        text += f"₿ Крипто: <b>{crypto_total_rub:,.0f} ₽</b> / <b>{crypto_total_usdt:,.0f} ₮</b>\n"
    if total_rub_debts > 0:
        text += f"📤 Долги: <b>-{total_rub_debts:,.0f} ₽</b> / <b>-{total_rub_debts/usdt_rate:,.0f} ₮</b>\n"
    text += f"\n💎 <b>Чистый капитал:</b>\n  <b>{net_rub:,.0f} ₽</b>\n  <b>{net_usdt:,.0f} ₮</b>"
    now = datetime.now().strftime("%H:%M")
    text += f"\n\n<i>🕐 {now} | 1 ₮ = {usdt_rate:,.1f} ₽</i>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=capital_kb())

@dp.callback_query(F.data == "cap_summary")
async def cap_summary(callback: types.CallbackQuery):
    assets = await db.get_assets(callback.from_user.id)
    crypto_assets = await db.get_crypto_assets(callback.from_user.id)
    if not assets and not crypto_assets:
        await callback.answer("Нет активов!", show_alert=True)
        return

    rates = await get_exchange_rates()
    usd_rate = rates.get("USD", 72.5)
    cur_assets, cur_debts, total_rub_assets, total_rub_debts = build_capital_totals(assets, rates)

    # Crypto totals
    crypto_total_rub = 0.0
    if crypto_assets:
        coin_ids = list({c["coin_id"] for c in crypto_assets})
        prices = await get_crypto_prices_rub(coin_ids)
        for c in crypto_assets:
            price_rub = prices.get(c["coin_id"], {}).get("rub", 0)
            crypto_total_rub += float(c["amount"]) * price_rub

    total_all_rub = total_rub_assets + crypto_total_rub
    net_rub = total_all_rub - total_rub_debts
    net_usd = net_rub / usd_rate

    # By type
    type_totals = {}
    for a in assets:
        label = get_asset_label(a["asset_type"])
        rub_val = float(a["amount"]) * rates.get(a["currency"], 1.0)
        type_totals[label] = type_totals.get(label, 0.0) + rub_val
    if crypto_total_rub > 0:
        type_totals["₿ Крипто-портфель"] = crypto_total_rub

    text = "📊 <b>Структура капитала</b>\n\n"
    for label, amt in sorted(type_totals.items(), key=lambda x: -x[1]):
        pct = amt / total_all_rub * 100 if total_all_rub > 0 else 0
        usd_amt = amt / usd_rate
        text += f"{label}:\n  <b>{amt:,.0f} ₽</b> / <b>${usd_amt:,.0f}</b> ({pct:.0f}%)\n"

    text += f"\n━━━━━━━━━━━━━━━\n"
    text += f"📦 Всего активов:\n  <b>{total_all_rub:,.0f} ₽</b> / <b>${total_all_rub/usd_rate:,.0f}</b>\n"
    if total_rub_debts > 0:
        text += f"📤 Долги:\n  <b>-{total_rub_debts:,.0f} ₽</b> / <b>-${total_rub_debts/usd_rate:,.0f}</b>\n"
    text += f"\n💎 <b>Чистый капитал:</b>\n  <b>{net_rub:,.0f} ₽</b>\n  <b>${net_usd:,.0f}</b>"

    now = datetime.now().strftime("%H:%M")
    text += f"\n\n<i>🕐 {now} | 1$ = {usd_rate:,.1f} ₽</i>"

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=capital_kb())

async def search_coin_on_coingecko(ticker: str) -> dict | None:
    """Search coin by ticker. Tries multiple methods with fallbacks."""
    import aiohttp
    import asyncio

    ticker = ticker.strip().lower()

    # Known coins map to avoid API calls for popular tickers
    KNOWN_COINS = {
        "btc": ("bitcoin", "Bitcoin", "BTC"),
        "eth": ("ethereum", "Ethereum", "ETH"),
        "usdt": ("tether", "Tether", "USDT"),
        "usdc": ("usd-coin", "USD Coin", "USDC"),
        "bnb": ("binancecoin", "BNB", "BNB"),
        "sol": ("solana", "Solana", "SOL"),
        "xrp": ("ripple", "XRP", "XRP"),
        "ton": ("the-open-network", "Toncoin", "TON"),
        "doge": ("dogecoin", "Dogecoin", "DOGE"),
        "ada": ("cardano", "Cardano", "ADA"),
        "trx": ("tron", "TRON", "TRX"),
        "avax": ("avalanche-2", "Avalanche", "AVAX"),
        "dot": ("polkadot", "Polkadot", "DOT"),
        "matic": ("matic-network", "Polygon", "MATIC"),
        "link": ("chainlink", "Chainlink", "LINK"),
        "shib": ("shiba-inu", "Shiba Inu", "SHIB"),
        "ltc": ("litecoin", "Litecoin", "LTC"),
        "dai": ("dai", "Dai", "DAI"),
        "uni": ("uniswap", "Uniswap", "UNI"),
        "atom": ("cosmos", "Cosmos", "ATOM"),
        "near": ("near", "NEAR Protocol", "NEAR"),
        "apt": ("aptos", "Aptos", "APT"),
        "op": ("optimism", "Optimism", "OP"),
        "arb": ("arbitrum", "Arbitrum", "ARB"),
        "not": ("notcoin", "Notcoin", "NOT"),
        "pepe": ("pepe", "Pepe", "PEPE"),
    }

    coin_id, coin_name, coin_symbol = None, None, None

    # Check known coins first (no API call needed)
    if ticker in KNOWN_COINS:
        coin_id, coin_name, coin_symbol = KNOWN_COINS[ticker]
    else:
        # Search via CoinGecko API
        import aiohttp
        headers = {"Accept": "application/json"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    f"https://api.coingecko.com/api/v3/search?query={ticker}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    if r.status == 429:
                        # Rate limited — wait and retry once
                        await asyncio.sleep(3)
                        async with session.get(
                            f"https://api.coingecko.com/api/v3/search?query={ticker}",
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as r2:
                            if r2.status == 200:
                                data = await r2.json()
                            else:
                                return None
                    elif r.status == 200:
                        data = await r.json()
                    else:
                        return None

                    coins = data.get("coins", [])
                    if not coins:
                        return None
                    # Prefer exact symbol match
                    coin = next((c for c in coins if c["symbol"].lower() == ticker), coins[0])
                    coin_id = coin["id"]
                    coin_name = coin["name"]
                    coin_symbol = coin["symbol"].upper()
        except Exception:
            return None

    if not coin_id:
        return None

    # Get price in RUB
    try:
        async with aiohttp.ClientSession() as session:
            await asyncio.sleep(0.5)  # Small delay to avoid rate limit
            async with session.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=rub,usd",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 429:
                    await asyncio.sleep(3)
                    async with session.get(
                        f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=rub,usd",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r2:
                        if r2.status == 200:
                            price_data = await r2.json()
                        else:
                            return None
                elif r.status == 200:
                    price_data = await r.json()
                else:
                    return None

                price_rub = price_data.get(coin_id, {}).get("rub", 0)
                price_usd = price_data.get(coin_id, {}).get("usd", 0)

                return {
                    "id": coin_id,
                    "name": coin_name,
                    "symbol": coin_symbol,
                    "price_rub": price_rub,
                    "price_usd": price_usd,
                }
    except Exception:
        return None


async def get_crypto_prices_rub(coin_ids: list[str]) -> dict:
    """Get current RUB prices for list of CoinGecko coin IDs."""
    import aiohttp
    if not coin_ids:
        return {}
    ids_str = ",".join(coin_ids)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=rub",
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status == 200:
                    return await r.json()
    except Exception:
        pass
    return {}


# ── CRYPTO PORTFOLIO HANDLERS ─────────────────────────────────────────────────

@dp.callback_query(F.data == "cap_add_stablecoin")
async def cap_add_stablecoin_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddCrypto.entering_ticker)
    await state.update_data(is_stablecoin=True)
    await callback.message.edit_text(
        "🔵 <b>Добавить стейблкоин</b>\n\n"
        "Введи тикер:\n\n"
        "• <code>USDT</code>\n"
        "• <code>USDC</code>\n"
        "• <code>DAI</code>\n"
        "• <code>BUSD</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb("section_capital")
    )


@dp.callback_query(F.data == "cap_add_crypto")
async def cap_add_crypto_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddCrypto.entering_ticker)
    await state.update_data(is_stablecoin=False)
    await callback.message.edit_text(
        "₿ <b>Добавить монету</b>\n\n"
        "Введи тикер или название монеты:\n\n"
        "Примеры:\n"
        "• <code>BTC</code>\n"
        "• <code>ETH</code>\n"
        "• <code>SOL</code>\n"
        "• <code>TON</code>\n"
        "• <code>DOGE</code>\n\n"
        "⚠️ USDT и USDC добавляй в раздел 🔵 Стейблкоин\n\n"
        "Поддерживаются любые монеты с CoinGecko 🌐",
        parse_mode="HTML",
        reply_markup=cancel_kb("section_capital")
    )


@dp.message(AddCrypto.entering_ticker)
async def cap_crypto_search(message: types.Message, state: FSMContext):
    ticker = message.text.strip()
    await message.answer(f"🔍 Ищу <b>{ticker.upper()}</b> на CoinGecko...", parse_mode="HTML")

    coin = await search_coin_on_coingecko(ticker)
    if not coin:
        await message.answer(
            f"❌ Монета <b>{ticker.upper()}</b> не найдена.\n\n"
            f"Попробуй:\n"
            f"• Проверь тикер (BTC, ETH, SOL, TON...)\n"
            f"• Подожди 10 секунд и попробуй снова\n"
            f"• Напиши полное название монеты",
            parse_mode="HTML",
            reply_markup=cancel_kb("section_capital")
        )
        return

    await state.update_data(coin=coin)
    await state.set_state(AddCrypto.confirming_coin)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, это она!", callback_data="crypto_confirm")
    b.button(text="❌ Нет, другая", callback_data="crypto_retry")
    b.adjust(2)

    await message.answer(
        f"Нашёл монету:\n\n"
        f"🪙 <b>{coin['name']}</b> ({coin['symbol']})\n"
        f"💰 Текущий курс: <b>{coin['price_usd']:,.4f} ₮</b>\n\n"
        f"Это то что ищешь?",
        parse_mode="HTML",
        reply_markup=b.as_markup()
    )


@dp.callback_query(F.data == "crypto_retry", AddCrypto.confirming_coin)
async def cap_crypto_retry(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddCrypto.entering_ticker)
    await callback.message.edit_text(
        "Введи другой тикер или название:",
        reply_markup=cancel_kb("section_capital")
    )


@dp.callback_query(F.data == "crypto_confirm", AddCrypto.confirming_coin)
async def cap_crypto_confirmed(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddCrypto.entering_amount)
    data = await state.get_data()
    coin = data["coin"]
    await callback.message.edit_text(
        f"🪙 <b>{coin['name']}</b> ({coin['symbol']})\n\n"
        f"Сколько монет у тебя есть?\n"
        f"Например: <code>0.5</code> или <code>1.672</code> или <code>1500.5</code>\n"
        f"<i>Точность до 8 знаков после запятой</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb("section_capital")
    )


@dp.message(AddCrypto.entering_amount)
async def cap_crypto_save(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи корректное количество:", reply_markup=cancel_kb("section_capital"))
        return

    data = await state.get_data()
    coin = data["coin"]
    is_stablecoin = data.get("is_stablecoin", False)
    await state.clear()

    total_usdt = amount * coin["price_usd"]

    await db.add_crypto_asset(
        user_id=message.from_user.id,
        coin_id=coin["id"],
        coin_symbol=coin["symbol"],
        coin_name=coin["name"],
        amount=amount,
        is_stablecoin=is_stablecoin
    )

    type_label = "🔵 Стейблкоин" if is_stablecoin else "₿ Монета"
    await message.answer(
        f"✅ <b>Добавлено!</b>\n\n"
        f"{type_label}: {coin['name']} ({coin['symbol']})\n"
        f"📦 Количество: <b>{amount:,.8f}".rstrip('0').rstrip('.') + "</b>\n"
        f"💰 По текущему курсу: <b>{total_usdt:,.2f} ₮</b>\n"
        f"📈 Курс: {coin['price_usd']:,.4f} ₮/{coin['symbol']}",
        parse_mode="HTML",
        reply_markup=capital_kb()
    )


@dp.callback_query(F.data == "cap_add")
async def cap_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddAsset.choosing_type)
    await callback.message.edit_text(
        "➕ <b>Добавить актив</b>\n\nВыбери тип:",
        parse_mode="HTML", reply_markup=asset_type_kb()
    )

@dp.callback_query(F.data == "asset_type_custom", AddAsset.choosing_type)
async def cap_choose_custom_type(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddAsset.entering_custom_type)
    await callback.message.edit_text(
        "✏️ <b>Свой тип актива</b>\n\n"
        "Напиши название типа. Примеры:\n"
        "• Золото\n"
        "• Бизнес/оборот\n"
        "• Ценные бумаги\n"
        "• Предметы искусства\n"
        "• Займ другу",
        parse_mode="HTML",
        reply_markup=cancel_kb("section_capital")
    )

@dp.message(AddAsset.entering_custom_type)
async def cap_enter_custom_type(message: types.Message, state: FSMContext):
    custom_type = message.text.strip()
    await state.update_data(asset_type=f"custom_{custom_type}", asset_label=custom_type)
    await state.set_state(AddAsset.entering_name)
    await message.answer(
        f"✅ Тип: <b>{custom_type}</b>\n\nКак называется актив?\nНапример: Золото Сбербанк, ООО Ромашка",
        parse_mode="HTML",
        reply_markup=cancel_kb("section_capital")
    )

@dp.callback_query(F.data.startswith("asset_type_"), AddAsset.choosing_type)
async def cap_choose_type(callback: types.CallbackQuery, state: FSMContext):
    asset_type = callback.data.replace("asset_type_", "")
    await state.update_data(asset_type=asset_type, asset_label=ASSET_TYPES.get(asset_type, asset_type))
    await state.set_state(AddAsset.entering_name)
    label = ASSET_TYPES.get(asset_type, asset_type)
    await callback.message.edit_text(
        f"{label}\n\nКак называется?\nНапример: Сбербанк, Квартира Москва, Tesla акции",
        reply_markup=cancel_kb("section_capital")
    )

@dp.message(AddAsset.entering_name)
async def cap_enter_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddAsset.entering_amount)
    await message.answer("💵 Введи сумму (только цифры):", reply_markup=cancel_kb("section_capital"))

@dp.message(AddAsset.entering_amount)
async def cap_enter_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи корректную сумму:", reply_markup=cancel_kb("section_capital"))
        return
    await state.update_data(amount=amount)
    await state.set_state(AddAsset.entering_currency)
    await message.answer("💱 Выбери валюту:", reply_markup=currency_kb())

@dp.callback_query(F.data.startswith("currency_"), AddAsset.entering_currency)
async def cap_enter_currency(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.replace("currency_", "")
    data = await state.get_data()
    await state.clear()
    await db.add_asset(
        user_id=callback.from_user.id,
        asset_type=data["asset_type"],
        name=data["name"],
        amount=data["amount"],
        currency=currency
    )
    sym = CURRENCY_SYMBOLS.get(currency, currency)
    label = data.get("asset_label", ASSET_TYPES.get(data["asset_type"], data["asset_type"]))
    await callback.message.edit_text(
        f"✅ <b>Актив добавлен!</b>\n\n{label}\n📌 {data['name']}\n💰 {data['amount']:,.0f} {sym}",
        parse_mode="HTML", reply_markup=capital_kb()
    )

@dp.callback_query(F.data == "cap_edit")
async def cap_edit_start(callback: types.CallbackQuery, state: FSMContext):
    assets = await db.get_assets(callback.from_user.id)
    crypto_assets = await db.get_crypto_assets(callback.from_user.id)

    if not assets and not crypto_assets:
        await callback.answer("Нет активов для обновления!", show_alert=True)
        return

    b = InlineKeyboardBuilder()
    for a in assets:
        sym = CURRENCY_SYMBOLS.get(a["currency"], a["currency"])
        b.button(
            text=f"{a['name']} ({float(a['amount']):,.2f} {sym})",
            callback_data=f"edit_asset_{a['id']}"
        )
    for c in crypto_assets:
        b.button(
            text=f"₿ {c['coin_name']} ({float(c['amount']):,.6f} {c['coin_symbol']})",
            callback_data=f"edit_crypto_{c['id']}"
        )
    b.button(text="◀️ Назад", callback_data="section_capital")
    b.adjust(1)
    await state.set_state(EditAsset.choosing_asset)
    await callback.message.edit_text("✏️ Выбери актив для обновления:", reply_markup=b.as_markup())


@dp.callback_query(F.data.startswith("edit_asset_"), EditAsset.choosing_asset)
async def cap_edit_choose(callback: types.CallbackQuery, state: FSMContext):
    asset_id = int(callback.data.replace("edit_asset_", ""))
    await state.update_data(asset_id=asset_id, is_crypto=False)
    await state.set_state(EditAsset.entering_amount)
    await callback.message.edit_text(
        "💵 Введи новую сумму:\n<i>Можно с десятичными: 1500.50</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb("section_capital")
    )


@dp.callback_query(F.data.startswith("edit_crypto_"), EditAsset.choosing_asset)
async def cap_edit_crypto_choose(callback: types.CallbackQuery, state: FSMContext):
    crypto_id = int(callback.data.replace("edit_crypto_", ""))
    await state.update_data(asset_id=crypto_id, is_crypto=True)
    await state.set_state(EditAsset.entering_amount)
    await callback.message.edit_text(
        "🪙 Введи новое количество монет:\n<i>Можно до 8 знаков: 1.672 или 0.00035</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb("section_capital")
    )


@dp.message(EditAsset.entering_amount)
async def cap_edit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи корректное число:")
        return

    data = await state.get_data()
    await state.clear()

    if data.get("is_crypto"):
        updated = await db.update_crypto_asset(data["asset_id"], amount)
        formatted = f"{amount:.8f}".rstrip('0').rstrip('.')
        await message.answer(
            f"✅ Обновлено!\n"
            f"🪙 {updated['coin_name']} ({updated['coin_symbol']}): <b>{formatted}</b>",
            parse_mode="HTML",
            reply_markup=capital_kb()
        )
    else:
        updated = await db.update_asset(data["asset_id"], amount)
        sym = CURRENCY_SYMBOLS.get(updated["currency"], updated["currency"])
        await message.answer(
            f"✅ Обновлено!\n📌 {updated['name']}: <b>{amount:,.2f} {sym}</b>",
            parse_mode="HTML",
            reply_markup=capital_kb()
        )


# ── DELETE ASSET ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "cap_delete")
async def cap_delete_start(callback: types.CallbackQuery):
    assets = await db.get_assets(callback.from_user.id)
    crypto_assets = await db.get_crypto_assets(callback.from_user.id)

    if not assets and not crypto_assets:
        await callback.answer("Нет активов для удаления!", show_alert=True)
        return

    b = InlineKeyboardBuilder()
    for a in assets:
        sym = CURRENCY_SYMBOLS.get(a["currency"], a["currency"])
        label = get_asset_label(a["asset_type"])
        b.button(
            text=f"🗑 {a['name']} ({float(a['amount']):,.0f} {sym})",
            callback_data=f"del_asset_{a['id']}"
        )
    for c in crypto_assets:
        b.button(
            text=f"🗑 {c['coin_name']} ({float(c['amount']):,.4f} {c['coin_symbol']})",
            callback_data=f"del_crypto_{c['id']}"
        )
    b.button(text="◀️ Назад", callback_data="section_capital")
    b.adjust(1)

    await callback.message.edit_text(
        "🗑 <b>Удалить актив</b>\n\nВыбери что удалить:",
        parse_mode="HTML",
        reply_markup=b.as_markup()
    )


@dp.callback_query(F.data.startswith("del_asset_"))
async def cap_delete_asset(callback: types.CallbackQuery):
    asset_id = int(callback.data.replace("del_asset_", ""))
    await db.delete_asset(asset_id)
    await callback.answer("✅ Актив удалён!", show_alert=False)

    # Refresh delete list
    assets = await db.get_assets(callback.from_user.id)
    crypto_assets = await db.get_crypto_assets(callback.from_user.id)

    if not assets and not crypto_assets:
        await callback.message.edit_text("✅ Все активы удалены.", reply_markup=capital_kb())
        return

    b = InlineKeyboardBuilder()
    for a in assets:
        sym = CURRENCY_SYMBOLS.get(a["currency"], a["currency"])
        b.button(
            text=f"🗑 {a['name']} ({float(a['amount']):,.0f} {sym})",
            callback_data=f"del_asset_{a['id']}"
        )
    for c in crypto_assets:
        b.button(
            text=f"🗑 {c['coin_name']} ({float(c['amount']):,.4f} {c['coin_symbol']})",
            callback_data=f"del_crypto_{c['id']}"
        )
    b.button(text="◀️ Назад", callback_data="section_capital")
    b.adjust(1)
    await callback.message.edit_text(
        "🗑 <b>Удалить актив</b>\n\nВыбери что удалить:",
        parse_mode="HTML",
        reply_markup=b.as_markup()
    )


@dp.callback_query(F.data.startswith("del_crypto_"))
async def cap_delete_crypto(callback: types.CallbackQuery):
    crypto_id = int(callback.data.replace("del_crypto_", ""))
    await db.delete_crypto_asset(crypto_id, callback.from_user.id)
    await callback.answer("✅ Монета удалена!", show_alert=False)

    # Refresh delete list
    assets = await db.get_assets(callback.from_user.id)
    crypto_assets = await db.get_crypto_assets(callback.from_user.id)

    if not assets and not crypto_assets:
        await callback.message.edit_text("✅ Все активы удалены.", reply_markup=capital_kb())
        return

    b = InlineKeyboardBuilder()
    for a in assets:
        sym = CURRENCY_SYMBOLS.get(a["currency"], a["currency"])
        b.button(
            text=f"🗑 {a['name']} ({float(a['amount']):,.0f} {sym})",
            callback_data=f"del_asset_{a['id']}"
        )
    for c in crypto_assets:
        b.button(
            text=f"🗑 {c['coin_name']} ({float(c['amount']):,.4f} {c['coin_symbol']})",
            callback_data=f"del_crypto_{c['id']}"
        )
    b.button(text="◀️ Назад", callback_data="section_capital")
    b.adjust(1)
    await callback.message.edit_text(
        "🗑 <b>Удалить актив</b>\n\nВыбери что удалить:",
        parse_mode="HTML",
        reply_markup=b.as_markup()
    )



@dp.message(Command("анализ", "analysis"))
async def cmd_analysis(message: types.Message):
    await message.answer("⏳ Анализирую финансы...")
    stats = await db.get_last_30_days_stats(message.from_user.id)
    if stats["income"] == 0 and stats["expense"] == 0:
        await message.answer("📭 За последние 30 дней нет записей.")
        return
    try:
        analysis = await get_full_analysis(stats)
        await message.answer(f"📊 <b>Анализ за 30 дней</b>\n\n{analysis}", parse_mode="HTML")
    except Exception:
        await message.answer("⚠️ AI-анализ недоступен — пополни баланс на console.anthropic.com")

@dp.message(Command("крипто", "crypto"))
async def cmd_crypto_detail(message: types.Message):
    crypto_assets = await db.get_crypto_assets(message.from_user.id)
    if not crypto_assets:
        await message.answer(
            "₿ У тебя пока нет монет.\n\nДобавь через: 🏦 Мой капитал → ➕ Добавить актив → ₿ Крипто"
        )
        return

    await message.answer("⏳ Загружаю курсы...")
    import aiohttp
    coin_ids = list({c["coin_id"] for c in crypto_assets})
    prices = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coin_ids)}&vs_currencies=rub,usd",
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status == 200:
                    prices = await r.json()
    except Exception:
        pass

    rates = await get_exchange_rates()
    usdt_rate = rates.get("USDT", 72.5)

    total_rub = 0.0
    text = "₿ <b>Крипто-портфель</b>\n\n"
    for c in crypto_assets:
        price_rub = prices.get(c["coin_id"], {}).get("rub", 0)
        price_usd = prices.get(c["coin_id"], {}).get("usd", 0)
        val_rub = float(c["amount"]) * price_rub
        val_usdt = val_rub / usdt_rate if usdt_rate else 0
        total_rub += val_rub
        text += (
            f"🪙 <b>{c['coin_name']}</b> ({c['coin_symbol']})\n"
            f"  Кол-во: <b>{float(c['amount']):,.6f}</b>\n"
            f"  Курс: <b>${price_usd:,.4f}</b> / {price_rub:,.2f} ₽\n"
            f"  Стоимость: <b>{val_rub:,.0f} ₽</b> / <b>{val_usdt:,.0f} ₮</b>\n\n"
        )

    total_usdt = total_rub / usdt_rate if usdt_rate else 0
    text += f"━━━━━━━━━━━━━━━\n"
    text += f"💼 Итого: <b>{total_rub:,.0f} ₽</b> / <b>{total_usdt:,.0f} ₮</b>"
    now = datetime.now().strftime("%H:%M")
    text += f"\n<i>🕐 {now} | 1 ₮ = {usdt_rate:,.1f} ₽</i>"

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("история", "history"))
async def cmd_history(message: types.Message):
    txs = await db.get_recent_transactions(message.from_user.id, 10)
    if not txs:
        await message.answer("📭 Нет записей.")
        return
    text = "📋 <b>Последние записи</b>\n\n"
    for t in txs:
        emoji = "💰" if t["type"] == "income" else "💸"
        sign = "+" if t["type"] == "income" else "-"
        date = t["created_at"].strftime("%d.%m")
        text += f"{emoji} {date} | <b>{sign}{t['amount']:,.0f} ₽</b> | {t['category']}\n"
        if t["description"]:
            text += f"   └ {t['description']}\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("новаяцель"))
async def cmd_new_goal(message: types.Message):
    parts = message.text.replace("/новаяцель", "").strip().split()
    if len(parts) < 2:
        await message.answer("Напиши так: <b>/новаяцель Название 100000</b>", parse_mode="HTML")
        return
    try:
        amount = float(parts[-1].replace(",", ""))
        name = " ".join(parts[:-1])
    except ValueError:
        await message.answer("Пример: <b>/новаяцель Отпуск 150000</b>", parse_mode="HTML")
        return
    await db.add_goal(message.from_user.id, name, amount)
    await message.answer(f"✅ Цель <b>{name}</b> создана!\n💵 Накопить: {amount:,.0f} ₽", parse_mode="HTML")

@dp.message(Command("помощь", "help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📋 <b>Как пользоваться</b>\n\n"
        "<b>Записать трату/доход — просто напиши:</b>\n"
        "• Потратил 3500 на бетон\n"
        "• Получил зарплату 80000\n\n"
        "<b>Спросить статистику:</b>\n"
        "• Сколько потратил на стройку\n"
        "• Расходы за июнь\n"
        "• Мой баланс\n\n"
        "<b>Команды:</b>\n"
        "/анализ — AI-отчёт за 30 дней\n"
        "/история — последние записи\n"
        "/новаяцель Название 100000",
        parse_mode="HTML", reply_markup=main_kb()
    )

# ── MAIN TEXT ─────────────────────────────────────────────────────────────────

@dp.message(F.text)
async def handle_text(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        return
    text = message.text.strip()
    try:
        query = parse_query(text)
        if query and query.get("is_query"):
            await handle_data_query(message, query)
            return
    except Exception:
        pass
    try:
        transaction = parse_transaction(text)
        if transaction:
            await handle_new_transaction(message, transaction)
            return
    except Exception:
        pass
    await message.answer(
        "🤔 Не понял...\n\n"
        "Попробуй:\n"
        "• <i>Потратил 3500 на бетон</i>\n"
        "• <i>Получил зарплату 80000</i>\n"
        "• <i>Сколько потратил на стройку</i>",
        parse_mode="HTML", reply_markup=main_kb()
    )

async def handle_new_transaction(message: types.Message, t: dict):
    await db.create_user(message.from_user.id, message.from_user.full_name)
    await db.add_transaction(
        user_id=message.from_user.id,
        t_type=t["type"], category=t["category"],
        amount=t["amount"], description=t.get("description")
    )
    emoji = "💰" if t["type"] == "income" else "💸"
    sign = "+" if t["type"] == "income" else "-"
    action = "Доход записан" if t["type"] == "income" else "Расход записан"
    await message.answer(
        f"{emoji} <b>{action}!</b>\n\n📂 {t['category']}\n💵 <b>{sign}{t['amount']:,.0f} ₽</b>\n📝 {t.get('description', '')}",
        parse_mode="HTML", reply_markup=main_kb()
    )

async def handle_data_query(message: types.Message, query: dict):
    user_id = message.from_user.id
    q_type = query.get("query_type")
    category = query.get("category")
    period = query.get("period", "month")
    period_ru = PERIOD_RU.get(period, period)
    if q_type == "balance":
        stats = await db.get_monthly_stats(user_id)
        total = await db.get_total_balance(user_id)
        income = stats.get("income", 0)
        expense = stats.get("expense", 0)
        net = income - expense
        await message.answer(
            f"💼 <b>Обзор</b>\n\n💰 Доходы: <b>+{income:,.0f} ₽</b>\n💸 Расходы: <b>-{expense:,.0f} ₽</b>\n"
            f"{'📈' if net >= 0 else '📉'} Баланс: <b>{'+' if net >= 0 else ''}{net:,.0f} ₽</b>\n🏦 Всего: <b>{total:,.0f} ₽</b>",
            parse_mode="HTML", reply_markup=main_kb()
        )
    elif q_type == "category_total" and category:
        total = await db.get_category_total(user_id, category, period)
        if total == 0:
            await message.answer(f"📭 Нет записей по «{category}» за {period_ru}.")
        else:
            await message.answer(f"📂 <b>{category.capitalize()}</b> за {period_ru}:\n\n💸 <b>{total:,.0f} ₽</b>", parse_mode="HTML", reply_markup=main_kb())
    elif q_type in ("expenses_by_period", "income_by_period"):
        is_expense = q_type == "expenses_by_period"
        rows = await db.get_expenses_by_period(user_id, period) if is_expense else await db.get_income_by_period(user_id, period)
        if not rows:
            await message.answer(f"📭 Нет {'расходов' if is_expense else 'доходов'} за {period_ru}.")
            return
        total = sum(r["total"] for r in rows)
        emoji = "💸" if is_expense else "💰"
        label = "Расходы" if is_expense else "Доходы"
        text = f"{emoji} <b>{label} за {period_ru}</b>\n\n"
        for r in rows:
            text += f"• {r['category']}: <b>{r['total']:,.0f} ₽</b> ({r['total']/total*100:.0f}%)\n"
        text += f"\n<b>Итого: {total:,.0f} ₽</b>"
        await message.answer(text, parse_mode="HTML", reply_markup=main_kb())
    elif q_type == "top_categories":
        rows = await db.get_expenses_by_period(user_id, period)
        if not rows:
            await message.answer(f"📭 Нет расходов за {period_ru}.")
            return
        total = sum(r["total"] for r in rows)
        medals = ["🥇", "🥈", "🥉"]
        text = f"🏆 <b>Топ расходов за {period_ru}</b>\n\n"
        for i, r in enumerate(rows[:5]):
            text += f"{medals[i] if i < 3 else '▪️'} {r['category']}: <b>{r['total']:,.0f} ₽</b> ({r['total']/total*100:.0f}%)\n"
        text += f"\n💸 Всего: <b>{total:,.0f} ₽</b>"
        await message.answer(text, parse_mode="HTML", reply_markup=main_kb())

# ── MORNING PULSE ─────────────────────────────────────────────────────────────

async def send_morning_pulse():
    while True:
        now = datetime.now()
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            from datetime import timedelta
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        users = await db.get_all_users()
        for user in users:
            try:
                stats = await db.get_last_30_days_stats(user["id"])
                if stats["income"] == 0 and stats["expense"] == 0:
                    continue
                income = stats.get("income", 0)
                expense = stats.get("expense", 0)
                avg_day = expense / 30
                savings = income - expense
                categories = stats.get("categories", {})
                top_cat = ""
                if categories and expense > 0:
                    top = max(categories, key=categories.get)
                    top_pct = round(categories[top] / expense * 100)
                    top_cat = f"\n🔥 Главная трата: <b>{top}</b> ({top_pct}% бюджета)"
                trend = "📈 превышают доходы" if expense > income else "✅ в норме"
                pulse = (
                    f"☀️ <b>Доброе утро!</b>\n\n"
                    f"📊 <b>Финансовый пульс (30 дней)</b>\n\n"
                    f"💰 Доходы: <b>{income:,.0f} ₽</b>\n"
                    f"💸 Расходы: <b>{expense:,.0f} ₽</b>\n"
                    f"📅 В среднем/день: <b>{avg_day:,.0f} ₽</b>\n"
                    f"💎 Накопления: <b>{savings:,.0f} ₽</b>"
                    f"{top_cat}\n\n"
                    f"Расходы {trend}"
                )
                await bot.send_message(user["id"], pulse, parse_mode="HTML", reply_markup=main_kb())
            except Exception as e:
                logger.error(f"Pulse error for {user['id']}: {e}")

async def main():
    await db.init()
    logger.info("Bot started!")
    asyncio.create_task(send_morning_pulse())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
