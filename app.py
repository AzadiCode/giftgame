# -*- coding: utf-8 -*-
"""XZ GIFT — Telegram Mini App starter. Virtual credits only; no real-money deposits/withdrawals."""
import os, hmac, hashlib, json, time, secrets, logging, re
import requests
from datetime import datetime, timezone, date
from urllib.parse import parse_qsl
from flask import Flask, request, jsonify, send_from_directory
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("xzgift")
app = Flask(__name__, static_folder="static", static_url_path="/static")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:10000").rstrip("/")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
STARTING_BALANCE = int(os.getenv("STARTING_BALANCE", "1000"))
DAILY_SPIN_REWARD_MIN = int(os.getenv("DAILY_SPIN_REWARD_MIN", "10"))
DAILY_SPIN_REWARD_MAX = int(os.getenv("DAILY_SPIN_REWARD_MAX", "150"))
INIT_DATA_MAX_AGE = int(os.getenv("INIT_DATA_MAX_AGE", "86400"))
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
if BOT_TOKEN and not TELEGRAM_WEBHOOK_SECRET:
    TELEGRAM_WEBHOOK_SECRET = hashlib.sha256(("xzgift-webhook:" + BOT_TOKEN).encode()).hexdigest()[:40]

mongo = None
if MONGO_URI:
    mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    db = mongo.get_database(os.getenv("MONGO_DB", "xzgift"))
    db.users.create_index("telegram_id", unique=True)
    db.transactions.create_index([("telegram_id", 1), ("created_at", -1)])
    db.game_rounds.create_index([("telegram_id", 1), ("created_at", -1)])
    db.daily_actions.create_index([("telegram_id", 1), ("day", 1), ("action", 1)], unique=True)
else:
    # Explicit development mode; data is in-memory and is lost on restart.
    from mongomock import MongoClient as MockMongoClient
    mongo = MockMongoClient()
    db = mongo.get_database("xzgift")
    log.warning("MONGO_URI unset: temporary in-memory storage enabled; data will reset on restart.")

def utcnow():
    return datetime.now(timezone.utc)

def verify_init_data(init_data):
    """Validate Telegram WebApp initData using Telegram's HMAC algorithm."""
    if not BOT_TOKEN or not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            return None
        auth_date = int(pairs.get("auth_date", "0"))
        if auth_date <= 0 or time.time() - auth_date > INIT_DATA_MAX_AGE or auth_date - time.time() > 60:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        user = json.loads(pairs["user"])
        if not isinstance(user, dict) or not user.get("id"):
            return None
        return user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

def dev_user():
    # Only available when BOT_TOKEN is unset. Never enable this in production.
    if BOT_TOKEN:
        return None
    return {"id": 100000001, "first_name": "Tester", "username": "tester"}

def current_user():
    raw = request.headers.get("X-Telegram-Init-Data", "")
    user = verify_init_data(raw) if BOT_TOKEN else dev_user()
    return user

def require_user():
    user = current_user()
    if not user:
        return None, (jsonify(error="احراز هویت تلگرام نامعتبر است. مینی‌اپ را از داخل تلگرام باز کنید."), 401)
    return user, None

def ensure_user(tg_user):
    tid = int(tg_user["id"])
    update = {
        "$set": {"first_name": str(tg_user.get("first_name", "کاربر"))[:80],
                 "username": str(tg_user.get("username", ""))[:64],
                 "last_seen": utcnow()},
        "$setOnInsert": {"telegram_id": tid, "balance": STARTING_BALANCE,
                         "created_at": utcnow(), "level": 1, "xp": 0}
    }
    return db.users.find_one_and_update({"telegram_id": tid}, update, upsert=True, return_document=ReturnDocument.AFTER)

def tx(tid, amount, kind, note, balance_after=None):
    db.transactions.insert_one({"telegram_id": tid, "amount": int(amount), "kind": kind,
                                "note": note[:200], "balance_after": balance_after,
                                "created_at": utcnow()})

def safe_user(u):
    return {"id": int(u["telegram_id"]), "first_name": u.get("first_name", "کاربر"),
            "username": u.get("username", ""), "balance": int(u.get("balance", 0)),
            "level": int(u.get("level", 1)), "xp": int(u.get("xp", 0))}

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

@app.get("/health")
def health():
    return jsonify(status="ok", storage="mongodb" if MONGO_URI else "temporary-memory")

