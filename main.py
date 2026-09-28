import asyncio
import os
import threading
from pyrogram import Client, filters, idle
from flask import Flask

api_id = 25956262
api_hash = "8e6268505a15d74f195672b802e34aa9"

app = Client("my_account_2", api_id=api_id, api_hash=api_hash)
web_app = Flask(__name__)

# ضع رابط كروب التخزين الخاص بك هنا ⬇️
STORAGE_GROUP_LINK = "ضع_رابط_كروبك_هنا"
STORAGE_GROUP_ID = None
STALE_PEER_ID = "-1002409275358"
FORWARD_LOCK = asyncio.Lock()

COMMANDS_TEXT = """✦ ─── ✦『 قائـمـة الاوامـر 』✦ ─── ✦

. م 1 ➾ اوامر الحساب
. م 2 ➾ اوامر الخاص
. م 3 ➾ اوامر الاسبام
. م 4 ➾ اوامر الاذاعه
. م 5 ➾ اوامر التحميل
. م 6 ➾ امر الحذف
. م 7 ➾ اوامر الزخرفه
. م 8 ➾ اوامر التسطير
. م 9 ➾ اوامر الساعه
. م 10 ➾ اوامر التفليش
. م 11 ➾ اوامر الترجمه
. م 12 ➾ اوامر الوهمي
. م 13 ➾ اوامر الانتحال
. م 14 ➾ اوامر النشر
. م 15 ➾ اوامر الذكاء الاصطناعي"""

@web_app.get("/")
def health_check():
    return {"service": "TelegramSource", "status": "ok"}

def run_web_server():
    port = int(os.environ.get("PORT", "5000"))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

@app.on_message(filters.me & filters.regex(r"^(\.|)الاوامر$"))
async def show_help_menu(client, message):
    try:
        await message.edit_text(COMMANDS_TEXT)
    except Exception as error:
        report_error(error)

def is_stale_peer_error(error):
    if error is None:
        return False
    error_text = str(error)
    return STALE_PEER_ID in error_text and ("Peer id invalid" in error_text or "ID not found" in error_text)

def report_error(error):
    if not is_stale_peer_error(error):
        print(f"خطأ: {error}")

async def resolve_storage_group(client):
    global STORAGE_GROUP_ID
    try:
        group = await client.get_chat(STORAGE_GROUP_LINK)
        STORAGE_GROUP_ID = getattr(group, "id", None) or getattr(getattr(group, "chat", None), "id", None)
        return STORAGE_GROUP_ID
    except Exception as error:
        if not is_stale_peer_error(error):
            raise
        return None

@app.on_message(filters.me & filters.regex(r"^(\.|)تخزين$"))
async def show_storage_group(client, message):
    try:
        msg = await message.edit_text("جاري الوصول إلى كروب التخزين الجديد...")
        await resolve_storage_group(client)
        await msg.edit_text(f"تم الوصول إلى كروب التخزين بنجاح!\nآيدي الكروب: `{STORAGE_GROUP_ID}`")
    except Exception as error:
        report_error(error)

# دالة مخصصة لترتيب ونقل رسائل الخاص (الواردة والصادرة) إلى كروب التخزين
@app.on_message(filters.all & filters.private & ~filters.bot)
async def forward_to_storage(client, message):
    try:
        async with FORWARD_LOCK:
            storage_group_id = STORAGE_GROUP_ID or await resolve_storage_group(client)
            if storage_group_id is None:
                return

            # تحديد ما إذا كانت الرسالة واردة من الشخص أو صادرة منك
            direction = "صادرة منك 📤" if message.outgoing else "واردة إليك 📥"
            sender_name = message.from_user.first_name if message.from_user else "شخص مخفي"
            sender_username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else "لا يوجد"
            chat_title = message.chat.first_name or "محادثة خاصة"

            # إرسال معلومات مرتبة مع الرسالة
            header_text = (
                f"💬 **رسالة جديدة في الخاص**\n"
                f"👤 المرسل/المستلم: [{chat_title}](tg://user?id={message.chat.id})\n"
                f"🏷️ الحالة: {direction}\n"
                f"🆔 الآيدي: `{message.chat.id}`"
            )

            # إرسال الترويسة أولاً ثم نسخ الرسالة الأصلية لضمان الترتيب والشكل الأنيق
            await client.send_message(storage_group_id, header_text)
            await message.copy(storage_group_id)

            timestamp = message.date.isoformat() if message.date else "unknown-time"
            print(f"[{timestamp}] Private message handled (chat_id={message.chat.id}, direction={direction})")
    except Exception as error:
        report_error(error)

def install_peer_error_filter():
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def handle_asyncio_exception(loop, context):
        error = context.get("exception")
        message = context.get("message", "")
        if is_stale_peer_error(error) or STALE_PEER_ID in message:
            return
        if previous_handler is not None:
            previous_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handle_asyncio_exception)

async def run():
    web_thread = threading.Thread(target=run_web_server, name="telegram-source-web", daemon=True)
    web_thread.start()
    await app.start()
    try:
        install_peer_error_filter()
        await resolve_storage_group(app)
        await idle()
    finally:
        await app.stop()

app.run(run())
