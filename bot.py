import os
import logging
import json
from datetime import datetime, timezone

import requests
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = str(os.environ.get("OWNER_TELEGRAM_ID", ""))
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Conversation states are kept in memory. If Render restarts, an unfinished
# conversation is cancelled, but saved database records remain safe.
states = {}
languages = {}


def tg(method, payload):
    r = requests.post(f"{TG}/{method}", json=payload, timeout=25)
    r.raise_for_status()
    result = r.json()
    if not result.get("ok"):
        raise Exception(result.get("description", "Telegram API error"))
    return result.get("result")


def send(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": str(text)}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    return tg("sendMessage", payload)


def callback_answer(callback_id, text=""):
    try:
        tg("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})
    except Exception:
        pass


def btn(label, data):
    return {"text": label, "callback_data": data}


def nav(back="menu"):
    return [[btn("⬅️ رجوع / Retour", back), btn("✖️ إلغاء / Annuler", "cancel")]]


def db(method, table, params=None, body=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("إعدادات Supabase غير موجودة على Render.")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    r = requests.request(
        method, f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers, params=params, json=body, timeout=30
    )
    if not r.ok:
        logging.error("Supabase %s: %s", table, r.text[:700])
        raise Exception(f"Supabase {r.status_code}: {r.text[:350]}")
    return r.json() if r.text else []


def fmt(value):
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "0"


def money(text):
    value = float(str(text).replace(",", ".").replace(" ", ""))
    if value < 0:
        raise ValueError()
    return value


def get_lang(uid):
    return languages.get(uid, "ar")


def tr(uid, ar, fr):
    return ar if get_lang(uid) == "ar" else fr


def main_menu(chat_id, uid):
    lang = get_lang(uid)
    if lang == "ar":
        text = "📺 Islam TV For You\n\nلوحة التسيير — اختر القسم:"
        keyboard = [
            [btn("📺 IPTV", "cat:IPTV"), btn("📡 أجهزة الاستقبال", "cat:RECEIVER")],
            [btn("🎬 الاشتراكات الرسمية", "cat:OFFICIAL")],
            [btn("🛒 عملية بيع جديدة", "sale_start")],
            [btn("📦 جميع المنتجات", "products")],
            [btn("➕ إضافة منتج", "add_start")],
            [btn("✏️ تعديل الأسعار", "edit_list"), btn("⛔ إيقاف منتج", "disable_list")],
            [btn("👥 الزبائن", "customers"), btn("➕ إضافة زبون", "customer_add")],
            [btn("💸 المصاريف", "expenses"), btn("➕ تسجيل مصروف", "expense_add")],
            [btn("🔄 Credits", "credits"), btn("📊 التقارير", "report")],
            [btn("🌐 Français", "language")],
        ]
    else:
        text = "📺 Islam TV For You\n\nTableau de gestion — choisissez une rubrique :"
        keyboard = [
            [btn("📺 IPTV", "cat:IPTV"), btn("📡 Récepteurs", "cat:RECEIVER")],
            [btn("🎬 Abonnements officiels", "cat:OFFICIAL")],
            [btn("🛒 Nouvelle vente", "sale_start")],
            [btn("📦 Tous les produits", "products")],
            [btn("➕ Ajouter un produit", "add_start")],
            [btn("✏️ Modifier les prix", "edit_list"), btn("⛔ Désactiver", "disable_list")],
            [btn("👥 Clients", "customers"), btn("➕ Ajouter client", "customer_add")],
            [btn("💸 Dépenses", "expenses"), btn("➕ Ajouter dépense", "expense_add")],
            [btn("🔄 Crédits", "credits"), btn("📊 Rapports", "report")],
            [btn("🌐 العربية", "language")],
        ]
    send(chat_id, text, keyboard)


def get_products(category=None, active=True):
    params = {
        "select": "id,name,category,purchase_price,selling_price,active,duration_prices,notes",
        "order": "name.asc",
        "limit": "500",
    }
    if active:
        params["active"] = "eq.true"
    if category:
        params["category"] = f"eq.{category}"
    return db("GET", "products", params)


def get_product(pid):
    rows = db("GET", "products", {"id": f"eq.{pid}", "select": "*", "limit": "1"})
    return rows[0] if rows else None


def get_customers():
    return db("GET", "customers", {
        "select": "id,name,phone,customer_type", "order": "name.asc", "limit": "100"
    })


def show_category(chat_id, uid, category):
    rows = get_products(category)
    names = {"IPTV": "اشتراكات IPTV", "RECEIVER": "أجهزة الاستقبال", "OFFICIAL": "الاشتراكات الرسمية"}
    fr_names = {"IPTV": "Abonnements IPTV", "RECEIVER": "Récepteurs", "OFFICIAL": "Abonnements officiels"}
    title = names.get(category, category) if get_lang(uid) == "ar" else fr_names.get(category, category)
    if not rows:
        send(chat_id, f"{title}\n\n{tr(uid, 'لا توجد منتجات في هذا القسم حالياً.', 'Aucun produit dans cette rubrique.')}",
             [[btn("➕ إضافة منتج", f"addcat:{category}")], *nav()])
        return
    lines = [f"📂 {title}\n"]
    for p in rows:
        lines.append(f"• {p['name']} — {fmt(p.get('selling_price'))} دج")
    keyboard = [[btn(tr(uid, "➕ إضافة منتج", "➕ Ajouter un produit"), f"addcat:{category}")],
                [btn(tr(uid, "🛒 بيع من هذا القسم", "🛒 Vendre dans cette rubrique"), f"salecat:{category}")]]
    keyboard += nav()
    send(chat_id, "\n".join(lines), keyboard)


def show_products(chat_id, uid):
    rows = get_products()
    if not rows:
        send(chat_id, tr(uid, "لا توجد منتجات مفعّلة.", "Aucun produit actif."), nav())
        return
    lines = ["📦 المنتجات المفعّلة:\n" if get_lang(uid) == "ar" else "📦 Produits actifs :\n"]
    for p in rows:
        category = p.get("category") or "غير مصنف"
        lines.append(f"• {p['name']} | {category}")
        prices = p.get("duration_prices") or {}
        if prices:
            for duration, price in sorted(prices.items(), key=lambda x: int(x[0])):
                lines.append(f"   {duration} شهر: شراء {fmt(price.get('purchase'))} / بيع {fmt(price.get('selling'))} دج")
        else:
            lines.append(f"   شراء {fmt(p.get('purchase_price'))} / بيع {fmt(p.get('selling_price'))} دج")
    send(chat_id, "\n".join(lines), nav())


def product_picker(chat_id, category, prefix):
    rows = get_products(category)
    if not rows:
        send(chat_id, "لا توجد منتجات مفعّلة في هذا القسم.", nav())
        return
    keyboard = [[btn(p["name"][:45], f"{prefix}:{p['id']}")] for p in rows[:40]]
    keyboard += nav()
    send(chat_id, "اختر المنتج:" if get_lang(str(chat_id)) == "ar" else "Choisissez le produit :", keyboard)


def start_add(chat_id, uid, category=None):
    if category not in ("IPTV", "RECEIVER", "OFFICIAL"):
        states[uid] = {"flow": "add", "step": "category"}
        send(chat_id, "اختر نوع المنتج:", [
            [btn("📺 IPTV", "addcat:IPTV"), btn("📡 جهاز استقبال", "addcat:RECEIVER")],
            [btn("🎬 اشتراك رسمي", "addcat:OFFICIAL")],
            *nav()
        ])
        return
    states[uid] = {"flow": "add", "step": "name", "category": category}
    send(chat_id, "أرسل اسم المنتج أو الاشتراك:", nav("menu"))


def add_step(chat_id, uid, text):
    s = states[uid]
    step = s["step"]
    if step == "name":
        s["name"] = text[:120]
        if s["category"] == "RECEIVER":
            s["step"] = "cost"
            send(chat_id, "أرسل سعر الشراء للجهاز بالدينار:", nav("menu"))
        else:
            s["duration_prices"] = {}
            s["duration_index"] = 0
            s["step"] = "duration_cost"
            ask_duration_cost(chat_id, s)
    elif step == "cost":
        s["cost"] = money(text)
        s["step"] = "sell"
        send(chat_id, "أرسل سعر البيع بالدينار:", nav("menu"))
    elif step == "sell":
        s["sell"] = money(text)
        s["step"] = "notes"
        send(chat_id, "أرسل ملاحظة أو - بدون ملاحظات:", nav("menu"))
    elif step == "notes":
        save_new_product(chat_id, uid, s, text)
    elif step == "duration_cost":
        duration = [1, 3, 6, 12][s["duration_index"]]
        if text.strip() == "-":
            s["duration_index"] += 1
            ask_duration_cost(chat_id, s)
            return
        s["pending_cost"] = money(text)
        s["step"] = "duration_sell"
        send(chat_id, f"أرسل سعر البيع لمدة {duration} شهر:", nav("menu"))
    elif step == "duration_sell":
        duration = [1, 3, 6, 12][s["duration_index"]]
        selling = money(text)
        s["duration_prices"][str(duration)] = {
            "purchase": s.pop("pending_cost"),
            "selling": selling,
        }
        s["duration_index"] += 1
        ask_duration_cost(chat_id, s)


def ask_duration_cost(chat_id, s):
    durations = [1, 3, 6, 12]
    if s["duration_index"] >= len(durations):
        if not s["duration_prices"]:
            send(chat_id, "يجب إدخال سعر مدة واحدة على الأقل. أعد إضافة المنتج.")
            return
        s["step"] = "notes"
        send(chat_id, "أرسل ملاحظة أو - بدون ملاحظات:", nav("menu"))
        return
    d = durations[s["duration_index"]]
    send(chat_id, f"مدة {d} شهر:\nأرسل سعر الشراء، أو - لتجاوز هذه المدة:", nav("menu"))


def save_new_product(chat_id, uid, s, notes):
    category = s["category"]
    if category == "RECEIVER":
        cost, selling = s["cost"], s["sell"]
        duration_prices = {}
    else:
        vals = list(s["duration_prices"].values())
        cost = vals[0]["purchase"]
        selling = vals[0]["selling"]
        duration_prices = s["duration_prices"]
    body = {
        "name": s["name"],
        "category": category,
        "purchase_price": cost,
        "selling_price": selling,
        "duration_prices": duration_prices,
        "notes": "" if notes == "-" else notes,
        "active": True,
    }
    try:
        db("POST", "products", body=body)
        send(chat_id, "✅ تمت إضافة المنتج بنجاح.", nav())
    except Exception as e:
        send(chat_id, f"❌ تعذرت الإضافة:\n{e}", nav())
    finally:
        states.pop(uid, None)


def start_edit(chat_id, uid, pid):
    p = get_product(pid)
    if not p or not p.get("active"):
        send(chat_id, "المنتج غير متاح.", nav())
        return
    category = p.get("category") or "RECEIVER"
    states[uid] = {"flow": "edit", "pid": pid, "category": category, "name": p["name"]}
    prices = p.get("duration_prices") or {}
    if category == "RECEIVER" or not prices:
        states[uid]["step"] = "edit_cost"
        send(chat_id, f"تعديل {p['name']}\nسعر الشراء الحالي: {fmt(p.get('purchase_price'))}\nأرسل سعر الشراء الجديد:", nav())
    else:
        keyboard = []
        for d in sorted(prices, key=lambda x: int(x)):
            keyboard.append([btn(f"{d} شهر", f"editdur:{pid}:{d}")])
        keyboard += nav()
        send(chat_id, f"اختر المدة التي تريد تعديل أسعارها — {p['name']}:", keyboard)


def edit_duration_start(chat_id, uid, pid, duration):
    p = get_product(pid)
    prices = (p or {}).get("duration_prices") or {}
    item = prices.get(duration)
    if not item:
        send(chat_id, "هذه المدة غير موجودة.", nav())
        return
    states[uid] = {
        "flow": "edit", "step": "edit_duration_cost", "pid": pid,
        "duration": duration, "prices": prices, "pending_cost": None
    }
    send(chat_id, f"السعر الحالي لمدة {duration} شهر:\nشراء: {fmt(item['purchase'])}\nبيع: {fmt(item['selling'])}\nأرسل سعر الشراء الجديد:", nav())


def edit_step(chat_id, uid, text):
    s = states[uid]
    try:
        value = money(text)
    except ValueError:
        send(chat_id, "أدخل مبلغاً صحيحاً موجباً أو صفراً.")
        return
    if s["step"] == "edit_cost":
        s["cost"] = value
        s["step"] = "edit_sell"
        send(chat_id, "أرسل سعر البيع الجديد:", nav())
    elif s["step"] == "edit_sell":
        try:
            db("PATCH", "products", {"id": f"eq.{s['pid']}"}, {
                "purchase_price": s["cost"], "selling_price": value
            })
            send(chat_id, "✅ تم تحديث الأسعار.", nav())
        except Exception as e:
            send(chat_id, f"❌ خطأ: {e}", nav())
        finally:
            states.pop(uid, None)
    elif s["step"] == "edit_duration_cost":
        s["pending_cost"] = value
        s["step"] = "edit_duration_sell"
        send(chat_id, "أرسل سعر البيع الجديد لهذه المدة:", nav())
    elif s["step"] == "edit_duration_sell":
        s["prices"][s["duration"]] = {"purchase": s["pending_cost"], "selling": value}
        try:
            vals = list(s["prices"].values())
            db("PATCH", "products", {"id": f"eq.{s['pid']}"}, {
                "duration_prices": s["prices"],
                "purchase_price": vals[0]["purchase"],
                "selling_price": vals[0]["selling"],
            })
            send(chat_id, "✅ تم تحديث أسعار المدة. المبيعات السابقة لن تتغير.", nav())
        except Exception as e:
            send(chat_id, f"❌ خطأ: {e}", nav())
        finally:
            states.pop(uid, None)


def customer_list(chat_id):
    rows = get_customers()
    if not rows:
        send(chat_id, "لا يوجد زبائن مسجلون.", nav())
        return
    lines = ["👥 الزبائن:\n"]
    for c in rows:
        lines.append(f"• {c['name']} | {c.get('phone') or '-'} | {c.get('customer_type')}")
    send(chat_id, "\n".join(lines), nav())


def start_customer_add(chat_id, uid):
    states[uid] = {"flow": "customer", "step": "name"}
    send(chat_id, "أرسل اسم الزبون:", nav())


def customer_step(chat_id, uid, text):
    s = states[uid]
    if s["step"] == "name":
        s["name"] = text[:120]
        s["step"] = "phone"
        send(chat_id, "أرسل رقم الهاتف أو - بدون رقم:", nav())
    elif s["step"] == "phone":
        s["phone"] = None if text == "-" else text
        s["step"] = "type"
        send(chat_id, "اختر نوع الزبون:", [
            [btn("زبون", "ctype:customer"), btn("موزع", "ctype:dealer")],
            [btn("موزع فرعي", "ctype:sub_dealer"), btn("بائع", "ctype:reseller")],
            *nav()
        ])


def save_customer_type(chat_id, uid, customer_type):
    s = states.get(uid)
    if not s:
        return
    try:
        db("POST", "customers", body={
            "name": s["name"], "phone": s.get("phone"),
            "customer_type": customer_type
        })
        send(chat_id, "✅ تمت إضافة الزبون.", nav())
    except Exception as e:
        send(chat_id, f"❌ تعذرت إضافة الزبون: {e}", nav())
    finally:
        states.pop(uid, None)


def start_sale(chat_id, uid, category=None):
    if category:
        sale_product_picker(chat_id, uid, category)
    else:
        send(chat_id, "اختر القسم الذي تريد البيع منه:", [
            [btn("📺 IPTV", "salecat:IPTV"), btn("📡 أجهزة الاستقبال", "salecat:RECEIVER")],
            [btn("🎬 الاشتراكات الرسمية", "salecat:OFFICIAL")],
            *nav()
        ])


def sale_product_picker(chat_id, uid, category):
    rows = get_products(category)
    if not rows:
        send(chat_id, "لا توجد منتجات مفعّلة في هذا القسم.", nav())
        return
    keyboard = [[btn(p["name"][:45], f"saleprod:{p['id']}")] for p in rows[:40]]
    keyboard += nav()
    send(chat_id, "اختر المنتج أو الاشتراك:", keyboard)


def select_sale_product(chat_id, uid, pid):
    p = get_product(pid)
    if not p or not p.get("active"):
        send(chat_id, "المنتج غير متاح.", nav())
        return
    prices = p.get("duration_prices") or {}
    if prices:
        states[uid] = {"flow": "sale", "step": "duration", "pid": pid, "name": p["name"],
                       "category": p.get("category"), "prices": prices}
        keyboard = [[btn(f"{d} شهر", f"saledur:{d}")] for d in sorted(prices, key=lambda x: int(x))]
        keyboard += nav()
        send(chat_id, f"اختر مدة {p['name']}:", keyboard)
    else:
        states[uid] = {"flow": "sale", "step": "quantity", "pid": pid,
                       "name": p["name"], "category": p.get("category"),
                       "cost": float(p["purchase_price"]), "price": float(p["selling_price"]),
                       "duration": None}
        send(chat_id, f"المنتج: {p['name']}\nالشراء: {fmt(p['purchase_price'])} دج\nالبيع: {fmt(p['selling_price'])} دج\nأرسل الكمية:", nav())


def select_sale_duration(chat_id, uid, duration):
    s = states.get(uid)
    if not s:
        send(chat_id, "انتهت العملية. ابدأ من جديد.", nav())
        return
    item = s["prices"].get(duration)
    if not item:
        send(chat_id, "المدة غير متاحة.", nav())
        return
    s["duration"] = int(duration)
    s["cost"] = float(item["purchase"])
    s["price"] = float(item["selling"])
    s["step"] = "quantity"
    send(chat_id, f"المنتج: {s['name']}\nالمدة: {duration} شهر\nسعر الشراء: {fmt(s['cost'])} دج\nسعر البيع: {fmt(s['price'])} دج\nأرسل الكمية:", nav())


def sale_quantity(chat_id, uid, text):
    s = states[uid]
    try:
        q = float(str(text).replace(",", "."))
        if q <= 0:
            raise ValueError()
    except ValueError:
        send(chat_id, "أدخل كمية صحيحة أكبر من صفر.")
        return
    s["quantity"] = q
    s["step"] = "customer"
    rows = get_customers()
    keyboard = [[btn(c["name"][:40], f"salecustomer:{c['id']}")] for c in rows[:35]]
    keyboard.append([btn("👤 بيع بدون تسجيل زبون", "sale_nocustomer")])
    keyboard += nav()
    send(chat_id, "اختر الزبون:", keyboard)


def choose_sale_customer(chat_id, uid, cid):
    rows = db("GET", "customers", {"id": f"eq.{cid}", "select": "id,name", "limit": "1"})
    if not rows:
        send(chat_id, "الزبون غير موجود.", nav())
        return
    s = states.get(uid)
    if not s:
        return
    s["customer_id"] = rows[0]["id"]
    s["customer_name"] = rows[0]["name"]
    ask_paid(chat_id, s)


def sale_no_customer(chat_id, uid):
    s = states.get(uid)
    if s:
        s["customer_id"] = None
        s["customer_name"] = "غير مسجل"
        ask_paid(chat_id, s)


def ask_paid(chat_id, s):
    total = s["price"] * s["quantity"]
    s["total"] = total
    s["step"] = "paid"
    send(chat_id, f"الزبون: {s.get('customer_name', 'غير مسجل')}\n"
                  f"الإجمالي: {fmt(total)} دج\n"
                  f"التكلفة: {fmt(s['cost'] * s['quantity'])} دج\n"
                  f"الربح المتوقع: {fmt((s['price'] - s['cost']) * s['quantity'])} دج\n\n"
                  "أرسل المبلغ المدفوع:", nav())


def save_sale(chat_id, uid, text):
    s = states.get(uid)
    try:
        paid = money(text)
    except ValueError:
        send(chat_id, "أدخل مبلغاً صحيحاً.")
        return
    total = s["total"]
    if paid > total:
        send(chat_id, f"المبلغ أكبر من الإجمالي ({fmt(total)} دج). أعد الإدخال.")
        return
    quantity = s["quantity"]
    cost = s["cost"]
    price = s["price"]
    profit = (price - cost) * quantity
    notes = f"العميل: {s.get('customer_name', 'غير مسجل')}; المتبقي: {fmt(total-paid)} دج"
    if s.get("duration"):
        notes += f"; المدة: {s['duration']} شهر"
    body = {
        "customer_id": s.get("customer_id"),
        "product_id": s["pid"],
        "product_name": s["name"],
        "quantity": quantity,
        "purchase_unit_cost": cost,
        "selling_unit_price": price,
        "paid_amount": paid,
        "profit": profit,
        "notes": notes,
        "duration_months": s.get("duration"),
        "product_category": s.get("category"),
    }
    try:
        # total_amount and total_cost are GENERATED ALWAYS columns; do not send them.
        db("POST", "sales", body=body)
        send(chat_id, "✅ تم تسجيل البيع بنجاح!\n\n"
                      f"المنتج: {s['name']}\n"
                      f"المدة: {str(s.get('duration')) + ' شهر' if s.get('duration') else 'غير محددة'}\n"
                      f"الكمية: {fmt(quantity)}\n"
                      f"الإجمالي: {fmt(total)} دج\n"
                      f"التكلفة: {fmt(cost*quantity)} دج\n"
                      f"الربح: {fmt(profit)} دج\n"
                      f"المدفوع: {fmt(paid)} دج\n"
                      f"المتبقي: {fmt(total-paid)} دج", nav())
    except Exception as e:
        send(chat_id, f"❌ لم يتم حفظ البيع:\n{e}", nav())
    finally:
        states.pop(uid, None)


def start_expense(chat_id, uid):
    states[uid] = {"flow": "expense", "step": "title"}
    send(chat_id, "أرسل عنوان المصروف:", nav())


def expense_step(chat_id, uid, text):
    s = states[uid]
    if s["step"] == "title":
        s["title"] = text
        s["step"] = "amount"
        send(chat_id, "أرسل مبلغ المصروف بالدينار:", nav())
    else:
        try:
            amount = money(text)
            db("POST", "expenses", body={"title": s["title"], "amount": amount,
                                         "expense_date": datetime.now(timezone.utc).isoformat()})
            send(chat_id, f"✅ تم تسجيل المصروف: {fmt(amount)} دج", nav())
        except ValueError:
            send(chat_id, "أدخل مبلغاً صحيحاً.")
            return
        except Exception as e:
            send(chat_id, f"❌ خطأ: {e}", nav())
        finally:
            states.pop(uid, None)


def show_expenses(chat_id):
    rows = db("GET", "expenses", {"select": "title,amount,expense_date", "order": "expense_date.desc", "limit": "50"})
    total = sum(float(x["amount"]) for x in rows)
    lines = [f"💸 المصاريف الأخيرة: {len(rows)} عملية", f"الإجمالي: {fmt(total)} دج\n"]
    for x in rows[:20]:
        lines.append(f"• {x['title']} — {fmt(x['amount'])} دج")
    send(chat_id, "\n".join(lines), nav())


def show_credits(chat_id):
    rows = db("GET", "credits_movements", {
        "select": "provider,movement_type,credits,unit_cost,notes,created_at",
        "order": "created_at.desc", "limit": "100"
    })
    balances = {}
    for x in rows:
        provider = x["provider"]
        item = balances.setdefault(provider, {"in": 0.0, "out": 0.0})
        typ = str(x["movement_type"]).lower()
        if typ in ("purchase", "in", "buy", "add", "شراء", "دخول"):
            item["in"] += float(x["credits"])
        else:
            item["out"] += float(x["credits"])
    lines = ["🔄 ملخص Credits:"]
    if not balances:
        lines.append("لا توجد حركات مسجلة.")
    for provider, v in balances.items():
        lines.append(f"• {provider}: مشتريات {fmt(v['in'])} | مبيعات/خروج {fmt(v['out'])} | الرصيد {fmt(v['in']-v['out'])}")
    send(chat_id, "\n".join(lines), nav())


def sales_report(chat_id):
    rows = db("GET", "sales", {
        "select": "total_amount,total_cost,paid_amount,profit", "limit": "5000"
    })
    expenses = db("GET", "expenses", {"select": "amount", "limit": "5000"})
    total_sales = sum(float(x.get("total_amount") or 0) for x in rows)
    total_cost = sum(float(x.get("total_cost") or 0) for x in rows)
    total_paid = sum(float(x.get("paid_amount") or 0) for x in rows)
    profit = sum(float(x.get("profit") or 0) for x in rows)
    expense_total = sum(float(x.get("amount") or 0) for x in expenses)
    send(chat_id, "📊 تقرير شامل\n\n"
                  f"عدد عمليات البيع: {len(rows)}\n"
                  f"إجمالي المبيعات: {fmt(total_sales)} دج\n"
                  f"تكلفة المنتجات: {fmt(total_cost)} دج\n"
                  f"المبالغ المحصلة: {fmt(total_paid)} دج\n"
                  f"الربح الإجمالي: {fmt(profit)} دج\n"
                  f"إجمالي المصاريف المسجلة: {fmt(expense_total)} دج\n"
                  f"صافي الربح التقديري: {fmt(profit-expense_total)} دج", nav())


def handle_callback(callback):
    user = callback.get("from", {})
    uid = str(user.get("id", ""))
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    action = callback.get("data", "")
    callback_answer(callback.get("id", ""))
    if not OWNER_ID or uid != OWNER_ID:
        return
    try:
        if action == "menu":
            states.pop(uid, None)
            main_menu(chat_id, uid)
        elif action == "cancel":
            states.pop(uid, None)
            send(chat_id, "تم إلغاء العملية.", nav())
        elif action == "language":
            languages[uid] = "fr" if get_lang(uid) == "ar" else "ar"
            main_menu(chat_id, uid)
        elif action.startswith("cat:"):
            show_category(chat_id, uid, action.split(":", 1)[1])
        elif action == "products":
            show_products(chat_id, uid)
        elif action == "add_start":
            start_add(chat_id, uid)
        elif action.startswith("addcat:"):
            start_add(chat_id, uid, action.split(":", 1)[1])
        elif action == "edit_list":
            rows = get_products()
            keyboard = [[btn(p["name"][:45], f"edit:{p['id']}")] for p in rows[:40]] + nav()
            send(chat_id, "اختر المنتج لتعديل أسعاره:", keyboard)
        elif action.startswith("edit:"):
            start_edit(chat_id, uid, action.split(":", 1)[1])
        elif action.startswith("editdur:"):
            _, pid, duration = action.split(":")
            edit_duration_start(chat_id, uid, pid, duration)
        elif action == "disable_list":
            rows = get_products()
            keyboard = [[btn(p["name"][:45], f"disable:{p['id']}")] for p in rows[:40]] + nav()
            send(chat_id, "اختر المنتج لإيقافه:", keyboard)
        elif action.startswith("disable:"):
            pid = action.split(":", 1)[1]
            db("PATCH", "products", {"id": f"eq.{pid}"}, {"active": False})
            send(chat_id, "✅ تم إيقاف المنتج دون حذف سجله.", nav())
        elif action == "customer_add":
            start_customer_add(chat_id, uid)
        elif action == "customers":
            customer_list(chat_id)
        elif action.startswith("ctype:"):
            save_customer_type(chat_id, uid, action.split(":", 1)[1])
        elif action == "sale_start":
            start_sale(chat_id, uid)
        elif action.startswith("salecat:"):
            sale_product_picker(chat_id, uid, action.split(":", 1)[1])
        elif action.startswith("saleprod:"):
            select_sale_product(chat_id, uid, action.split(":", 1)[1])
        elif action.startswith("saledur:"):
            select_sale_duration(chat_id, uid, action.split(":", 1)[1])
        elif action.startswith("salecustomer:"):
            choose_sale_customer(chat_id, uid, action.split(":", 1)[1])
        elif action == "sale_nocustomer":
            sale_no_customer(chat_id, uid)
        elif action == "expense_add":
            start_expense(chat_id, uid)
        elif action == "expenses":
            show_expenses(chat_id)
        elif action == "credits":
            show_credits(chat_id)
        elif action == "report":
            sales_report(chat_id)
    except Exception as e:
        logging.exception("Callback failed")
        send(chat_id, f"❌ حدث خطأ:\n{e}", nav())


@app.route("/")
def home():
    return "Islam TV For You Bot is running!"


@app.route("/telegram-webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    callback = data.get("callback_query")
    if callback:
        handle_callback(callback)
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

    if text in ("/cancel", "/annuler"):
        states.pop(uid, None)
        send(chat_id, "تم إلغاء العملية.", nav())
        return "OK"
    if text in ("/start", "/menu"):
        main_menu(chat_id, uid)
        return "OK"
    if text == "/status":
        try:
            db("GET", "products", {"select": "id", "limit": "1"})
            send(chat_id, "✅ البوت يعمل\n✅ Supabase متصل\n✅ حماية المالك مفعّلة")
        except Exception as e:
            send(chat_id, f"❌ مشكلة اتصال Supabase:\n{e}")
        return "OK"
    if text == "/help":
        send(chat_id, "استعمل أزرار القائمة. /cancel لإلغاء أي عملية.")
        return "OK"

    s = states.get(uid, {})
    step = s.get("step", "")
    try:
        if s.get("flow") == "add":
            add_step(chat_id, uid, text)
        elif s.get("flow") == "edit":
            edit_step(chat_id, uid, text)
        elif s.get("flow") == "customer":
            customer_step(chat_id, uid, text)
        elif s.get("flow") == "sale" and step == "quantity":
            sale_quantity(chat_id, uid, text)
        elif s.get("flow") == "sale" and step == "paid":
            save_sale(chat_id, uid, text)
        elif s.get("flow") == "expense":
            expense_step(chat_id, uid, text)
        else:
            send(chat_id, "اختر عملية من القائمة الرئيسية: /start")
    except ValueError:
        send(chat_id, "أدخل قيمة صحيحة.")
    except Exception as e:
        logging.exception("Message handler failed")
        send(chat_id, f"❌ حدث خطأ:\n{e}")
    return "OK"


@app.route("/set-webhook")
def set_webhook():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not BOT_TOKEN or not render_url:
        return "Missing configuration", 500
    url = render_url.rstrip("/") + "/telegram-webhook"
    try:
        return requests.post(f"{TG}/setWebhook", json={"url": url}, timeout=20).text
    except Exception as e:
        return str(e), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
