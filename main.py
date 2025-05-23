import telebot
import threading
import requests
import json
import os
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = '8155271835:AAHoCTwDe5laiIRFiQerj7EKRygg1JHDOkA'
DATA_FILE = 'djezzy_data.json'

bot = telebot.TeleBot(TOKEN)

def load_user_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            os.remove(DATA_FILE)
    return {}

def save_user_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def hide_phone_number(phone):
    return phone[:4] + '*******' + phone[-2:]

def send_otp(msisdn):
    url = 'https://apim.djezzy.dz/oauth2/registration'
    payload = f'msisdn={msisdn}&client_id=6E6CwTkp8H1CyQxraPmcEJPQ7xka&scope=smsotp'
    headers = {
        'User-Agent': 'Djezzy/2.6.7',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        res = requests.post(url, data=payload, headers=headers, verify=False)
        return res.status_code == 200 or "confirmation code" in res.text.lower()
    except:
        return False

def verify_otp(msisdn, otp):
    url = 'https://apim.djezzy.dz/oauth2/token'
    payload = f'otp={otp}&mobileNumber={msisdn}&scope=openid&client_id=6E6CwTkp8H1CyQxraPmcEJPQ7xka&client_secret=MVpXHW_ImuMsxKIwrJpoVVMHjRsa&grant_type=mobile'
    headers = {
        'User-Agent': 'Djezzy/2.6.7',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        res = requests.post(url, data=payload, headers=headers, verify=False)
        return res.json() if res.status_code == 200 else None
    except:
        return None

def apply_gift(bot, chat_id, msisdn, token, username, name):
    user_data = load_user_data()
    last = user_data.get(str(chat_id), {}).get('last_applied')
    if last and datetime.now() - datetime.fromisoformat(last) < timedelta(days=1):
        bot.send_message(chat_id, "⏳ انتظر 24 ساعة قبل طلب جديد.")
        return
    url = f'https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/{msisdn}/subscription-product?include='
    payload = {
        "data": {
            "id": "TransferInternet2Go",
            "type": "products",
            "meta": {
                "services": {
                    "steps": 10000,
                    "code": "FAMILY4000",
                    "id": "WALKWIN"
                }
            }
        }
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Djezzy/2.6.7'
    }
    try:
        r = requests.post(url, json=payload, headers=headers, verify=False)
        data = r.json()
        if "successfully done" in str(data.get("message", "")):
            msg = f"✅ تم منحك الهدية!\n👤 {name}\n🔷 @{username}\n📞 {hide_phone_number(msisdn)}"
            bot.send_message(chat_id, msg)
            user_data[str(chat_id)]['last_applied'] = datetime.now().isoformat()
            save_user_data(user_data)
        else:
            bot.send_message(chat_id, f"⚠️ خطأ: {data.get('message', 'غير معروف')}")
    except:
        bot.send_message(chat_id, "⚠️ حدث خطأ أثناء تنفيذ العملية.")

@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    bot.send_message(chat_id, "مرحباً بك في بوت هدايا Djezzy! أرسل رقمك (يبدأ بـ 07):")

@bot.message_handler(func=lambda message: True)
def handle_phone(msg):
    chat_id = msg.chat.id
    text = msg.text.strip()
    if not (text.startswith("07") and len(text) == 10 and text.isdigit()):
        bot.send_message(chat_id, "❌ رقم غير صحيح. حاول مرة أخرى.")
        return
    msisdn = '213' + text[1:]
    data = load_user_data()

    # البحث عن الرقم في قاعدة البيانات
    existing_user = None
    for user_id, user_info in data.items():
        if user_info.get('msisdn') == msisdn:
            existing_user = user_info
            break

    if existing_user:
        # رقم موجود مسبقاً
        data[str(chat_id)] = {
            'msisdn': msisdn,
            'username': msg.from_user.username or 'غير معروف',
            'access_token': existing_user['access_token'],
            'refresh_token': existing_user['refresh_token'],
            'last_applied': existing_user.get('last_applied')
        }
        save_user_data(data)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("🎁 خذ الهدية", callback_data='walkwingift'))
        bot.send_message(chat_id, "✅ مرحباً من جديد! اضغط لأخذ الهدية:", reply_markup=markup)
    else:
        # رقم جديد، إرسال OTP
        if send_otp(msisdn):
            bot.send_message(chat_id, "✅ أرسل الرمز اللي وصلك:")
            bot.register_next_step_handler_by_chat_id(chat_id, lambda m: handle_otp(m, msisdn))
        else:
            bot.send_message(chat_id, "⚠️ فشل في إرسال OTP.")

def handle_otp(msg, msisdn):
    chat_id = msg.chat.id
    otp = msg.text.strip()
    if len(otp) != 6 or not otp.isdigit():
        bot.send_message(chat_id, "❌ الرمز غير صالح.")
        return
    tokens = verify_otp(msisdn, otp)
    if tokens:
        data = load_user_data()
        data[str(chat_id)] = {
            'msisdn': msisdn,
            'username': msg.from_user.username or 'غير معروف',
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'last_applied': None
        }
        save_user_data(data)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("🎁 خذ الهدية", callback_data='walkwingift'))
        bot.send_message(chat_id, "✅ تم التحقق! اضغط لأخذ الهدية:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "❌ رمز خاطئ أو منتهي.")

@bot.callback_query_handler(func=lambda call: call.data == 'walkwingift')
def gift(call):
    chat_id = call.message.chat.id
    data = load_user_data()
    if str(chat_id) in data:
        u = data[str(chat_id)]
        apply_gift(bot, chat_id, u['msisdn'], u['access_token'], u['username'], call.from_user.first_name or "مستخدم")
    else:
        bot.send_message(chat_id, "❌ لم نجد بياناتك. استعمل /start من جديد.")

def run_bot():
    print("🤖 البوت شغال...")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    run_bot()
