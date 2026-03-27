import logging
import os
import time
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

TOKEN = "8277742376:AAFYbNj7sLroVHcOcRgYkQf4qnFow6hvOV4"
ADMIN_ID = 5474672519
COOLDOWN_SECONDS = 10

allUsers = set()
userCooldown = {}
userCountry = {}

countries = {
    "🇧🇩": {"name": "Bangladesh", "file": "bd.txt"},
    "🇺🇸": {"name": "USA", "file": "usa.txt"},
    "🇬🇧": {"name": "UK", "file": "uk.txt"}
}

os.makedirs("numbers", exist_ok=True)

logging.basicConfig(level=logging.INFO)


def is_admin(uid):
    return uid == ADMIN_ID


def count_numbers(path):

    if not os.path.exists(path):
        return 0

    with open(path) as f:
        return len([x for x in f.readlines() if x.strip()])


def get_country_keyboard():

    keyboard = []

    for flag, data in countries.items():

        file = f"numbers/{data['file']}"
        remaining = count_numbers(file)

        keyboard.append([
            InlineKeyboardButton(
                f"{flag} {data['name']} ({remaining})",
                callback_data=f"country_{flag}"
            )
        ])

    return InlineKeyboardMarkup(keyboard)


def get_numbers(file):

    if not os.path.exists(file):
        return None

    with open(file) as f:
        numbers = [x.strip() for x in f.readlines() if x.strip()]

    if len(numbers) < 3:
        return None

    send = numbers[:3]
    remain = numbers[3:]

    with open(file, "w") as f:
        f.write("\n".join(remain))

    return send, len(remain)


