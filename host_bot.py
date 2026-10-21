import os
import time
import json
import subprocess
import telebot

# ================= কনফিগারেশন =================
BOT_TOKEN = "8706468056:AAGOK5S0RE4npvHoHfz75hqVDBX9iT_hAm0"
ADMIN_USERNAME = "NahidAhmed_2"  # এডমিন ইউজারনেম
MAX_BOT_LIMIT = 12               # সর্বোচ্চ ১২টি সাব-বট
TRIAL_PERIOD_SECONDS = 2 * 24 * 60 * 60  # ২ দিনের ফ্রি ট্রায়াল
# ===============================================

bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "database.json"
BASE_DIR = "user_bots"
os.makedirs(BASE_DIR, exist_ok=True)

running_processes = {}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"admin_id": None, "users": {}, "banned": []}
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except Exception:
            return {"admin_id": None, "users": {}, "banned": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ক্ষতিকর কোড বা ভাইরাস প্রতিরোধক ফিল্টার
DANGEROUS_PATTERNS = [
    "os.system", "shutil.rmtree", "subprocess.call", "subprocess.Popen(['rm'", 
    "subprocess.Popen(['termux", "eval(", "exec(", "__import__", 
    "/data/data/com.termux", "storage/shared", "rm -rf", "open('/etc"
]

def scan_file_for_virus(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            for pattern in DANGEROUS_PATTERNS:
                if pattern.lower() in content.lower():
                    return True, pattern
    except Exception:
        return True, "ফাইল রিড এরর"
    return False, None

def ban_user(user_id, reason="Malicious Activity"):
    db = load_data()
    if user_id not in db["banned"]:
        db["banned"].append(user_id)
        save_data(db)
    kill_user_bot(user_id)
    try:
        bot.send_message(user_id, "🚨 নিরাপত্তা সতর্কতা!\nআপনার ফাইলে ভাইরাস বা ক্ষতিকর স্ক্রিপ্ট থাকায় পার্মানেন্ট ব্যান করা হয়েছে।")
        if db.get("admin_id"):
            bot.send_message(db["admin_id"], f"⚠️ ইউজার ব্যান করা হয়েছে!\nUser ID: {user_id}\nকারণ: {reason}")
    except Exception:
        pass

def kill_user_bot(user_id):
    uid_str = str(user_id)
    proc = running_processes.get(uid_str)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        del running_processes[uid_str]

# ================= কমান্ড হ্যান্ডলারস =================

@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    uname = message.from_user.username or ""
    db = load_data()

    if uname.lower() == ADMIN_USERNAME.lower():
        if db.get("admin_id") != uid:
            db["admin_id"] = uid
            save_data(db)

    if uid in db.get("banned", []):
        bot.reply_to(message, "❌ আপনি এই সার্ভার থেকে ব্যান আছেন।")
        return

    text = (
        "🚀 স্বাগতম ফাইল হোস্টিং বটে!\n\n"
        "আপনার তৈরি করা নিজস্ব টেলিগ্রাম বট ফাইল (.py) এখানে হোস্ট করতে পারেন।\n"
        "🎁 প্রথমবার পাবেন ২ দিনের ফ্রি ট্রায়াল!\n\n"
        "📌 ব্যবহারের নিয়ম:\n"
        "১. আপনার তৈরি করা বট ফাইলটি (.py) এখানে ডকুমেন্ট আকারে সেন্ড করুন।\n"
        "২. এডমিন অনুমোদন দিলে বট স্বয়ংক্রিয়ভাবে চালু হয়ে যাবে।\n\n"
        "🛠 অন্যান্য কমান্ড:\n"
        "• /status - আপনার বটের লাইভ অবস্থা দেখতে\n"
        "• /stop - বট বন্ধ করতে\n\n"
        f"📞 এডমিন যোগাযোগ: @{ADMIN_USERNAME}"
    )
    bot.reply_to(message, text)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    uid = str(message.from_user.id)
    db = load_data()

    if int(uid) in db.get("banned", []):
        return

    file_name = message.document.file_name
    if not file_name.endswith('.py'):
        bot.reply_to(message, "⚠️ শুধুমাত্র পাইথন ফাইল (.py) আপলোড করা যাবে!")
        return

    user_dir = os.path.join(BASE_DIR, uid)
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, "bot.py")

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    is_bad, pattern = scan_file_for_virus(file_path)
    if is_bad:
        os.remove(file_path)
        ban_user(int(uid), f"ক্ষতিকর কোড পাওয়া গেছে: {pattern}")
        return

    if uid in db.get("users", {}) and db["users"][uid].get("status") == "approved":
        if time.time() > db["users"][uid].get("expiry_time", 0):
            bot.reply_to(message, f"⏳ আপনার ফ্রি ট্রায়াল শেষ! এডমিনের সাথে যোগাযোগ করুন: @{ADMIN_USERNAME}")
            return
        run_user_script(message, uid, file_path)
    else:
        admin_id = db.get("admin_id")
        if admin_id:
            bot.send_message(
                admin_id,
                f"🔔 নতুন বট ফাইল আপলোড হয়েছে!\n"
                f"👤 ইউজার: @{message.from_user.username or 'No Username'}\n"
                f"🆔 ID: {uid}\n\n"
                f"অনুমোদন দিয়ে রান করতে পাঠান:\n/approve {uid}"
            )
            bot.reply_to(message, "✅ ফাইল আপলোড সফল হয়েছে। এডমিন অনুমোদন দিলেই আপনার বট চালু হবে।")
        else:
            bot.reply_to(message, "⚠️ এডমিন এখনো অফলাইন। অপেক্ষা করুন।")

def run_user_script(message, uid, file_path):
    active_count = sum(1 for p in running_processes.values() if p.poll() is None)
    if active_count >= MAX_BOT_LIMIT:
        bot.reply_to(message, "⚠️ সার্ভার ফুল! একসাথে ১২টির বেশি বট চলা সম্ভব নয়।")
        return

    kill_user_bot(uid)

    proc = subprocess.Popen(["python", file_path])
    running_processes[uid] = proc

    db = load_data()
    rem_hours = int((db["users"][uid]["expiry_time"] - time.time()) / 3600)
    bot.reply_to(
        message,
        f"✅ আপনার বট সফলভাবে চালু হয়েছে!\n"
        f"📌 Process ID (PID): {proc.pid}\n"
        f"⏳ ফ্রি ট্রায়াল বাকি: {rem_hours} ঘণ্টা"
    )

@bot.message_handler(commands=['approve'])
def handle_approve(message):
    db = load_data()
    admin_id = db.get("admin_id")

    if not admin_id or message.from_user.id != admin_id:
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ ব্যবহার: /approve <user_id>")
        return

    target_id = args[1].strip()
    file_path = os.path.join(BASE_DIR, target_id, "bot.py")

    if not os.path.exists(file_path):
        bot.reply_to(message, "⚠️ এই ইউজারের কোনো আপলোড করা ফাইল পাওয়া যায়নি।")
        return

    curr_t = time.time()
    db["users"][target_id] = {
        "status": "approved",
        "start_time": curr_t,
        "expiry_time": curr_t + TRIAL_PERIOD_SECONDS
    }
    save_data(db)

    proc = subprocess.Popen(["python", file_path])
    running_processes[target_id] = proc

    bot.reply_to(message, f"✅ ইউজার {target_id}-এর ফাইল অনুমোদন ও ব্যাকগ্রাউন্ডে চালু করা হয়েছে।")
    try:
        bot.send_message(
            int(target_id),
            "🎉 আপনার ফাইলটি এডমিন অনুমোদন করেছেন এবং বটটি চালু হয়েছে!\n"
            "⏳ আগামী ২ দিন সম্পূর্ণ ফ্রিতে চলবে।"
        )
    except Exception:
        pass

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    uid = str(message.from_user.id)
    if uid in running_processes and running_processes[uid].poll() is None:
        kill_user_bot(uid)
        bot.reply_to(message, "🛑 আপনার বটটি বন্ধ করা হয়েছে।")
    else:
        bot.reply_to(message, "⚠️ আপনার কোনো বট বর্তমানে সক্রিয় নেই।")

@bot.message_handler(commands=['status'])
def handle_status(message):
    uid = str(message.from_user.id)
    db = load_data()

    if uid in running_processes and running_processes[uid].poll() is None:
        rem_sec = db["users"].get(uid, {}).get("expiry_time", 0) - time.time()
        rem_hrs = max(0, int(rem_sec / 3600))
        bot.reply_to(message, f"🟢 আপনার বট সচল রয়েছে!\n⏳ ফ্রি ট্রায়াল বাকি: {rem_hrs} ঘণ্টা")
    else:
        bot.reply_to(message, "🔴 বর্তমানে কোনো বট সক্রিয় নেই।")

bot.infinity_polling()
