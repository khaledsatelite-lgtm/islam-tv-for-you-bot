
import os
import logging
import requests
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Temporary conversation states
states = {}


# =====================================
# TELEGRAM
# =====================================

def tg(method, payload):
    r = requests.post(
        f"{TG}/{method}",
        json=payload,
        timeout=20
    )
    r.raise_for_status()
    return r.json()


def send(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    tg("sendMessage", payload)


def edit_message(chat_id, message_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    tg("editMessageText", payload)


def callback_answer(callback_id, text=""):
    try:
        tg("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": text
        })
    except Exception:
        pass


# =====================================
# SUPABASE
# =====================================

def db(method, table, params=None, body=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("إعدادات Supabase غير موجودة")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    r = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers,
        params=params,
        json=body,
        timeout=25
    )

    if not r.ok:
        logging.error("Supabase %s: %s", table, r.text[:500])
        raise Exception(
            f"خطأ قاعدة البيانات ({r.status_code}): {r.text[:250]}"
        )

    return r.json() if r.text else []


def products(active=True):
    params = {
        "select": "id,name,category,purchase_price,selling_price,active",
        "order": "name.asc"
    }
    if active:
        params["active"] = "eq.true"
    return db("GET", "products", params)


def customers():
    return db(
        "GET", "customers",
        {"select": "*", "order": "id.desc", "limit": "30"}
    )


def product_by_id(pid):
    rows = db(
        "GET", "products",
        {"id": f"eq.{pid}", "select": "*", "limit": "1"}
    )
    return rows[0] if rows else None


def customer_by_id(cid):
    rows = db(
        "GET", "customers",
        {"id": f"eq.{cid}", "select": "*", "limit": "1"}
    )
    return rows[0] if rows else None


def fmt(value):
    return f"{float(value):,.2f}".rstrip("0").rstrip(".")


# =====================================
# MAIN MENU
# =====================================

def main_menu(chat_id):
    keyboard = [
        [{"text": "🛒 عملية بيع جديدة", "callback_data": "sale"}],
        [{"text": "📦 عرض المنتجات", "callback_data": "products"}],
        [{"text": "➕ إضافة منتج", "callback_data": "addproduct"}],
        [{"text": "✏️ تعديل الأسعار", "callback_data": "editproduct"}],
        [{"text": "⛔ إيقاف منتج", "callback_data": "offproduct"}],
        [{"text": "👥 العملاء", "callback_data": "customers"}],
        [{"text": "➕ إضافة عميل", "callback_data": "addcustomer"}],
        [{"text": "📊 تقرير المبيعات", "callback_data": "report"}],
        [{"text": "🔄 تحديث القائمة", "callback_data": "menu"}]
    ]
    send(chat_id, "📺 Islam TV For You\n\nاختر العملية:", keyboard)


# =====================================
# PRODUCTS
# =====================================

def show_products(chat_id):
    try:
        rows = products()
        if not rows:
            send(chat_id, "لا توجد منتجات مفعّلة.")
            return

        lines = ["📦 المنتجات المفعّلة:\n"]
        for p in rows:
            lines.append(
                f"• {p['name']}\n"
                f"التصنيف: {p.get('category') or '-'}\n"
                f"الشراء: {fmt(p['purchase_price'])} دج\n"
                f"البيع: {fmt(p['selling_price'])} دج\n"
            )
        send(chat_id, "\n".join(lines))
    except Exception as e:
        send(chat_id, f"❌ خطأ: {e}")


def product_buttons(chat_id, prefix):
    rows = products()
    if not rows:
        send(chat_id, "لا توجد منتجات مفعّلة.")
        return

    keyboard = []
    for p in rows[:40]:
        keyboard.append([{
            "text": p["name"],
            "callback_data": f"{prefix}:{p['id']}"
        }])

    send(chat_id, "اختر المنتج:", keyboard)


# =====================================
# ADD PRODUCT
# =====================================

def start_add_product(chat_id, uid):
    states[uid] = {"step": "p_name"}
    send(chat_id, "أرسل اسم المنتج الجديد.\nأرسل /cancel للإلغاء.")


def add_product_step(chat_id, uid, text):
    s = states[uid]
    step = s["step"]

    if step == "p_name":
        s["name"] = text
        s["step"] = "p_category"
        send(chat_id, "أرسل تصنيف المنتج.")

    elif step == "p_category":
        s["category"] = text
        s["step"] = "p_cost"
        send(chat_id, "أرسل سعر الشراء بالدينار.")

    elif step == "p_cost":
        try:
            x = float(text.replace(",", "."))
            if x < 0:
                raise ValueError()
            s["cost"] = x
            s["step"] = "p_sell"
            send(chat_id, "أرسل سعر البيع بالدينار.")
        except ValueError:
            send(chat_id, "أدخل مبلغاً صحيحاً.")

    elif step == "p_sell":
        try:
            x = float(text.replace(",", "."))
            if x < 0:
                raise ValueError()
            s["sell"] = x
            s["step"] = "p_notes"
            send(chat_id, "أرسل الملاحظات أو - بدون ملاحظات.")
        except ValueError:
            send(chat_id, "أدخل مبلغاً صحيحاً.")

    elif step == "p_notes":
        try:
            db("POST", "products", body={
                "name": s["name"],
                "category": s["category"],
                "purchase_price": s["cost"],
                "selling_price": s["sell"],
                "notes": "" if text == "-" else text,
                "active": True
            })
            send(chat_id, "✅ تمت إضافة المنتج بنجاح.")
        except Exception as e:
            send(chat_id, f"❌ تعذرت الإضافة: {e}")
        finally:
            states.pop(uid, None)


# =====================================
# EDIT PRODUCT
# =====================================

def start_edit(chat_id, uid, pid):
    p = product_by_id(pid)
    if not p or not p.get("active"):
        send(chat_id, "المنتج غير متاح.")
        return

    states[uid] = {
        "step": "edit_cost",
        "pid": pid,
        "name": p["name"]
    }
    send(
        chat_id,
        f"تعديل {p['name']}\n"
        f"سعر الشراء الحالي: {fmt(p['purchase_price'])}\n"
        f"سعر البيع الحالي: {fmt(p['selling_price'])}\n\n"
        "أرسل سعر الشراء الجديد."
    )


def edit_step(chat_id, uid, text):
    s = states[uid]
    try:
        x = float(text.replace(",", "."))
        if x < 0:
            raise ValueError()
    except ValueError:
        send(chat_id, "أدخل مبلغاً صحيحاً.")
        return

    if s["step"] == "edit_cost":
        s["cost"] = x
        s["step"] = "edit_sell"
        send(chat_id, "أرسل سعر البيع الجديد.")

    else:
        try:
            db(
                "PATCH", "products",
                {"id": f"eq.{s['pid']}"},
                {
                    "purchase_price": s["cost"],
                    "selling_price": x
                }
            )
            send(chat_id, "✅ تم تحديث الأسعار بنجاح.")
        except Exception as e:
            send(chat_id, f"❌ خطأ: {e}")
        finally:
            states.pop(uid, None)


# =====================================
# CUSTOMERS
# =====================================

def show_customers(chat_id):
    try:
        rows = customers()
        if not rows:
            send(chat_id, "لا يوجد عملاء مسجلون.")
            return

        lines = ["👥 العملاء:\n"]
        for c in rows:
            lines.append(
                f"• {c.get('name', 'بدون اسم')} "
                f"| {c.get('phone') or '-'}"
            )
        send(chat_id, "\n".join(lines))
    except Exception as e:
        send(chat_id, f"❌ خطأ: {e}")


def start_add_customer(chat_id, uid):
    states[uid] = {"step": "c_name"}
    send(chat_id, "أرسل اسم العميل.")


def add_customer_step(chat_id, uid, text):
    s = states[uid]
    if s["step"] == "c_name":
        s["name"] = text
        s["step"] = "c_phone"
        send(chat_id, "أرسل رقم الهاتف أو - إذا لم يتوفر.")

    else:
        try:
            db("POST", "customers", body={
                "name": s["name"],
                "phone": None if text == "-" else text
            })
            send(chat_id, "✅ تمت إضافة العميل.")
        except Exception as e:
            send(chat_id, f"❌ تعذرت إضافة العميل: {e}")
        finally:
            states.pop(uid, None)


# =====================================
# SALES
# =====================================

def start_sale(chat_id):
    rows = products()
    if not rows:
        send(chat_id, "لا توجد منتجات. أضف منتجاً أولاً.")
        return

    keyboard = []
    for p in rows[:40]:
        keyboard.append([{
            "text": p["name"],
            "callback_data": f"saleproduct:{p['id']}"
        }])

    send(chat_id, "🛒 اختر المنتج الذي تريد بيعه:", keyboard)


def select_sale_product(chat_id, uid, pid):
    p = product_by_id(pid)
    if not p or not p.get("active"):
        send(chat_id, "المنتج غير متاح.")
        return

    states[uid] = {
        "step": "sale_customer",
        "pid": pid,
        "name": p["name"],
        "cost": float(p["purchase_price"]),
        "price": float(p["selling_price"])
    }

    try:
        rows = customers()
        keyboard = [[{
            "text": c.get("name", "عميل"),
            "callback_data": f"salecustomer:{c['id']}"
        }] for c in rows[:30]]

        keyboard.append([{
            "text": "👤 عميل جديد / بدون تسجيل",
            "callback_data": "sale_newcustomer"
        }])

        send(
            chat_id,
            f"📦 المنتج: {p['name']}\n"
            f"سعر البيع: {fmt(p['selling_price'])} دج\n"
            f"التكلفة: {fmt(p['purchase_price'])} دج\n\n"
            "اختر العميل:",
            keyboard
        )
    except Exception as e:
        send(chat_id, f"❌ خطأ في العملاء: {e}")


def choose_sale_customer(chat_id, uid, cid):
    c = customer_by_id(cid)
    if not c:
        send(chat_id, "العميل غير موجود.")
        return

    s = states.get(uid)
    if not s:
        send(chat_id, "انتهت العملية. ابدأ بيعاً جديداً.")
        return

    s["customer_id"] = cid
    s["customer_name"] = c.get("name", "")
    s["step"] = "sale_paid"
    send(
        chat_id,
        f"العميل: {s['customer_name']}\n"
        f"سعر البيع المقترح: {fmt(s['price'])} دج\n\n"
        "أرسل المبلغ الذي دفعه العميل."
    )


def choose_new_customer(chat_id, uid):
    s = states.get(uid)
    if not s:
        return
    s["step"] = "sale_new_name"
    send(chat_id, "أرسل اسم العميل الجديد، أو أرسل - للبيع دون تسجيل اسم.")


def save_sale(chat_id, uid, paid):
    s = states.get(uid)
    if not s:
        send(chat_id, "انتهت العملية. ابدأ من جديد.")
        return

    price = s["price"]
    cost = s["cost"]

    if paid < 0:
        send(chat_id, "المبلغ لا يمكن أن يكون سالباً.")
        return

    total = price
    profit = total - cost
    remaining = max(total - paid, 0)

    if paid > total:
        send(
            chat_id,
            f"المبلغ المدفوع أكبر من سعر البيع ({fmt(total)} دج).\n"
            "أعد إدخال المبلغ."
        )
        return

    body = {
        "customer_id": s.get("customer_id"),
        "product_id": s["pid"],
        "quantity": 1,
        "selling_unit_price": price,
        "purchase_unit_cost": cost,
        "total_amount": total,
        "total_cost": cost,
        "paid_amount": paid,
        "profit": profit,
        "notes": (
            f"العميل: {s.get('customer_name', 'غير مسجل')}; "
            f"المتبقي: {remaining}"
        )
    }

    try:
        db("POST", "sales", body=body)

        send(
            chat_id,
            "✅ تم تسجيل البيع بنجاح!\n\n"
            f"📦 المنتج: {s['name']}\n"
            f"👤 العميل: {s.get('customer_name', 'غير مسجل')}\n"
            f"💰 سعر البيع: {fmt(total)} دج\n"
            f"📉 التكلفة: {fmt(cost)} دج\n"
            f"🟢 الربح الإجمالي: {fmt(profit)} دج\n"
            f"💳 المدفوع: {fmt(paid)} دج\n"
            f"⏳ المتبقي: {fmt(remaining)} دج"
        )

    except Exception as e:
        send(chat_id, f"❌ لم يتم حفظ البيع:\n{e}")

    finally:
        states.pop(uid, None)


# =====================================
# REPORT
# =====================================

def sales_report(chat_id):
    try:
        rows = db(
            "GET", "sales",
            {
                "select": "total_amount,total_cost,paid_amount,profit",
                "limit": "1000"
            }
        )

        total_sales = sum(float(x.get("total_amount") or 0) for x in rows)
        total_cost = sum(float(x.get("total_cost") or 0) for x in rows)
        total_paid = sum(float(x.get("paid_amount") or 0) for x in rows)
        profit = sum(float(x.get("profit") or 0) for x in rows)

        send(
            chat_id,
            "📊 تقرير المبيعات المسجلة\n\n"
            f"عدد العمليات: {len(rows)}\n"
            f"إجمالي المبيعات: {fmt(total_sales)} دج\n"
            f"إجمالي التكلفة: {fmt(total_cost)} دج\n"
            f"المبالغ المحصلة: {fmt(total_paid)} دج\n"
            f"الربح الإجمالي: {fmt(profit)} دج"
        )
    except Exception as e:
        send(chat_id, f"❌ تعذر إعداد التقرير:\n{e}")


# =====================================
# WEBHOOK
# =====================================

@app.route("/")
def home():
    return "Islam TV For You Bot is running!"


@app.route("/telegram-webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    callback = data.get("callback_query")

    if callback:
        user = callback.get("from", {})
        uid = str(user.get("id", ""))
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        action = callback.get("data", "")

        callback_answer(callback.get("id"))

        if not OWNER_ID or uid != OWNER_ID:
            return "OK"

        if action == "menu":
            main_menu(chat_id)
        elif action == "sale":
            start_sale(chat_id)
        elif action == "products":
            show_products(chat_id)
        elif action == "addproduct":
            start_add_product(chat_id, uid)
        elif action == "editproduct":
            product_buttons(chat_id, "edit")
        elif action == "offproduct":
            product_buttons(chat_id, "off")
        elif action == "customers":
            show_customers(chat_id)
        elif action == "addcustomer":
            start_add_customer(chat_id, uid)
        elif action == "report":
            sales_report(chat_id)

        elif action.startswith("saleproduct:"):
            select_sale_product(chat_id, uid, action.split(":", 1)[1])
        elif action.startswith("salecustomer:"):
            choose_sale_customer(chat_id, uid, action.split(":", 1)[1])
        elif action == "sale_newcustomer":
            choose_new_customer(chat_id, uid)
        elif action.startswith("edit:"):
            start_edit(chat_id, uid, action.split(":", 1)[1])
        elif action.startswith("off:"):
            pid = action.split(":", 1)[1]
            try:
                db("PATCH", "products", {"id": f"eq.{pid}"}, {"active": False})
                send(chat_id, "✅ تم إيقاف المنتج دون حذف سجله.")
            except Exception as e:
                send(chat_id, f"❌ خطأ: {e}")

        return "OK"

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    uid = str(message.get("from", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return "OK"

    if not OWNER_ID or uid != OWNER_ID:
        send(chat_id, "⛔ هذا البوت خاص بصاحبه فقط.")
        return "OK"

    if text == "/cancel":
        states.pop(uid, None)
        send(chat_id, "تم إلغاء العملية.")
        return "OK"

    if text in ("/start", "/menu"):
        main_menu(chat_id)
        return "OK"

    if text == "/status":
        try:
            db("GET", "products", {"select": "id", "limit": "1"})
            send(chat_id, "✅ البوت يعمل\n✅ Supabase متصل\n✅ حساب المالك محمي")
        except Exception as e:
            send(chat_id, f"❌ مشكلة اتصال Supabase:\n{e}")
        return "OK"

    if text == "/help":
        send(chat_id, "استعمل الأزرار في القائمة الرئيسية.\n/cancel لإلغاء أي عملية.")
        return "OK"

    s = states.get(uid, {})
    step = s.get("step", "")

    if step.startswith("p_"):
        add_product_step(chat_id, uid, text)
    elif step.startswith("edit_"):
        edit_step(chat_id, uid, text)
    elif step.startswith("c_"):
        add_customer_step(chat_id, uid, text)
    elif step == "sale_paid":
        try:
            paid = float(text.replace(",", "."))
            save_sale(chat_id, uid, paid)
        except ValueError:
            send(chat_id, "أدخل مبلغاً صحيحاً.")
    elif step == "sale_new_name":
        s["customer_name"] = "" if text == "-" else text
        s["step"] = "sale_new_phone"
        send(chat_id, "أرسل رقم الهاتف أو - بدون رقم.")
    elif step == "sale_new_phone":
        try:
            if s.get("customer_name"):
                new_customer = db("POST", "customers", body={
                    "name": s["customer_name"],
                    "phone": None if text == "-" else text
                })
                if new_customer:
                    s["customer_id"] = new_customer[0]["id"]
            s["step"] = "sale_paid"
            send(
                chat_id,
                f"المنتج: {s['name']}\n"
                f"سعر البيع: {fmt(s['price'])} دج\n"
                "أرسل المبلغ المدفوع."
            )
        except Exception as e:
            send(chat_id, f"❌ خطأ في تسجيل العميل: {e}")

    else:
        send(chat_id, "اختر عملية من القائمة الرئيسية: /start")

    return "OK"


# =====================================
# WEBHOOK SETUP
# =====================================

@app.route("/set-webhook")
def set_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not BOT_TOKEN or not render_url:
        return "Missing configuration", 500

    url = render_url.rstrip("/") + "/telegram-webhook"
    try:
        return requests.post(
            f"{TG}/setWebhook",
            json={"url": url},
            timeout=20
        ).text
    except Exception as e:
        return str(e), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
