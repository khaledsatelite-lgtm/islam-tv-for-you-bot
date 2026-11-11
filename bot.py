
import os
import requests
from flask import Flask, request

app = Flask(__name__)

# =====================================
# SETTINGS
# =====================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID", "")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Temporary conversation steps
user_states = {}


# =====================================
# TELEGRAM HELPERS
# =====================================

def send_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = {
            "inline_keyboard": keyboard
        }

    try:
        requests.post(
            f"{TG_API}/sendMessage",
            json=payload,
            timeout=20
        )
    except requests.RequestException:
        pass


def answer_callback(callback_id, text=""):
    try:
        requests.post(
            f"{TG_API}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id,
                "text": text
            },
            timeout=15
        )
    except requests.RequestException:
        pass


# =====================================
# SUPABASE HELPERS
# =====================================

def db_request(method, table="products", params=None, body=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("Supabase settings are missing")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    response = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers,
        params=params,
        json=body,
        timeout=20
    )

    if not response.ok:
        raise Exception(
            f"Database error {response.status_code}: "
            f"{response.text[:300]}"
        )

    if response.text:
        return response.json()

    return []


def get_products(active_only=False):
    params = {
        "select": "id,name,category,purchase_price,selling_price,notes,active",
        "order": "name.asc"
    }

    if active_only:
        params["active"] = "eq.true"

    return db_request("GET", params=params)


def get_product(product_id):
    rows = db_request(
        "GET",
        params={
            "id": f"eq.{product_id}",
            "select": "id,name,category,purchase_price,selling_price,active",
            "limit": "1"
        }
    )

    return rows[0] if rows else None


def money(value):
    return f"{float(value):,.2f}".rstrip("0").rstrip(".")


# =====================================
# MENUS
# =====================================

def main_menu(chat_id):
    keyboard = [
        [
            {"text": "📦 عرض المنتجات", "callback_data": "prod:list"}
        ],
        [
            {"text": "➕ إضافة منتج", "callback_data": "prod:add"}
        ],
        [
            {"text": "✏️ تعديل الأسعار", "callback_data": "prod:edit"}
        ],
        [
            {"text": "⛔ إيقاف منتج", "callback_data": "prod:off"}
        ],
        [
            {"text": "📊 حالة النظام", "callback_data": "prod:status"}
        ]
    ]

    send_message(
        chat_id,
        "📺 Islam TV For You\n\n"
        "اختر العملية التي تريد تنفيذها:",
        keyboard
    )


# =====================================
# PRODUCT LIST
# =====================================

def show_products(chat_id):
    try:
        products = get_products(active_only=True)

        if not products:
            send_message(
                chat_id,
                "📦 لا توجد منتجات مفعّلة حالياً.\n"
                "اضغط إضافة منتج للبدء."
            )
            return

        lines = ["📦 قائمة المنتجات المفعّلة:\n"]

        for index, p in enumerate(products, 1):
            lines.append(
                f"{index}. {p['name']}\n"
                f"التصنيف: {p.get('category') or '-'}\n"
                f"الشراء: {money(p['purchase_price'])} دج\n"
                f"البيع: {money(p['selling_price'])} دج\n"
            )

        send_message(chat_id, "\n".join(lines))

    except Exception as error:
        send_message(chat_id, f"❌ تعذر جلب المنتجات:\n{error}")


# =====================================
# ADD PRODUCT FLOW
# =====================================

def start_add(chat_id, user_id):
    user_states[user_id] = {"step": "add_name"}

    send_message(
        chat_id,
        "➕ إضافة منتج جديد\n\n"
        "أرسل اسم المنتج.\n\n"
        "مثال: NEO 4K\n"
        "للإلغاء أرسل /cancel"
    )


