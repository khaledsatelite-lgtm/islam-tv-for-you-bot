
import os
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20
    )


@app.route("/")
def home():
    return "Islam TV For You Bot is running!"


@app.route("/telegram-webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id:
        return "OK"

    if text == "/start":
        send_message(
            chat_id,
            "مرحبا بك في نظام Islam TV For You 📺\n\n"
            "البوت قيد الإعداد.\n"
            "قريباً ستتمكن من تسجيل المبيعات "
            "والمشتريات والمصاريف ومتابعة الأرباح وCredits."
        )
    elif text == "/help":
        send_message(
            chat_id,
            "أوامر البوت:\n/start - البداية\n/help - المساعدة"
        )
    else:
        send_message(
            chat_id,
            "وصلت رسالتك 👍 النظام قيد الإعداد."
        )

    return "OK"


@app.route("/set-webhook")
def set_webhook():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url or not TOKEN:
        return "Missing configuration", 500

    result = requests.post(
        f"{API}/setWebhook",
        json={"url": url + "/telegram-webhook"},
        timeout=20
    )
    return result.text
