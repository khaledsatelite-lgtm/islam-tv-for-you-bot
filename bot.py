
import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ==============================
# CONFIGURATION
# ==============================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID", "")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ==============================
# TELEGRAM FUNCTIONS
# ==============================

def send_message(chat_id, text):
    if not BOT_TOKEN:
        return

    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=20
        )
    except requests.RequestException:
        pass


# ==============================
# SUPABASE CONNECTION
# ==============================

def check_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False

    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=*&limit=1",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            },
            timeout=15
        )

        return response.status_code == 200

    except requests.RequestException:
        return False


# ==============================
# HOME PAGE
# ==============================

@app.route("/")
def home():
    return "Islam TV For You Bot is running!"


# ==============================
# TELEGRAM WEBHOOK
# ==============================

@app.route("/telegram-webhook", methods=["POST"])
def webhook():

    data = request.get_json(silent=True) or {}
    message = data.get("message", {})

    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_id = chat.get("id")
    user_id = str(user.get("id", ""))
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return "OK"

    # Owner protection
    if not OWNER_ID or user_id != OWNER_ID:
        send_message(
            chat_id,
            "⛔ هذا البوت خاص بصاحبه فقط."
        )
        return "OK"

    # ==========================
    # START
    # ==========================

    if text == "/start":

        send_message(
            chat_id,
            "📺 مرحباً بك في نظام Islam TV For You\n\n"
            "👤 حساب المالك: مفعل\n"
            "🔐 حماية البوت: مفعلة\n\n"
            "📊 نظام إدارة المبيعات والمشتريات\n"
            "💰 متابعة الأرباح والمصاريف\n"
            "🎟️ إدارة Credits\n\n"
            "اختر أحد الأوامر:\n"
            "/status - حالة النظام\n"
            "/dbtest - اختبار قاعدة البيانات\n"
            "/help - المساعدة"
        )

    # ==========================
    # HELP
    # ==========================

    elif text == "/help":

        send_message(
            chat_id,
            "📋 أوامر بوت Islam TV For You\n\n"
            "/start - البداية\n"
            "/help - المساعدة\n"
            "/status - حالة النظام\n"
            "/dbtest - اختبار اتصال Supabase\n\n"
            "🚧 وظائف تسجيل المبيعات والمشتريات "
            "والمصاريف قيد الإضافة."
        )

    # ==========================
    # STATUS
    # ==========================

    elif text == "/status":

        db_ok = check_supabase()

        send_message(
            chat_id,
            "📊 حالة نظام Islam TV For You\n\n"
            "✅ البوت يعمل\n"
            "✅ اتصال Telegram فعال\n"
            "✅ حساب المالك محمي\n"
            +
            (
                "✅ قاعدة بيانات Supabase متصلة"
                if db_ok
                else "❌ اتصال Supabase غير متاح"
            )
        )

    # ==========================
    # DATABASE TEST
    # ==========================

    elif text == "/dbtest":

        send_message(
            chat_id,
            "⏳ جارٍ اختبار الاتصال بقاعدة البيانات..."
        )

        if check_supabase():
            send_message(
                chat_id,
                "✅ الاتصال بقاعدة بيانات Supabase ناجح!\n\n"
                "📦 جدول products متاح."
            )
        else:
            send_message(
                chat_id,
                "❌ فشل الاتصال بقاعدة البيانات.\n\n"
                "تحقق من إعدادات Supabase في Render "
                "ومن صلاحيات المفتاح."
            )

    # ==========================
    # UNKNOWN COMMAND
    # ==========================

    else:

        send_message(
            chat_id,
            "⚠️ الأمر غير معروف.\n"
            "أرسل /help لعرض الأوامر المتاحة."
        )

    return "OK"


# ==============================
# SET WEBHOOK
# ==============================

@app.route("/set-webhook")
def set_webhook():

    if not BOT_TOKEN or not RENDER_URL:
        return "Missing BOT_TOKEN or RENDER_EXTERNAL_URL", 500

    webhook_url = (
        RENDER_URL.rstrip("/") + "/telegram-webhook"
    )

    try:
        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url},
            timeout=20
        )

        return response.text, response.status_code

    except requests.RequestException as error:
        return str(error), 500


# ==============================
# RUN SERVER
# ==============================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