def process_add(chat_id, user_id, text):
    state = user_states.get(user_id, {})
    step = state.get("step")

    if step == "add_name":
        state["name"] = text
        state["step"] = "add_category"
        send_message(chat_id, "أرسل تصنيف المنتج.\nمثال: IPTV أو Receiver")

    elif step == "add_category":
        state["category"] = text
        state["step"] = "add_purchase"
        send_message(chat_id, "أرسل سعر الشراء بالدينار الجزائري.")

    elif step == "add_purchase":
        try:
            value = float(text.replace(",", "."))
            if value < 0:
                raise ValueError()
            state["purchase_price"] = value
            state["step"] = "add_selling"
            send_message(chat_id, "أرسل سعر البيع بالدينار الجزائري.")
        except ValueError:
            send_message(chat_id, "❌ أدخل مبلغاً صحيحاً، مثال: 2200")

    elif step == "add_selling":
        try:
            value = float(text.replace(",", "."))
            if value < 0:
                raise ValueError()
            state["selling_price"] = value
            state["step"] = "add_notes"
            send_message(
                chat_id,
                "أرسل ملاحظات المنتج، أو أرسل - إذا لم توجد ملاحظات."
            )
        except ValueError:
            send_message(chat_id, "❌ أدخل مبلغاً صحيحاً، مثال: 3500")

    elif step == "add_notes":
        notes = "" if text == "-" else text

        body = {
            "name": state["name"],
            "category": state["category"],
            "purchase_price": state["purchase_price"],
            "selling_price": state["selling_price"],
            "notes": notes,
            "active": True
        }

        try:
            db_request("POST", body=body)
            profit = state["selling_price"] - state["purchase_price"]

            send_message(
                chat_id,
                "✅ تمت إضافة المنتج بنجاح!\n\n"
                f"📦 الاسم: {state['name']}\n"
                f"التصنيف: {state['category']}\n"
                f"سعر الشراء: {money(state['purchase_price'])} دج\n"
                f"سعر البيع: {money(state['selling_price'])} دج\n"
                f"الفرق بين السعرين: {money(profit)} دج"
            )

        except Exception as error:
            send_message(chat_id, f"❌ لم تتم إضافة المنتج:\n{error}")

        finally:
            user_states.pop(user_id, None)


# =====================================
# EDIT PRODUCT
# =====================================

def choose_product(chat_id, action):
    try:
        products = get_products(active_only=True)

        if not products:
            send_message(chat_id, "لا توجد منتجات مفعّلة.")
            return

        keyboard = []

        for p in products[:30]:
            keyboard.append([
                {
                    "text": p["name"],
                    "callback_data": f"pick{action}:{p['id']}"
                }
            ])

        send_message(
            chat_id,
            "اختر المنتج:",
            keyboard
        )

    except Exception as error:
        send_message(chat_id, f"❌ خطأ:\n{error}")


def start_edit(chat_id, user_id, product_id):
    try:
        product = get_product(product_id)

        if not product or not product["active"]:
            send_message(chat_id, "المنتج غير موجود أو غير مفعّل.")
            return

        user_states[user_id] = {
            "step": "edit_purchase",
            "product_id": product_id,
            "name": product["name"]
        }

        send_message(
            chat_id,
            f"✏️ تعديل أسعار: {product['name']}\n\n"
            f"السعر الحالي للشراء: {money(product['purchase_price'])} دج\n"
            f"السعر الحالي للبيع: {money(product['selling_price'])} دج\n\n"
            "أرسل سعر الشراء الجديد.\n"
            "للإلغاء أرسل /cancel"
        )

    except Exception as error:
        send_message(chat_id, f"❌ خطأ:\n{error}")


def process_edit(chat_id, user_id, text):
    state = user_states.get(user_id, {})

    try:
        value = float(text.replace(",", "."))
        if value < 0:
            raise ValueError()

    except ValueError:
        send_message(chat_id, "❌ أدخل مبلغاً صحيحاً.")
        return

    if state["step"] == "edit_purchase":
        state["purchase_price"] = value
        state["step"] = "edit_selling"

        send_message(chat_id, "أرسل سعر البيع الجديد.")

    elif state["step"] == "edit_selling":
        try:
            db_request(
                "PATCH",
                params={"id": f"eq.{state['product_id']}"},
                body={
                    "purchase_price": state["purchase_price"],
                    "selling_price": value
                }
            )

            send_message(
                chat_id,
                "✅ تم تحديث الأسعار بنجاح.\n\n"
                f"📦 {state['name']}\n"
                f"الشراء: {money(state['purchase_price'])} دج\n"
                f"البيع: {money(value)} دج"
            )

        except Exception as error:
            send_message(chat_id, f"❌ فشل تحديث الأسعار:\n{error}")

        finally:
            user_states.pop(user_id, None)


# =====================================
# DEACTIVATE PRODUCT
# =====================================

