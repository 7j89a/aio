import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.enums import ChatAction, ParseMode
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# بيانات API و البوت
API_ID = 20944746
API_HASH = "d169162c1bcf092a6773e685c62c3894"
BOT_TOKEN = "7427094764:AAGEyokyZofIwvnm5Vzf0DXgb77JzNjoVo0"

GEMINI_API_KEY = "AIzaSyAOPduTp5DO_8MuPCbJnO0Dgl9G0O1CKn4"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_histories = {}

# سيرفر health check على port 8080
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def run_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server.serve_forever()

# safe edit function
async def safe_edit_message(msg, text):
    while True:
        try:
            await msg.edit_text(text)
            break
        except Exception as e:
            if "Too Many Requests" in str(e):
                wait_sec = 5
                if "seconds" in str(e):
                    try:
                        wait_sec = int(str(e).split("for ")[1].split(" second")[0])
                    except:
                        pass
                print(f"Rate limit! Waiting {wait_sec} seconds...")
                await asyncio.sleep(wait_sec + 1)
                continue
            else:
                print("Other error:", e)
                break

# /start command
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    start_text = (
        "✨ <b>مرحباً بك في بوت Gemini الذكي!</b> ✨\n\n"
        "🤖 هذا البوت يتيح لك الدردشة مع الذكاء الاصطناعي والإجابة على أي سؤال أو مساعدتك في أي مهمة!\n\n"
        "<b>طريقة الاستخدام:</b>\n"
        "• فقط أرسل سؤالك أو طلبك مباشرة للبوت وسيتم الرد عليك.\n\n"
        "<b>الأوامر المتاحة:</b>\n"
        "🔹 <code>/start</code> — عرض هذه الرسالة الترحيبية\n"
        "🔹 <code>/reset</code> — حذف سجل المحادثة الخاص بك والبدء من جديد\n"
        "🔹 <code>/clear</code> — أمر بديل لـ /reset لمسح المحادثة\n\n"
        "💡 <b>ملاحظات:</b>\n"
        "• كل محادثة لك محفوظة بشكل خاص لك\n"
        "• يمكنك البدء من جديد بأي وقت باستخدام /reset\n"
        "• البوت يدعم العربية والإنجليزية\n\n"
        "🧑‍💻 <i>تم تطوير هذا البوت باستخدام Gemini API وPyrogram</i>\n"
        "———\n"
        "📬 <b>ابدأ الآن وأرسل لي أي سؤال!</b>"
    )
    await message.reply_text(
        start_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

# /reset & /clear commands
@app.on_message(filters.command("reset") | filters.command("clear"))
async def reset_history(client, message):
    user_id = message.from_user.id
    user_histories[user_id] = []
    await message.reply_text("✅ <b>تم حذف سجل المحادثة الخاص بك بنجاح!</b>", parse_mode=ParseMode.HTML)

# رسائل المستخدم العادية
@app.on_message(filters.text & ~filters.command(["start", "reset", "clear"]))
async def handle_message(client, message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "text": user_text})
    max_history = 6
    history = user_histories[user_id][-max_history:]

    gemini_parts = [{"text": turn["text"]} for turn in history]
    payload = {
        "contents": [
            {"parts": gemini_parts}
        ]
    }
    headers = {"Content-Type": "application/json"}

    await app.send_chat_action(message.chat.id, ChatAction.TYPING)
    sent_msg = await message.reply_text("✍️ يكتب...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GEMINI_API_URL, headers=headers, json=payload, timeout=60) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if not data.get("candidates"):
            await safe_edit_message(sent_msg, "❌ لم يتم الحصول على رد من الذكاء الاصطناعي.")
            return

        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        user_histories[user_id].append({"role": "assistant", "text": reply})

        length = len(reply)
        if length < 100:
            sleep_time = 0.12
            step = 3
        elif length < 300:
            sleep_time = 1.5
            step = 40
        elif length < 700:
            sleep_time = 1.5
            step = 40
        else:
            sleep_time = 1.5
            step = 50

        text_buffer = ""
        for i, char in enumerate(reply):
            text_buffer += char
            if i % step == 0 or i == length - 1:
                await app.send_chat_action(message.chat.id, ChatAction.TYPING)
                await safe_edit_message(sent_msg, "💬 " + text_buffer + "▌")
                await asyncio.sleep(sleep_time)
        await safe_edit_message(sent_msg, "💬 " + text_buffer)
    except Exception as e:
        await safe_edit_message(sent_msg, f"❌ حدث خطأ: {e}")

# تشغيل البوت والسيرفر معًا
if __name__ == "__main__":
    print("البوت يعمل ...")
    threading.Thread(target=run_server, daemon=True).start()  # سيرفر healthcheck
    app.run()
