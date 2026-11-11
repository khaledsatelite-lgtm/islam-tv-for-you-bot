
import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Configuration
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    if not TOKEN:
        return

    try:
        requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=20
        )
    except requests.RequestException:
        pass


@app.route("/")
def home():
    return "Islam TV For You Bot is running!"


@app.route("/telegram-webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    message = data.get("message", {})
    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_id = chat.get("id")
    user_id = str(user.get("id", ""))
    text = message.get("text", "").strip()

    if not chat_id:
        return "OK"

    # Owner protection
    if not OWNER_ID or user_id != OWNER_ID:
        send_message(
            chat_id,
            "⛔ هذا البوت خاص بصاحبه فقط."
        )
        return "OK"

    # Start command
    if text == "/start":
        send_message(
            chat_id,
            "📺 مرحبا بك في نظام Islam TV For You\n\n"
            "👤 حساب المالك: مفعل\n"
            "🔐 الحماية: مفعلة\n\n"
            "📊 نظام إدارة المبيعات والمشتريات "
            "والمصاريف والأرباح وCredits.\n\n"
            "🚧 النظام قيد التطوير.\n"
            "قريباً ستتمكن من تسجيل عملياتك ومتابعة نشاطك."
        )

    # Help command
    elif text == "/help":
        send_message(
            chat_id,
            "📋 أوامر البوت:\n\n"
            "/start - البداية\n"
            "/help - المساعدة\n"
            "/status - حالة النظام\n\n"
            "ستضاف أوامر المبيعات والمشتريات "
            "والمصاريف وCredits في المرحلة القادمة."
        )

    # Status command
    elif text == "/status":
        send_message(
            chat_id,
            "✅ البوت يعمل\n"
            "✅ اتصال Telegram فعال\n"
            "✅ حساب المالك محمي\n"
            "🚧 ربط عمليات Supabase قيد التطوير."
        )

    else:
        send_message(
            chat_id,
            "👍 وصلت رسالتك.\n"
            "اكتب /help لعرض الأوامر المتاحة."
        )

    return "OK"


@app.route("/set-webhook")
def set_webhook():
    if not TOKEN or not RENDER_URL:
        return "Missing configuration", 500

    webhook_url = RENDER_URL.rstrip("/") + "/telegram-webhook"

    try:
        result = requests.post(
            f"{API}/setWebhook",
            json={"url": webhook_url},
            timeout=20
        )
        return result.text
    except requests.RequestException as error:
        return str(error), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