def deactivate_product(chat_id, product_id):
    try:
        product = get_product(product_id)

        if not product:
            send_message(chat_id, "المنتج غير موجود.")
            return

        db_request(
            "PATCH",
            params={"id": f"eq.{product_id}"},
            body={"active": False}
        )

        send_message(
            chat_id,
            f"✅ تم إيقاف المنتج: {product['name']}\n"
            "لم يتم حذف سجله من قاعدة البيانات."
        )

    except Exception as error:
        send_message(chat_id, f"❌ تعذر إيقاف المنتج:\n{error}")


# =====================================
# STATUS
# =====================================

def status_message():
    db_ok = False

    try:
        db_request(
            "GET",
            params={"select": "id", "limit": "1"}
        )
        db_ok = True
    except Exception:
        pass

    return (
        "📊 حالة النظام\n\n"
        "✅ Telegram Bot يعمل\n"
        "✅ حماية المالك مفعّلة\n"
        + (
            "✅ Supabase متصل"
            if db_ok else
            "❌ Supabase غير متصل"
        )
    )


# =====================================
# WEBHOOK
# =====================================

@app.route("/")
def home():
    return "Islam TV For You Bot is running!"


@app.route("/telegram-webhook", methods=["POST"])
def webhook():

    data = request.get_json(silent=True) or {}

    # Callback buttons
    callback = data.get("callback_query")

    if callback:
        user = callback.get("from", {})
        user_id = str(user.get("id", ""))
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        action = callback.get("data", "")

        answer_callback(callback.get("id"))

        if not OWNER_ID or user_id != OWNER_ID:
            return "OK"

        if action == "prod:list":
            show_products(chat_id)

        elif action == "prod:add":
            start_add(chat_id, user_id)

        elif action == "prod:edit":
            choose_product(chat_id, "edit")

        elif action == "prod:off":
            choose_product(chat_id, "off")

        elif action == "prod:status":
            send_message(chat_id, status_message())

        elif action.startswith("pickedit:"):
            product_id = action.split(":", 1)[1]
            start_edit(chat_id, user_id, product_id)

        elif action.startswith("pickoff:"):
            product_id = action.split(":", 1)[1]
            deactivate_product(chat_id, product_id)

        return "OK"

    # Normal messages
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
        send_message(chat_id, "⛔ هذا البوت خاص بصاحبه فقط.")
        return "OK"

    if text == "/cancel":
        user_states.pop(user_id, None)
        send_message(chat_id, "تم إلغاء العملية.")
        return "OK"

    if text == "/start" or text == "/menu":
        main_menu(chat_id)
        return "OK"

    if text == "/help":
        send_message(
            chat_id,
            "📋 الأوامر:\n\n"
            "/start - القائمة الرئيسية\n"
            "/products - عرض المنتجات\n"
            "/addproduct - إضافة منتج\n"
            "/editproduct - تعديل الأسعار\n"
            "/deactivateproduct - إيقاف منتج\n"
            "/status - حالة النظام\n"
            "/cancel - إلغاء العملية"
        )
        return "OK"

    if text == "/products":
        show_products(chat_id)
        return "OK"

    if text == "/addproduct":
        start_add(chat_id, user_id)
        return "OK"

    if text == "/editproduct":
        choose_product(chat_id, "edit")
        return "OK"

    if text == "/deactivateproduct":
        choose_product(chat_id, "off")
        return "OK"

    if text == "/status":
        send_message(chat_id, status_message())
        return "OK"

    state = user_states.get(user_id, {})
    step = state.get("step")

    if step and step.startswith("add_"):
        process_add(chat_id, user_id, text)

    elif step and step.startswith("edit_"):
        process_edit(chat_id, user_id, text)

    else:
        send_message(
            chat_id,
            "اختر عملية من القائمة أو أرسل /help."
        )

    return "OK"


# =====================================
# SET WEBHOOK
# =====================================

@app.route("/set-webhook")
def set_webhook():

    if not BOT_TOKEN or not RENDER_URL:
        return "Missing configuration", 500

    url = RENDER_URL.rstrip("/") + "/telegram-webhook"

    try:
        response = requests.post(
            f"{TG_API}/setWebhook",
            json={"url": url},
            timeout=20
        )

        return response.text, response.status_code

    except requests.RequestException as error:
        return str(error), 500


# =====================================
# START SERVER
# =====================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