@app.post("/telegram/webhook")
def telegram_webhook():
    """Respond to /start and open the Mini App. Telegram calls this endpoint via webhook."""
    if not BOT_TOKEN:
        return "bot token not configured", 503
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(supplied, TELEGRAM_WEBHOOK_SECRET):
        return "forbidden", 403
    update = request.get_json(silent=True) or {}
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    text = (msg.get("text") or "").strip()
    if chat.get("type") == "private" and text.split("@", 1)[0].split(" ", 1)[0] == "/start":
        if not BASE_URL.startswith("https://"):
            log.error("BASE_URL must be the public HTTPS Render URL for Telegram Mini App")
            return "ok"
        payload = {
            "chat_id": chat.get("id"),
            "text": "🎁 سلام! به XZ GIFT خوش اومدی. برای ورود به مینی‌اپ روی دکمه زیر بزن.",
            "reply_markup": {"inline_keyboard": [[{"text": "🚀 باز کردن XZ GIFT", "web_app": {"url": BASE_URL}}]]}
        }
        try:
            response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=12)
            if response.status_code >= 400 or not response.json().get("ok"):
                log.error("Telegram sendMessage failed: %s", response.text[:300])
        except Exception:
            log.exception("Telegram sendMessage request failed")
    return "ok"

def setup_telegram_webhook():
    """Register webhook on deployment startup; Telegram bot /start won't work without this."""
    if not BOT_TOKEN:
        log.warning("BOT_TOKEN is empty: Telegram /start webhook is disabled")
        return
    if not BASE_URL.startswith("https://"):
        log.warning("BASE_URL must be the public HTTPS URL; skipping webhook setup")
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={"url": f"{BASE_URL}/telegram/webhook",
                  "secret_token": TELEGRAM_WEBHOOK_SECRET,
                  "allowed_updates": ["message"]}, timeout=15)
        data = response.json()
        if not data.get("ok"):
            log.error("Telegram setWebhook failed: %s", data)
        else:
            log.info("Telegram webhook configured: %s/telegram/webhook", BASE_URL)
        # Also expose the Mini App from the bot's menu button.
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMenuButton",
            json={"menu_button": {"type": "web_app", "text": "باز کردن مینی‌اپ",
                                   "web_app": {"url": BASE_URL}}}, timeout=12)
    except Exception:
        log.exception("Could not configure Telegram webhook")

@app.get("/api/me")
def api_me():
    tg_user, err = require_user()
    if err: return err
    u = ensure_user(tg_user)
    tid = int(tg_user["id"])
    history = list(db.transactions.find({"telegram_id": tid}, {"_id": 0}).sort("created_at", -1).limit(8))
    for h in history:
        h["created_at"] = h["created_at"].isoformat()
    return jsonify(user=safe_user(u), transactions=history, daily_spin_ready=not bool(db.daily_actions.find_one({"telegram_id": tid, "day": date.today().isoformat(), "action": "spin"})))

@app.get("/api/leaderboard")
def leaderboard():
    # Ensure a user session exists even in development mode.
    tg_user, err = require_user()
    if err: return err
    ensure_user(tg_user)
    rows = list(db.users.find({}, {"telegram_id": 1, "first_name": 1, "username": 1, "balance": 1, "level": 1}).sort("balance", -1).limit(20))
    return jsonify(items=[{"id": int(x["telegram_id"]), "name": x.get("first_name", "کاربر"), "balance": int(x.get("balance", 0)), "level": int(x.get("level", 1))} for x in rows])

@app.post("/api/spin")
def spin():
    tg_user, err = require_user()
    if err: return err
    u = ensure_user(tg_user); tid = int(tg_user["id"]); today = date.today().isoformat()
    reward = secrets.randbelow(DAILY_SPIN_REWARD_MAX - DAILY_SPIN_REWARD_MIN + 1) + DAILY_SPIN_REWARD_MIN
    try:
        db.daily_actions.insert_one({"telegram_id": tid, "day": today, "action": "spin", "created_at": utcnow()})
    except Exception:
        return jsonify(error="امروز گردونه رو چرخوندی؛ فردا دوباره امتحان کن."), 409
    updated = db.users.find_one_and_update({"telegram_id": tid}, {"$inc": {"balance": reward, "xp": 5}}, return_document=ReturnDocument.AFTER)
    tx(tid, reward, "daily_spin", "جایزه گردونه روزانه", updated["balance"])
    return jsonify(reward=reward, user=safe_user(updated), message=f"{reward} سکه به موجودی مجازی اضافه شد.")

