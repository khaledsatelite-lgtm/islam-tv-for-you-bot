
استيراد نظام التشغيل
استيراد التسجيل
طلبات الاستيراد
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = os.environ.get("OWNER_TELEGRAM_ID", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

حالات المحادثة المؤقتة
states = {}


# =====================================
# تيليجرام
# =====================================

def tg(method, payload):
    r = requests.post(
        f"{TG}/{method}",
        json=payload,
        مهلة = 20
    )
    r.raise_for_status()
    إرجاع r.json()


دالة إرسال (معرف_الدردشة، نص، لوحة_المفاتيح=لا_شيء):
    الحمولة = {"chat_id": chat_id, "text": text}
    إذا كانت لوحة المفاتيح:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    tg("sendMessage", payload)


def edit_message(chat_id, message_id, text, keyboard=None):
    الحمولة = {
        "chat_id": chat_id,
        "message_id": message_id,
        "نص": نص
    }
    إذا كانت لوحة المفاتيح:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    tg("editMessageText", payload)


def callback_answer(callback_id, text=""):
    حاول:
        tg("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "نص": نص
        })
    باستثناء الاستثناء:
        تمرير


# =====================================
# SUPABASE
# =====================================

def db(method, table, params=None, body=None):
    إذا لم يكن SUPABASE_URL أو لم يكن SUPABASE_KEY:
        رفع الاستثناء("إعدادات Supabase غير موجودة")

    الرؤوس = {
        "apikey": SUPABASE_KEY,
        "التفويض": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "تفضيل": "return=representation"
    }

    r = requests.request(
        طريقة،
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers,
        params=params,
        json=body,
        مهلة = 25
    )

    إذا لم يكن r.ok:
        logging.error("Supabase %s: %s", table, r.text[:500])
        ارفع استثناءً (
            f" قاعدة خطأ البيانات ({r.status_code}): {r.text[:250]}"
        )

    أعد r.json() إذا كان r.text وإلا []


def products(active=True):
    params = {
        "select": "id,name,category,purchase_price,selling_price,active",
        "order": "name.asc"
    }
    إذا كان نشطًا:
        params["active"] = "eq.true"
    return db("GET", "products", params)


def customers():
    إرجاع قاعدة البيانات (
        "GET"، "customers"،
        {"select": "*", "order": "id.desc", "limit": "30"}
    )


def product_by_id(pid):
    صفوف = قاعدة البيانات (
        "GET"، "products"،
        {"id": f"eq.{pid}", "select": "*", "limit": "1"}
    )
    أعد الصف الأول إذا كان هناك صفوف، وإلا فأعد لا شيء


def customer_by_id(cid):
    صفوف = قاعدة البيانات (
        "GET"، "customers"،
        {"id": f"eq.{cid}", "select": "*", "limit": "1"}
    )
    أعد الصف الأول إذا كان هناك صفوف، وإلا فأعد لا شيء


def fmt(value):
    return f"{float(value):,.2f}".rstrip("0").rstrip(".")


# =====================================
# القائمة الرئيسية
# =====================================

def main_menu(chat_id):
    لوحة المفاتيح = [
        [{"text": "🛒 عملية بيع جديدة", "callback_data": "sale"}],
        [{"text": "📦 عرض المنتجات", "callback_data": "products"}],
        [{"text": "➕ إضافة منتج"، "callback_data": "addproduct"}]،
        [{"text": "✏️ تعديل التصاميم", "callback_data": "editproduct"}],
        [{"text": "⛔ إيقاف المنتج"، "callback_data": "offproduct"}],
        [{"text": "👥 العملاء"، "callback_data": "customers"}]،
        [{"text": "➕ إضافة عميل", "callback_data": "addcustomer"}],
        [{"text": "📊 تقرير المبيعات", "callback_data": "report"}],
        [{"text": "🔄 تحديث القائمة", "callback_data": "menu"}]
    ]
    send(chat_id, "📺 تلفزيون الإسلام من أجلك\n\nاختر الصحيح:", Keyboard)


# =====================================
# منتجات
# =====================================

