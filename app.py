import os
import random
import sqlite3
import threading
from pathlib import Path
from time import time

from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    import telebot  # pyTelegramBotAPI
except ImportError:  # pragma: no cover
    telebot = None


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

app = Flask(__name__)
CORS(app)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_for_webapp() -> None:
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
    cur.execute("CREATE TABLE IF NOT EXISTS user_pools (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, active INTEGER DEFAULT 1)")
    cur.execute("CREATE TABLE IF NOT EXISTS boosts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, pool_id INTEGER, bonus_rate REAL, started_at INTEGER, expires_at INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS roulette_settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("INSERT OR IGNORE INTO roulette_settings(key, value) VALUES ('win_chance', ?)", (str(ROULETTE_DEFAULT_WIN_CHANCE),))
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


def ensure_user(user_id: int) -> None:
    conn = db()
    exists = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not exists:
        conn.execute("INSERT INTO users(user_id, balance, created_at) VALUES (?, 5.0, ?)", (user_id, int(time())))
        conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def get_win_chance() -> int:
    conn = db()
    row = conn.execute("SELECT value FROM roulette_settings WHERE key='win_chance'").fetchone()
    conn.close()
    try:
        return max(0, min(100, int(float(row[0])))) if row else ROULETTE_DEFAULT_WIN_CHANCE
    except (TypeError, ValueError):
        return ROULETTE_DEFAULT_WIN_CHANCE


def list_wins(user_id: int, limit: int = 50):
    conn = db()
    rows = conn.execute("SELECT * FROM roulette_wins WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_win(user_id: int, prize: dict, status: str) -> int:
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO roulette_wins(user_id, prize_type, prize_label, amount_usdt, token_amount, boost_hours, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            prize.get("type", "nothing"),
            prize.get("label", "Nothing"),
            float(prize.get("amount", 0.0) or 0.0),
            int(prize.get("tokens", 0) or 0),
            int(prize.get("hours", 0) or 0),
            status,
            int(time()),
        ),
    )
    win_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return win_id


def apply_boost(user_id: int, hours: int) -> bool:
    conn = db()
    pool = conn.execute("SELECT id FROM user_pools WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if not pool:
        conn.close()
        return False
    pool_id = int(pool[0])
    already = conn.execute("SELECT id FROM boosts WHERE user_id=? AND pool_id=? LIMIT 1", (user_id, pool_id)).fetchone()
    if already:
        conn.close()
        return False
    now = int(time())
    conn.execute("INSERT INTO boosts(user_id, pool_id, bonus_rate, started_at, expires_at) VALUES (?, ?, 0.03, ?, ?)", (user_id, pool_id, now, now + hours * 3600))
    conn.commit()
    conn.close()
    return True


def activate_boost_prize(user_id: int, win_id: int) -> dict:
    conn = db()
    row = conn.execute("SELECT * FROM roulette_wins WHERE id=? AND user_id=? AND prize_type='boost'", (win_id, user_id)).fetchone()
    conn.close()
    if not row:
        return {"status": "not_found"}
    if row["status"] == "activated":
        return {"status": "already"}
    hours = int(row["boost_hours"] or 24)
    if not apply_boost(user_id, hours):
        return {"status": "no_pool"}
    conn = db()
    conn.execute("UPDATE roulette_wins SET status='activated' WHERE id=?", (win_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "hours": hours}


def spin(user_id: int) -> dict:
    user = get_user(user_id)
    if not user or float(user["balance"]) < ROULETTE_SPIN_COST:
        return {"status": "insufficient"}

    conn = db()
    conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (ROULETTE_SPIN_COST, user_id))
    conn.commit()
    conn.close()

    chance = get_win_chance()
    if chance <= 0:
        prize = random.choice(ROULETTE_ZERO_CHANCE_POOL)
    elif random.random() >= chance / 100.0:
        prize = {"type": "nothing", "label": "Ничего не выйграно"}
    else:
        prize = random.choices(ROULETTE_PRIZES, weights=[p["weight"] for p in ROULETTE_PRIZES], k=1)[0]

    ptype = prize["type"]
    if ptype == "nothing":
        win_id = add_win(user_id, prize, "awarded")
        return {"status": "ok", "reward": "nothing", "prize_label": prize["label"], "win_id": win_id}
    if ptype == "usdt":
        amount = float(prize.get("amount", 0.0))
        conn = db()
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
        conn.commit()
        conn.close()
        win_id = add_win(user_id, prize, "credited")
        return {"status": "ok", "reward": "usdt", "amount": amount, "prize_label": prize["label"], "win_id": win_id}
    if ptype == "token":
        win_id = add_win(user_id, prize, "awarded")
        return {"status": "ok", "reward": "token", "tokens": int(prize["tokens"]), "prize_label": prize["label"], "win_id": win_id}

    win_id = add_win(user_id, prize, "pending_activation")
    return {"status": "ok", "reward": "boost", "hours": int(prize.get("hours", 24)), "prize_label": prize["label"], "win_id": win_id}


def start_telegram_polling_thread() -> None:
    if not telebot or not BOT_TOKEN:
        return

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

    @bot.message_handler(commands=["start"])
    def _start(message):
        bot.reply_to(message, "🤖 API server online. Bot polling in separate thread.")

    def _run():
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)

    threading.Thread(target=_run, daemon=True).start()


@app.get("/api/profile")
def api_profile():
    user_id = int(request.args.get("user_id", 0) or 0)
    if user_id <= 0:
        return jsonify({"ok": False, "error": "bad_user"}), 400
    ensure_user(user_id)
    user = get_user(user_id)
    return jsonify({
        "ok": True,
        "user_id": user_id,
        "balance": float(user["balance"] if user else 0.0),
        "wins": list_wins(user_id),
        "win_chance": get_win_chance(),
        "won_total_label": "Более 5000USDT",
    })


@app.post("/api/spin")
def api_spin():
    payload = request.get_json(silent=True) or {}
    user_id = int(payload.get("user_id", 0) or 0)
    if user_id <= 0:
        return jsonify({"ok": False, "error": "bad_user"}), 400
    ensure_user(user_id)
    res = spin(user_id)
    if res.get("status") == "insufficient":
        return jsonify({"ok": False, "error": "insufficient"}), 400
    user = get_user(user_id)
    return jsonify({"ok": True, **res, "balance": float(user["balance"] if user else 0.0), "wins": list_wins(user_id)})


@app.post("/api/activate_boost")
def api_activate_boost():
    payload = request.get_json(silent=True) or {}
    user_id = int(payload.get("user_id", 0) or 0)
    win_id = int(payload.get("win_id", 0) or 0)
    if user_id <= 0 or win_id <= 0:
        return jsonify({"ok": False, "error": "bad_request"}), 400
    res = activate_boost_prize(user_id, win_id)
    return jsonify({"ok": res.get("status") == "ok", **res, "wins": list_wins(user_id)})


if __name__ == "__main__":
    init_db_for_webapp()
    start_telegram_polling_thread()
    port = int(os.environ.get("PORT", "4173"))
    app.run(host="0.0.0.0", port=port)