async def send_numbers(update, numbers, remaining, flag):

    query = update.callback_query
    country = countries[flag]["name"]

    text = f"🔥 *Dynamo OTP New Numbers*\n\n"
    text += f"🌍 Country: {flag} {country}\n"
    text += f"📊 Remaining: {remaining}\n\n"
    text += "📋 Numbers:\n\n"

    for n in numbers:
        text += f"`+{n}`\n\n\n"

    keyboard = [
        [InlineKeyboardButton("➡️ Next 3 Numbers", callback_data="next")],
        [InlineKeyboardButton("🌍 Change Country", callback_data="change_country")],
        [InlineKeyboardButton("👥 OTP Group", url="https://t.me/dynamo_otp_group")]
    ]

    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    allUsers.add(update.effective_chat.id)

    await update.message.reply_text(
        "🌍 Select Country",
        reply_markup=get_country_keyboard()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    chat = query.message.chat.id
    data = query.data

    if data.startswith("country_"):

        flag = data.split("_")[1]
        userCountry[chat] = flag

        file = f"numbers/{countries[flag]['file']}"

        result = get_numbers(file)

        if not result:
            await query.edit_message_text("❌ Not enough numbers")
            return

        numbers, remain = result

        userCooldown[chat] = time.time()

        await send_numbers(update, numbers, remain, flag)

    elif data == "next":

        last = userCooldown.get(chat, 0)

        if time.time() - last < COOLDOWN_SECONDS:

            wait = int(COOLDOWN_SECONDS - (time.time() - last))
            await query.answer(f"⏳ Wait {wait}s", show_alert=True)
            return

        flag = userCountry.get(chat)

        if not flag:
            await query.answer("Select country first")
            return

        file = f"numbers/{countries[flag]['file']}"

        result = get_numbers(file)

        if not result:
            await query.edit_message_text("❌ No numbers left")
            return

        numbers, remain = result

        userCooldown[chat] = time.time()

        await send_numbers(update, numbers, remain, flag)

    elif data == "change_country":

        await query.edit_message_text(
            "🌍 Select Country",
            reply_markup=get_country_keyboard()
        )


# ---------------- ADMIN PANEL ---------------- #

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    keyboard = [
        [InlineKeyboardButton("📤 Upload TXT", callback_data="upload")],
        [InlineKeyboardButton("🗑 Delete File", callback_data="delete")],
        [InlineKeyboardButton("📂 File List", callback_data="list")],
        [InlineKeyboardButton("📊 Country Numbers", callback_data="stats")],
        [InlineKeyboardButton("➕ Add Country", callback_data="add_country")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]

    await update.message.reply_text(
        "⚙️ Admin Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "upload":

        context.user_data["step"] = "upload"
        await query.edit_message_text("📤 Send TXT file")

    elif data == "delete":

        context.user_data["step"] = "delete"
        await query.edit_message_text("Send file name\nExample: bd.txt")

    elif data == "list":

        files = os.listdir("numbers")

        if not files:
            text = "❌ No files"
        else:

            text = "📂 Number Files\n\n"

            for f in files:

                count = count_numbers(f"numbers/{f}")
                text += f"{f} ({count})\n"

        await query.edit_message_text(text)

    elif data == "stats":

        text = "📊 Country Numbers\n\n"

        for flag, data in countries.items():

            file = f"numbers/{data['file']}"
            count = count_numbers(file)

            text += f"{flag} {data['name']} : {count}\n"

        await query.edit_message_text(text)

    elif data == "add_country":

        context.user_data["step"] = "flag"
        await query.edit_message_text("Send country flag")

    elif data == "broadcast":

        context.user_data["step"] = "broadcast"
        await query.edit_message_text("Send broadcast message")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    step = context.user_data.get("step")
    text = update.message.text

    if step == "delete":

        file = f"numbers/{text}"

        if os.path.exists(file):

            os.remove(file)
            await update.message.reply_text("✅ File deleted")

        else:

            await update.message.reply_text("❌ File not found")

        context.user_data.clear()

    elif step == "broadcast":

        success = 0

        for u in allUsers:

            try:
                await context.bot.send_message(u, text)
                success += 1
            except:
                pass

        await update.message.reply_text(f"✅ Sent to {success} users")
        context.user_data.clear()

    elif step == "flag":

        context.user_data["flag"] = text
        context.user_data["step"] = "name"
        await update.message.reply_text("Send country name")

    elif step == "name":

        context.user_data["name"] = text
        context.user_data["step"] = "file"
        await update.message.reply_text("Send file name\nExample: brazil.txt")

    elif step == "file":

        flag = context.user_data["flag"]
        name = context.user_data["name"]
        file = text

        countries[flag] = {"name": name, "file": file}

        await update.message.reply_text("✅ Country added")
        context.user_data.clear()


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    if context.user_data.get("step") != "upload":
        return

    file = await update.message.document.get_file()
    name = update.message.document.file_name
    path = f"numbers/{name}"

    await file.download_to_drive(path)

    await update.message.reply_text(f"✅ Uploaded {name}")

    context.user_data.clear()


# ---------------- MAIN ---------------- #

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getnumber", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(
        CallbackQueryHandler(
            admin_buttons,
            pattern="^(upload|delete|list|stats|add_country|broadcast)$"
        )
    )

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

    print("✅ Bot Running")

    # manual event loop (Python 3.14 fix)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(app.initialize())
    loop.run_until_complete(app.start())
    loop.run_until_complete(app.updater.start_polling())

    loop.run_forever()


if __name__ == "__main__":
    main()
def count_numbers(path):

    if not os.path.exists(path):
        return 0

    with open(path) as f:
        return len([x for x in f.readlines() if x.strip()])


def get_country_keyboard():

    keyboard = []

    for flag, data in countries.items():

        file = f"numbers/{data['file']}"
        remaining = count_numbers(file)

        keyboard.append([
            InlineKeyboardButton(
                f"{flag} {data['name']} ({remaining})",
                callback_data=f"country_{flag}"
            )
        ])

    return InlineKeyboardMarkup(keyboard)


def get_numbers(file):

    if not os.path.exists(file):
        return None

    with open(file) as f:
        numbers = [x.strip() for x in f.readlines() if x.strip()]

    if len(numbers) < 3:
        return None

    send = numbers[:3]
    remain = numbers[3:]

    with open(file, "w") as f:
        f.write("\n".join(remain))

    return send, len(remain)


async def send_numbers(update, numbers, remaining, flag):

    query = update.callback_query

    country = countries[flag]["name"]

    text = f"🔥 *Dynamo OTP New Numbers*\n\n"
    text += f"🌍 Country: {flag} {country}\n"
    text += f"📊 Remaining: {remaining}\n\n"
    text += "📋 Numbers:\n\n"

    for n in numbers:
        text += f"`+{n}`\n\n\n"

    keyboard = [
        [InlineKeyboardButton("➡️ Next 3 Numbers", callback_data="next")],
        [InlineKeyboardButton("🌍 Change Country", callback_data="change_country")],
        [InlineKeyboardButton("👥 OTP Group", url="https://t.me/dynamo_otp_group")]
    ]

    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    allUsers.add(update.effective_chat.id)

    await update.message.reply_text(
        "🌍 Select Country",
        reply_markup=get_country_keyboard()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    chat = query.message.chat.id
    data = query.data

    if data.startswith("country_"):

        flag = data.split("_")[1]

        userCountry[chat] = flag

        file = f"numbers/{countries[flag]['file']}"

        result = get_numbers(file)

        if not result:
            await query.edit_message_text("❌ Not enough numbers")
            return

        numbers, remain = result

        userCooldown[chat] = time.time()

        await send_numbers(update, numbers, remain, flag)

    elif data == "next":

        last = userCooldown.get(chat, 0)

        if time.time() - last < COOLDOWN_SECONDS:

            wait = int(COOLDOWN_SECONDS - (time.time() - last))

            await query.answer(f"⏳ Wait {wait}s", show_alert=True)
            return

        flag = userCountry.get(chat)

        file = f"numbers/{countries[flag]['file']}"

        result = get_numbers(file)

        if not result:
            await query.edit_message_text("❌ No numbers left")
            return

        numbers, remain = result

        userCooldown[chat] = time.time()

        await send_numbers(update, numbers, remain, flag)

    elif data == "change_country":

        await query.edit_message_text(
            "🌍 Select Country",
            reply_markup=get_country_keyboard()
        )


# ---------------- ADMIN PANEL ---------------- #

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    keyboard = [
        [InlineKeyboardButton("📤 Upload TXT", callback_data="upload")],
        [InlineKeyboardButton("🗑 Delete File", callback_data="delete")],
        [InlineKeyboardButton("📂 File List", callback_data="list")],
        [InlineKeyboardButton("📊 Country Numbers", callback_data="stats")],
        [InlineKeyboardButton("➕ Add Country", callback_data="add_country")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ]

    await update.message.reply_text(
        "⚙️ Admin Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "upload":

        context.user_data["step"] = "upload"
        await query.edit_message_text("📤 Send TXT file")

    elif data == "delete":

        context.user_data["step"] = "delete"
        await query.edit_message_text("Send file name\nExample: bd.txt")

    elif data == "list":

        files = os.listdir("numbers")

        if not files:
            text = "❌ No files"

        else:

            text = "📂 Number Files\n\n"

            for f in files:

                count = count_numbers(f"numbers/{f}")

                text += f"{f} ({count})\n"

        await query.edit_message_text(text)

    elif data == "stats":

        text = "📊 Country Numbers\n\n"

        for flag, data in countries.items():

            file = f"numbers/{data['file']}"

            count = count_numbers(file)

            text += f"{flag} {data['name']} : {count}\n"

        await query.edit_message_text(text)

    elif data == "add_country":

        context.user_data["step"] = "flag"

        await query.edit_message_text("Send country flag")

    elif data == "broadcast":

        context.user_data["step"] = "broadcast"

        await query.edit_message_text("Send broadcast message")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    step = context.user_data.get("step")

    text = update.message.text

    if step == "delete":

        file = f"numbers/{text}"

        if os.path.exists(file):

            os.remove(file)

            await update.message.reply_text("✅ File deleted")

        else:

            await update.message.reply_text("❌ File not found")

        context.user_data.clear()

    elif step == "broadcast":

        success = 0

        for u in allUsers:

            try:
                await context.bot.send_message(u, text)
                success += 1
            except:
                pass

        await update.message.reply_text(f"✅ Sent to {success} users")

        context.user_data.clear()

    elif step == "flag":

        context.user_data["flag"] = text
        context.user_data["step"] = "name"

        await update.message.reply_text("Send country name")

    elif step == "name":

        context.user_data["name"] = text
        context.user_data["step"] = "file"

        await update.message.reply_text("Send file name\nExample: brazil.txt")

    elif step == "file":

        flag = context.user_data["flag"]
        name = context.user_data["name"]
        file = text

        countries[flag] = {"name": name, "file": file}

        await update.message.reply_text("✅ Country added")

        context.user_data.clear()


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    if context.user_data.get("step") != "upload":
        return

    file = await update.message.document.get_file()

    name = update.message.document.file_name

    path = f"numbers/{name}"

    await file.download_to_drive(path)

    await update.message.reply_text(f"✅ Uploaded {name}")

    context.user_data.clear()


def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getnumber", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(
        CallbackQueryHandler(
            admin_buttons,
            pattern="^(upload|delete|list|stats|add_country|broadcast)$"
        )
    )

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

    print("✅ Bot Running")

    app.run_polling()


if __name__ == "__main__":
    main()