def show_products(chat_id):
    حاول:
        صفوف = منتجات()
        إذا لم تكن هناك صفوف:
            send(chat_id, "لا توجد منتجات مفعّلة."")
            إرجاع

        lines = ["📦 المنتجات المفعّلة:\n"]
        for p in rows:
            lines.append(
                f"• {p['name']}\n"
                f"التصنيف: {p.get('category') or '-'}\n"
                f"الشراء: {fmt(p['purchase_price'])} دج\n"
                f"البيع: {fmt(p['selling_price'])} دج\n"
            )
        send(chat_id, "\n".join(lines))
    باستثناء الاستثناء كـ e:
        إرسال(chat_id, f"❌ خطأ: {e}")


def product_buttons(chat_id, prefix):
    صفوف = منتجات()
    إذا لم تكن هناك صفوف:
        send(chat_id, "لا توجد منتجات مفعّلة."")
        إرجاع

    لوحة المفاتيح = []
    for p in rows[:40]:
        keyboard.append([{
            "نص": p["اسم"],
            "callback_data": f"{prefix}:{p['id']}"
        }])

    إرسال (chat_id، "اختر المنتج:"، لوحة المفاتيح)


# =====================================
# إضافة منتج
# =====================================

def start_add_product(chat_id, uid):
    states[uid] = {"step": "p_name"}
    send(chat_id, "أرسل اسم المنتج الجديد.\nأرسل /إلغاء للإلغاء.")


دالة إضافة_خطوة_المنتج(معرف_المحادثة، معرف_التطبيق، النص):
    s = states[uid]
    خطوة = s["خطوة"]

    إذا كانت الخطوة تساوي "p_name":
        s["name"] = نص
        s["step"] = "p_category"
        send(chat_id, "أرسل تصنيف المنتج.")

    elif step == "p_category":
        s["category"] = نص
        s["step"] = "p_cost"
        send(chat_id, "أرسل سعر الشراء بالدينار.")

    elif step == "p_cost":
        حاول:
            x = float(text.replace(",", "."))
            إذا كانت قيمة x أقل من 0:
                ارفع ValueError()
            s["cost"] = x
            s["step"] = "p_sell"
            send(chat_id, "أرسل سعر البيع بالدينار.")
        باستثناء ValueError:
            send(chat_id, "أدخل مبلغاً عادياً.")

    elif step == "p_sell":
        حاول:
            x = float(text.replace(",", "."))
            إذا كانت قيمة x أقل من 0:
                ارفع ValueError()
            s["sell"] = x
            s["step"] = "p_notes"
            send(chat_id, "أرسل الملاحظات أو - بدون ملاحظات.")
        باستثناء ValueError:
            send(chat_id, "أدخل مبلغاً عادياً.")

    elif step == "p_notes":
        حاول:
            db("POST", "products", body={
                "الاسم": s["الاسم"],
                "category": s["category"],
                "سعر_الشراء": s["التكلفة"],
                "selling_price": s["sell"],
                "ملاحظات": "" إذا كان النص يساوي "-" وإلا النص،
                "نشط": صحيح
            })
            send(chat_id, "✅ أكمل إضافة المنتج الفعال.")
        باستثناء الاستثناء كـ e:
            send(chat_id, f"❌ عذرت الإضافة: {e}")
        أخيرًا:
            states.pop(uid, None)


# =====================================
# تحرير المنتج
# =====================================

دالة بدء التحرير (معرف_الدردشة، معرف_الشخص، معرف_العملية):
    p = product_by_id(pid)
    إذا لم يكن p أو لم يكن p.get("active"):
        send(chat_id, "المنتج غير متاح.")
        إرجاع

    states[uid] = {
        "step": "edit_cost",
        "pid": pid,
        "الاسم": p["الاسم"]
    }
    إرسال(
        chat_id,
        f" تمر {p['name']}\n"
        f"سعر الشراء الحالي: {fmt(p['purchase_price'])}\n"
        f"السعر الحالي: {fmt(p['sale_price'])}\n\n"
        "أرسل سعر الشراء الجديد."
    )


دالة edit_step(chat_id, uid, text):
    s = states[uid]
    حاول:
        x = float(text.replace(",", "."))
        إذا كانت قيمة x أقل من 0:
            ارفع ValueError()
    باستثناء ValueError:
        send(chat_id, "أدخل مبلغاً عادياً.")
        إرجاع

    إذا كانت قيمة s["step"] تساوي "edit_cost":
        s["cost"] = x
        s["step"] = "edit_sell"
        send(chat_id, "أرسل سعر البيع الجديد.")

    وإلا:
        حاول:
            db(
                "PATCH"، "products"،
                {"id": f"eq.{s['pid']}"},
                {
                    "سعر_الشراء": s["التكلفة"],
                    "selling_price": x
                }
            )
            send(chat_id, ""تم تحديث المنتجات الفعالة.")
        باستثناء الاستثناء كـ e:
            إرسال(chat_id, f"❌ خطأ: {e}")
        أخيرًا:
            states.pop(uid, None)


# =====================================
# عملاء
# =====================================

def show_customers(chat_id):
    حاول:
        صفوف = عملاء()
        إذا لم تكن هناك صفوف:
            send(chat_id, "لا يوجد عملاء مسجلون.")
            إرجاع

        خطوط = ["👥 العملاء:\n"]
        for c in rows:
            lines.append(
                f"• {c.get('name', 'بدون اسم')} "
                f"| {c.get('phone') or '-'}"
            )
        send(chat_id, "\n".join(lines))
    باستثناء الاستثناء كـ e:
        إرسال(chat_id, f"❌ خطأ: {e}")


def start_add_customer(chat_id, uid):
    states[uid] = {"step": "c_name"}
    send(chat_id, "أرسل اسم العميل.")


دالة إضافة خطوة للعميل(معرف_المحادثة، معرف_الموظف، النص):
    s = states[uid]
    إذا كان s["step"] يساوي "c_name":
        s["name"] = نص
        s["step"] = "c_phone"
        send(chat_id, "أرسل رقم الهاتف أو - إذا لم يدعى."")

    وإلا:
        حاول:
            db("POST", "customers", body={
                "الاسم": s["الاسم"],
                "phone": لا شيء إذا كان النص يساوي "-" وإلا نص
            })
            send(chat_id, "✅ متابعة إضافة العميل.")
        باستثناء الاستثناء كـ e:
            send(chat_id, f"❌ عذرًا إضافة العميل: {e}")
        أخيرًا:
            states.pop(uid, None)


# =====================================
# مبيعات
# =====================================

def start_sale(chat_id):
    صفوف = منتجات()
    إذا لم تكن هناك صفوف:
        send(chat_id, "لا توجد. إضافة منتجات منتجاً الجمعة."")
        إرجاع

    لوحة المفاتيح = []
    for p in rows[:40]:
        keyboard.append([{
            "نص": p["اسم"],
            "callback_data": f"saleproduct:{p['id']}"
        }])

    send(chat_id, "🛒 اختر المنتج الذي تريد بيعه:"، Keyboard)


دالة select_sale_product(chat_id, uid, pid):
    p = product_by_id(pid)
    إذا لم يكن p أو لم يكن p.get("active"):
        send(chat_id, "المنتج غير متاح.")
        إرجاع

    states[uid] = {
        "step": "sale_customer",
        "pid": pid,
        "الاسم": p["الاسم"],
        "التكلفة": float(p["سعر_الشراء"]),
        "السعر": float(p["selling_price"])
    }

    حاول:
        صفوف = عملاء()
        لوحة المفاتيح = [[{
            "text": c.get("name", "البريد"),
            "callback_data": f"salecustomer:{c['id']}"
        }] for c in rows[:30]]

        keyboard.append([{
            "text": "👤 عميل جديد / بدون تسجيل",
            "callback_data": "sale_newcustomer"
        }])

        إرسال(
            chat_id,
            f"📦 المنتج: {p['name']}\n"
            f"السعر: {fmt(p['sale_price'])} دج\n"
            f"الطلب: {fmt(p['purchase_price'])} دج\n\n"
            "اختر جو:",
            لوحة المفاتيح
        )
    باستثناء الاستثناء كـ e:
        send(chat_id, f"❌ خطأ في العملاء: {e}")


دالة اختيار عميل البيع (معرف الدردشة، معرف المستخدم، معرف العميل):
    c = customer_by_id(cid)
    إذا لم يكن ج:
        إرسال (chat_id، "العميل غير موجود.")
        إرجاع

    s = states.get(uid)
    إذا لم يكن s:
        send(chat_id, "انتهت الحرارة. ابدأ بيعاً جديداً.")
        إرجاع

    s["customer_id"] = cid
    s["customer_name"] = c.get("name", "")
    s["step"] = "sale_paid"
    إرسال(
        chat_id,
        f"البريد الإلكتروني: {s['customer_name']}\n"
        f"سعر البيع المقترح: {fmt(s['price'])} دج\n\n"
        "أرسل الاتحاد الذي دفعه العميل."
    )


def choose_new_customer(chat_id, uid):
    s = states.get(uid)
    إذا لم يكن s:
        إرجاع
    s["step"] = "sale_new_name"
    send(chat_id, "أرسل اسم العميل الجديد، أو أرسل - للبيع دون تسجيل اسم.")


دالة حفظ_البيع(معرف_المحادثة، معرف_الموظف، مدفوع):
    s = states.get(uid)
    إذا لم يكن s:
        send(chat_id, "انتهت الحرارة. ابدأ من جديد.")
        إرجاع

    السعر = s["السعر"]
    التكلفة = s["التكلفة"]

    إذا كان المبلغ المدفوع أقل من صفر:
        send(chat_id, "المبلغ لا يمكن أن يكون سالباً.")
        إرجاع

    الإجمالي = السعر
    الربح = الإجمالي - التكلفة
    المتبقي = الحد الأقصى (الإجمالي - المدفوع، 0)

    إذا كان المبلغ المدفوع أكبر من الإجمالي:
        إرسال(
            chat_id,
            f"المبلغ المدفوع أكبر من سعر البيع ({fmt(total)} دج).\n"
            "أعد العلامة التجارية."
        )
        إرجاع

    body = {
        "customer_id": s.get("customer_id"),
        "product_id": s["pid"],
        الكمية: 1،
        "selling_unit_price": السعر،
        "purchase_unit_cost": cost,
        "total_amount": الإجمالي،
        "total_cost": cost,
        "paid_amount": مدفوع،
        «الربح»: الربح،
        «ملاحظات»: (
            f"العميل: {s.get('customer_name', 'غير مسجل')}; "
            f"المتبقي: {remaining}"
        )
    }

    حاول:
        db("POST", "sales", body=body)

        إرسال(
            chat_id,
            "✅ تم تسجيل فعال!\n\n"
            f"📦 المنتج: {s['name']}\n"
            f"👤 العميل: {s.get('customer_name', 'غير مسجل')}\n"
            f"💰 سعر البيع: {fmt(total)} دج\n"
            f"📉 التكلفة: {fmt(cost)} دج\n"
            f"🟢 تسويق الإعلانات: {fmt(profit)} دج\n"
            f"💳 المدفوع: {fmt(payed)} دج\n"
            f"⏳ النهائي: {fmt(remaining)} دج"
        )

    باستثناء الاستثناء كـ e:
        send(chat_id, f"❌ لم يتم حفظ البيع:\n{e}")

    أخيرًا:
        states.pop(uid, None)


# =====================================
# تقرير
# =====================================

def sales_report(chat_id):
    حاول:
        صفوف = قاعدة البيانات (
            "GET"، "sales"،
            {
                "select": "total_amount,total_cost,paid_amount,profit",
                "الحد": "1000"
            }
        )

        إجمالي_المبيعات = مجموع(عدد_عشري(x.get("إجمالي_المبلغ") أو 0) لكل x في الصفوف)
        التكلفة_الإجمالية = مجموع(عدد_عشري(x.get("التكلفة_الإجمالية") أو 0) لكل x في الصفوف)
        total_paid = sum(float(x.get("paid_amount") or 0) for x in rows)
        الربح = مجموع (عدد عشري (x.get("الربح") أو 0) لكل x في الصفوف)

        إرسال(
            chat_id,
            "📊 تقرير المبيعات الجديدة\n\n"
            f" عدد الصفوف: {len(rows)}\n"
            f"إجمالي المبيعات: {fmt(total_sales)} دج\n"
            f"إجمالي التكلفة: {fmt(total_cost)} دج\n"
            f"المبالغ المحصلة: {fmt(total_pay)} دج\n"
            f"الربح المعلن: {fmt(profit)} دج"
        )
    باستثناء الاستثناء كـ e:
        send(chat_id, f"❌ تعذر إعداد التقرير:\n{e}")


# =====================================
# WEBHOOK
# =====================================

@app.route("/")
def home():
    "يعمل بوت Islam TV For You!"


@app.route("/telegram-webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    callback = data.get("callback_query")

    إذا كان رد الاتصال:
        المستخدم = callback.get("from", {})
        uid = str(user.get("id", ""))
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        action = callback.get("data", "")

        callback_answer(callback.get("id"))

        إذا لم يكن OWNER_ID أو uid != OWNER_ID:
            إرجاع "موافق"

        إذا كان الإجراء يساوي "القائمة":
            main_menu(chat_id)
        elif action == "sale":
            start_sale(chat_id)
        elif action == "products":
            عرض_المنتجات(معرف_الدردشة)
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
            حاول:
                db("PATCH", "products", {"id": f"eq.{pid}"}, {"active": False})
                send(chat_id, ""تم إيقاف المنتج دون حذف السجل.")
            باستثناء الاستثناء كـ e:
                إرسال(chat_id, f"❌ خطأ: {e}")

        إرجاع "موافق"

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    uid = str(message.get("from", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    إذا لم يكن chat_id أو لم يكن نصًا:
        إرجاع "موافق"

    إذا لم يكن OWNER_ID أو uid != OWNER_ID:
        send(chat_id, "⛔ هذا البوت خاص بصاحبه فقط.")
        إرجاع "موافق"

    إذا كان النص يساوي "/إلغاء":
        states.pop(uid, None)
        send(chat_id, "تم إلغاء العزل.")
        إرجاع "موافق"

    إذا كان النص موجودًا في ("/start", "/menu"):
        main_menu(chat_id)
        إرجاع "موافق"

    إذا كان النص يساوي "/status":
        حاول:
            db("GET", "products", {"select": "id", "limit": "1"})
            send(chat_id, "✅ البوت يعمل\n✅ Supabase متصل\n✅ حساب المالك محمي")
        باستثناء الاستثناء كـ e:
            send(chat_id, f"❌ مشكلة اتصال Supabase:\n{e}")
        إرجاع "موافق"

    إذا كان النص يساوي "/help":
        send(chat_id, "الأزرار المستعملة في القائمة الرئيسية.\n/إلغاء لإلغاء أي عملية.")
        إرجاع "موافق"

    s = states.get(uid, {})
    الخطوة = s.get("الخطوة", "")

    إذا كانت الخطوة تبدأ بـ "p_":
        add_product_step(chat_id, uid, text)
    elif step.startswith("edit_"):
        edit_step(chat_id, uid, text)
    elif step.startswith("c_"):
        add_customer_step(chat_id, uid, text)
    elif step == "sale_paid":
        حاول:
            تم الدفع = float(text.replace(",", "."))
            save_sale(chat_id, uid, paid)
        باستثناء ValueError:
            send(chat_id, "أدخل مبلغاً عادياً.")
    elif step == "sale_new_name":
        s["customer_name"] = "" if text == "-" else text
        s["step"] = "sale_new_phone"
        send(chat_id, "أرسل رقم الهاتف أو - بدون رقم.")
    elif step == "sale_new_phone":
        حاول:
            إذا كان s.get("customer_name"):
                new_customer = db("POST", "customers", body={
                    "الاسم": s["اسم_العميل"],
                    "phone": لا شيء إذا كان النص يساوي "-" وإلا نص
                })
                إذا كان العميل جديدًا:
                    s["customer_id"] = new_customer[0]["id"]
            s["step"] = "sale_paid"
            إرسال(
                chat_id,
                f"العلامة: {s['name']}\n"
                f"السعر: {fmt(s['price'])} دج\n"
                "أرسل رسالة الإيصال."
            )
        باستثناء الاستثناء كـ e:
            send(chat_id, f"❌ خطأ في تسجيل العميل: {e}")

    وإلا:
        send(chat_id, "اختر الطريقة من القائمة الرئيسية: /start")

    إرجاع "موافق"


# =====================================
# إعداد خطاف الويب
# =====================================

@app.route("/set-webhook")
def set_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    إذا لم يكن رمز البوت أو لم يكن عنوان URL للعرض:
        إرجاع "التكوين مفقود"، 500

    url = render_url.rstrip("/") + "/telegram-webhook"
    حاول:
        return requests.post(
            f"{TG}/setWebhook",
            json={"url": url},
            مهلة = 20
        ).text
    باستثناء الاستثناء كـ e:
        إرجاع str(e)، 500


إذا كان __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