@app.post("/api/game/crash")
def crash_game():
    tg_user, err = require_user()
    if err: return err
    body = request.get_json(silent=True) or {}
    try: bet = int(body.get("bet", 10))
    except (TypeError, ValueError): return jsonify(error="مقدار شرط معتبر نیست."), 400
    if bet < 1 or bet > 10000: return jsonify(error="مبلغ باید بین ۱ تا ۱۰٬۰۰۰ سکه باشد."), 400
    tid = int(tg_user["id"]); u = ensure_user(tg_user)
    if int(u["balance"]) < bet: return jsonify(error="موجودی مجازی کافی نیست."), 400
    # Demo-only round: server determines outcome. No real-money wagering.
    bust = round(1.0 + (secrets.randbelow(500) / 100), 2)
    cashout = float(body.get("cashout", 1.5))
    cashout = min(max(cashout, 1.01), 10.0)
    won = cashout <= bust
    payout = int(bet * cashout) if won else 0
    delta = payout - bet
    updated = db.users.find_one_and_update({"telegram_id": tid, "balance": {"$gte": bet}},
        {"$inc": {"balance": delta, "xp": 2}}, return_document=ReturnDocument.AFTER)
    if not updated: return jsonify(error="موجودی تغییر کرده؛ دوباره تلاش کن."), 409
    tx(tid, delta, "crash_win" if won else "crash_loss", f"Crash دمو؛ ضریب هدف {cashout:.2f}x، ضریب سقوط {bust:.2f}x", updated["balance"])
    db.game_rounds.insert_one({"telegram_id": tid, "game": "crash", "bet": bet, "cashout": cashout, "bust": bust, "won": won, "delta": delta, "created_at": utcnow()})
    return jsonify(won=won, bust=bust, cashout=cashout, delta=delta, user=safe_user(updated), message=(f"بردی! +{delta} سکه مجازی" if won else f"این دور باختی؛ {bet} سکه مجازی کم شد."))

@app.post("/api/game/mines")
def mines_game():
    tg_user, err = require_user()
    if err: return err
    body = request.get_json(silent=True) or {}
    try:
        bet = int(body.get("bet", 10)); picks = int(body.get("picks", 1))
    except (TypeError, ValueError): return jsonify(error="ورودی نامعتبر است."), 400
    if bet < 1 or bet > 10000 or picks < 1 or picks > 5: return jsonify(error="مبلغ یا تعداد انتخاب معتبر نیست."), 400
    tid = int(tg_user["id"]); u = ensure_user(tg_user)
    if int(u["balance"]) < bet: return jsonify(error="موجودی مجازی کافی نیست."), 400
    # Demo outcome resolved server-side; simplified one-shot mini game.
    mines = secrets.randbelow(5) + 1
    safe = secrets.randbelow(6) + 1
    won = picks <= safe
    payout = int(bet * (1 + picks * 0.25)) if won else 0
    delta = payout - bet
    updated = db.users.find_one_and_update({"telegram_id": tid, "balance": {"$gte": bet}}, {"$inc": {"balance": delta, "xp": 2}}, return_document=ReturnDocument.AFTER)
    if not updated: return jsonify(error="موجودی تغییر کرده؛ دوباره تلاش کن."), 409
    tx(tid, delta, "mines_win" if won else "mines_loss", f"Mines دمو؛ {picks} انتخاب", updated["balance"])
    db.game_rounds.insert_one({"telegram_id": tid, "game": "mines", "bet": bet, "picks": picks, "won": won, "delta": delta, "created_at": utcnow()})
    return jsonify(won=won, delta=delta, picks=picks, user=safe_user(updated), message=(f"خانه‌های امن! +{delta} سکه مجازی" if won else f"مین فعال شد؛ {bet} سکه مجازی از دست رفت."))

@app.post("/api/admin/credit")
def admin_credit():
    tg_user, err = require_user()
    if err: return err
    if int(tg_user["id"]) not in ADMIN_IDS: return jsonify(error="دسترسی غیرمجاز"), 403
    body = request.get_json(silent=True) or {}
    try: target, amount = int(body["telegram_id"]), int(body["amount"])
    except (KeyError, TypeError, ValueError): return jsonify(error="ورودی نامعتبر است."), 400
    if amount == 0 or abs(amount) > 1000000: return jsonify(error="مقدار نامعتبر است."), 400
    updated = db.users.find_one_and_update({"telegram_id": target, **({"balance": {"$gte": -amount}} if amount < 0 else {})},
        {"$inc": {"balance": amount}}, return_document=ReturnDocument.AFTER)
    if not updated: return jsonify(error="کاربر پیدا نشد یا موجودی کافی نیست."), 404
    tx(target, amount, "admin_adjustment", "تغییر موجودی توسط مدیر", updated["balance"])
    return jsonify(ok=True, balance=updated["balance"])

@app.errorhandler(500)
def internal_error(e):
    log.exception("Internal server error: %s", e)
    return jsonify(error="خطای داخلی سرور؛ گزارش سرور را بررسی کنید."), 500

if __name__ == "__main__":
    setup_telegram_webhook()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")), debug=False)
else:
    # Gunicorn imports app:app; configure the webhook during service startup.
    setup_telegram_webhook()
