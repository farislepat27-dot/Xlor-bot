import sqlite3
import random
import string
import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = "8627553248:AAHqOHa-7yyUmxh7CD9-Ywj7oIwlNfWT2ug"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xlor_bot.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user',
        subscription TEXT DEFAULT NULL,
        subscription_end TEXT DEFAULT NULL,
        reg_date TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS keys (
        key_value TEXT PRIMARY KEY,
        duration TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT,
        used_by INTEGER DEFAULT NULL,
        used_at TEXT DEFAULT NULL
    )""")
    conn.commit()
    conn.close()


def db(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    res = c.fetchall()
    conn.commit()
    conn.close()
    return res


def gen_key():
    chars = string.ascii_uppercase + string.digits
    return "-".join("".join(random.choices(chars, k=4)) for _ in range(4))


def get_user(user_id):
    r = db("SELECT user_id,username,password,role,subscription,subscription_end,reg_date FROM users WHERE user_id=?", (user_id,))
    if r:
        return dict(user_id=r[0][0], username=r[0][1], password=r[0][2], role=r[0][3], subscription=r[0][4], subscription_end=r[0][5], reg_date=r[0][6])
    return None


def get_user_by_name(name):
    r = db("SELECT user_id,username,password,role,subscription,subscription_end,reg_date FROM users WHERE username=?", (name,))
    if r:
        return dict(user_id=r[0][0], username=r[0][1], password=r[0][2], role=r[0][3], subscription=r[0][4], subscription_end=r[0][5], reg_date=r[0][6])
    return None


def sub_text(user):
    if not user:
        return "Подписка: Не активна"
    if user["subscription"] == "forever":
        return "Подписка: Навсегда"
    if user["subscription_end"]:
        try:
            if datetime.strptime(user["subscription_end"], "%d.%m.%Y") > datetime.now():
                return f"Подписка до: {user['subscription_end']}"
        except ValueError:
            pass
    return "Подписка: Истекла"


def main_menu_kb(user):
    kb = [[InlineKeyboardButton("Dashboard", callback_data="dashboard")],
          [InlineKeyboardButton("Активировать ключ", callback_data="activate_key"),
           InlineKeyboardButton("Скачать лаунчер", callback_data="download")]]
    if user["role"] in ("admin", "owner"):
        kb.append([InlineKeyboardButton("Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)


def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_main")]])


def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Генерировать ключ", callback_data="gen_key")],
        [InlineKeyboardButton("Список ключей", callback_data="list_keys")],
        [InlineKeyboardButton("Список пользователей", callback_data="list_users")],
        [InlineKeyboardButton("Выдать роль", callback_data="give_role")],
        [InlineKeyboardButton("Назад", callback_data="back_main")],
    ])


def clear_state(context):
    context.user_data.pop("state", None)
    context.user_data.pop("data", None)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    user = get_user(update.effective_user.id)
    if user:
        text = f"Xlor Client Bot\n\nПривет, {user['username']}!\nID: {user['user_id']}\nРоль: {user['role']}\n{sub_text(user)}\nРегистрация: {user['reg_date']}"
        await update.message.reply_text(text, reply_markup=main_menu_kb(user))
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Регистрация", callback_data="register")],
            [InlineKeyboardButton("Вход", callback_data="login")],
        ])
        await update.message.reply_text("Xlor Client Bot\n\nУправление подпиской, ключами и скачивание лаунчера.\nВойдите или зарегистрируйтесь.", reply_markup=kb)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    user = get_user(update.effective_user.id)
    if not user or user["role"] not in ("admin", "owner"):
        await update.message.reply_text("Доступ запрещён.")
        return
    await update.message.reply_text(f"Admin Panel\n\nДобро пожаловать, {user['username']}.", reply_markup=admin_kb())


async def cb_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = get_user(q.from_user.id)
    if user:
        text = f"Вы уже авторизованы как {user['username']}!"
        await q.edit_message_text(text, reply_markup=main_menu_kb(user))
        return
    context.user_data["state"] = "reg_username"
    await q.edit_message_text("Регистрация\n\nВведите имя пользователя (логин):")


async def cb_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = get_user(q.from_user.id)
    if user:
        text = f"Вы уже авторизованы как {user['username']}!"
        await q.edit_message_text(text, reply_markup=main_menu_kb(user))
        return
    context.user_data["state"] = "login_username"
    await q.edit_message_text("Введите имя пользователя:")


async def cb_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    q = update.callback_query
    await q.answer()
    user = get_user(q.from_user.id)
    if not user:
        await q.edit_message_text("Вы не зарегистрированы. /start")
        return
    score = len(user["username"]) * 100
    text = f"Dashboard\n\nПользователь: {user['username']} [{score}]\nEmail: {user['user_id']}@xlor.gg\nРоль: {user['role']}\nДата регистрации: {user['reg_date']}\n{sub_text(user)}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Активировать ключ", callback_data="activate_key")],
        [InlineKeyboardButton("Сменить пароль", callback_data="change_pass")],
        [InlineKeyboardButton("Скачать лаунчер", callback_data="download")],
        [InlineKeyboardButton("Магазин", callback_data="shop")],
        [InlineKeyboardButton("Назад", callback_data="back_main")],
    ])
    await q.edit_message_text(text, reply_markup=kb)


async def cb_activate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = "awaiting_key"
    await q.edit_message_text("Активация ключа\n\nОтправьте лицензионный ключ:")


async def cb_change_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = "change_old_pass"
    await q.edit_message_text("Введите текущий пароль:")


async def cb_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    q = update.callback_query
    await q.answer()
    launcher_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "XlorLauncher.exe")
    text = "Скачивание лаунчера\n\nСистемные требования:\n- Windows 10+ (x64)\n- Intel / AMD процессор\n- 4GB RAM\n\n"
    if os.path.exists(launcher_path):
        await q.edit_message_text(text + "Файл отправляется...")
        with open(launcher_path, "rb") as f:
            await context.bot.send_document(chat_id=q.from_user.id, document=f, filename="XlorLauncher.exe")
    else:
        await q.edit_message_text(text + "Файл лаунчера не найден на сервере.")
    await context.bot.send_message(chat_id=q.from_user.id, text="Меню:", reply_markup=back_kb())


async def cb_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    q = update.callback_query
    await q.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("30 дней", callback_data="shop_30d"), InlineKeyboardButton("60 дней", callback_data="shop_60d")],
        [InlineKeyboardButton("90 дней", callback_data="shop_90d"), InlineKeyboardButton("Навсегда", callback_data="shop_forever")],
        [InlineKeyboardButton("Free Play", callback_data="shop_free")],
        [InlineKeyboardButton("Назад", callback_data="back_main")],
    ])
    await q.edit_message_text("Магазин\nВыберите план:", reply_markup=kb)


async def cb_shop_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    plan = q.data.replace("shop_", "")
    await q.answer()
    if plan == "free":
        await q.edit_message_text("Вы играете бесплатно! Enjoy!")
    else:
        await q.edit_message_text("Для покупки подписки напишите администратору.\nFunPay: https://funpay.com/users/16043142/")
    await q.message.reply_text("Меню:", reply_markup=back_kb())


async def cb_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    q = update.callback_query
    await q.answer()
    user = get_user(q.from_user.id)
    if user:
        text = f"Xlor Client Bot\n\nПривет, {user['username']}!\nID: {user['user_id']}\nРоль: {user['role']}\n{sub_text(user)}\nРегистрация: {user['reg_date']}"
        await q.edit_message_text(text, reply_markup=main_menu_kb(user))
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Регистрация", callback_data="register")],
            [InlineKeyboardButton("Вход", callback_data="login")],
        ])
        await q.edit_message_text("Xlor Client Bot\n\nВойдите или зарегистрируйтесь.", reply_markup=kb)


async def cb_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    q = update.callback_query
    await q.answer()
    user = get_user(q.from_user.id)
    if not user or user["role"] not in ("admin", "owner"):
        await q.edit_message_text("Доступ запрещён.")
        return
    await q.edit_message_text(f"Admin Panel\n\nДобро пожаловать, {user['username']}.", reply_markup=admin_kb())


async def cb_gen_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("30 дней", callback_data="gen_30"), InlineKeyboardButton("60 дней", callback_data="gen_60")],
        [InlineKeyboardButton("90 дней", callback_data="gen_90"), InlineKeyboardButton("Навсегда", callback_data="gen_forever")],
        [InlineKeyboardButton("Назад", callback_data="admin_panel")],
    ])
    await q.edit_message_text("Выберите длительность ключа:", reply_markup=kb)


async def cb_gen_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    duration = q.data.replace("gen_", "")
    context.user_data["state"] = "gen_count"
    context.user_data["data"] = {"gen_duration": duration}
    await q.edit_message_text("Введите количество ключей (1-100):")


async def cb_list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    q = update.callback_query
    await q.answer()
    rows = db("SELECT key_value,duration,status,created_at,used_by,used_at FROM keys ORDER BY rowid DESC LIMIT 30")
    if not rows:
        text = "Список ключей пуст."
    else:
        lines = []
        for r in rows:
            st = "Активен" if r[2] == "active" else "Использован"
            dur = "навсегда" if r[1] == "forever" else f"{r[1]}д"
            used = f" | Использовал: {r[4]} ({r[5]})" if r[4] else ""
            lines.append(f"{r[0]} | {dur} | {st} | {r[3]}{used}")
        text = "Последние ключи:\n\n" + "\n".join(lines)
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]]))


async def cb_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(context)
    q = update.callback_query
    await q.answer()
    rows = db("SELECT user_id,username,role,subscription,subscription_end FROM users ORDER BY rowid DESC LIMIT 30")
    if not rows:
        text = "Список пользователей пуст."
    else:
        lines = [f"{r[1]} (ID: {r[0]}) | {r[2]} | Подписка: {r[3] or 'нет'}" for r in rows]
        text = "Пользователи:\n\n" + "\n".join(lines)
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]]))


async def cb_give_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = "give_role"
    await q.edit_message_text("Введите Telegram ID пользователя и роль через пробел.\nПример: 123456789 admin\n\nДоступные роли: user, admin")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if state == "reg_username":
        if len(text) < 3:
            await update.message.reply_text("Имя минимум 3 символа. Попробуйте снова:")
            return
        if get_user_by_name(text):
            await update.message.reply_text("Имя занято. Введите другое:")
            return
        context.user_data["data"] = {"reg_username": text}
        context.user_data["state"] = "reg_password"
        await update.message.reply_text("Введите пароль (минимум 6 символов):")

    elif state == "reg_password":
        if len(text) < 6:
            await update.message.reply_text("Пароль минимум 6 символов. Введите снова:")
            return
        d = context.user_data["data"]
        username = d["reg_username"]
        count = db("SELECT COUNT(*) FROM users")[0][0]
        role = "owner" if count == 0 else "user"
        reg_date = datetime.now().strftime("%d.%m.%Y")
        try:
            db("INSERT INTO users (user_id,username,password,role,reg_date) VALUES (?,?,?,?,?)", (user_id, username, text, role, reg_date))
        except sqlite3.IntegrityError:
            clear_state(context)
            await update.message.reply_text("Ошибка. Пользователь уже существует. /start")
            return
        clear_state(context)
        user = get_user(user_id)
        await update.message.reply_text(f"Регистрация успешна! Добро пожаловать, {username}.")
        await update.message.reply_text(f"Xlor Client Bot\n\nПривет, {user['username']}!\nID: {user['user_id']}\nРоль: {user['role']}\n{sub_text(user)}\nРегистрация: {user['reg_date']}", reply_markup=main_menu_kb(user))

    elif state == "login_username":
        user = get_user_by_name(text)
        if not user:
            await update.message.reply_text("Пользователь не найден. Попробуйте снова:")
            return
        context.user_data["data"] = {"login_name": text}
        context.user_data["state"] = "login_password"
        await update.message.reply_text("Введите пароль:")

    elif state == "login_password":
        d = context.user_data["data"]
        user = get_user_by_name(d["login_name"])
        if not user or user["password"] != text:
            clear_state(context)
            await update.message.reply_text("Неверный логин или пароль. /start")
            return
        if user["user_id"] != user_id:
            clear_state(context)
            await update.message.reply_text("Аккаунт привязан к другому Telegram ID.")
            return
        clear_state(context)
        await update.message.reply_text("Вход выполнен!")
        await update.message.reply_text(f"Xlor Client Bot\n\nПривет, {user['username']}!\nID: {user['user_id']}\nРоль: {user['role']}\n{sub_text(user)}\nРегистрация: {user['reg_date']}", reply_markup=main_menu_kb(user))

    elif state == "awaiting_key":
        key = text.upper()
        user = get_user(user_id)
        if not user:
            clear_state(context)
            await update.message.reply_text("Ошибка. /start")
            return
        r = db("SELECT duration,status FROM keys WHERE key_value=?", (key,))
        if not r or r[0][1] != "active":
            await update.message.reply_text("Неверный или использованный ключ.")
            return
        duration = r[0][0]
        now = datetime.now()
        if duration == "forever":
            new_sub, new_end = "forever", "Forever"
        else:
            days = int(duration)
            new_sub = f"{days}d"
            if user["subscription_end"] and user["subscription_end"] != "Forever":
                try:
                    cur = datetime.strptime(user["subscription_end"], "%d.%m.%Y")
                    cur = cur + timedelta(days=days) if cur > now else now + timedelta(days=days)
                except ValueError:
                    cur = now + timedelta(days=days)
            else:
                cur = now + timedelta(days=days)
            new_end = cur.strftime("%d.%m.%Y")
        db("UPDATE users SET subscription=?,subscription_end=? WHERE user_id=?", (new_sub, new_end, user_id))
        db("UPDATE keys SET status='used',used_by=?,used_at=? WHERE key_value=?", (user_id, now.strftime("%d.%m.%Y"), key))
        clear_state(context)
        days_text = "навсегда" if duration == "forever" else f"{duration} дней"
        await update.message.reply_text(f"Ключ активирован на {days_text}!")
        user = get_user(user_id)
        await update.message.reply_text(f"Xlor Client Bot\n\nПривет, {user['username']}!\nID: {user['user_id']}\nРоль: {user['role']}\n{sub_text(user)}\nРегистрация: {user['reg_date']}", reply_markup=main_menu_kb(user))

    elif state == "change_old_pass":
        user = get_user(user_id)
        if not user or user["password"] != text:
            clear_state(context)
            await update.message.reply_text("Неверный пароль. /start")
            return
        context.user_data["state"] = "change_new_pass"
        await update.message.reply_text("Введите новый пароль (минимум 6 символов):")

    elif state == "change_new_pass":
        if len(text) < 6:
            await update.message.reply_text("Пароль минимум 6 символов. Введите снова:")
            return
        db("UPDATE users SET password=? WHERE user_id=?", (text, user_id))
        clear_state(context)
        await update.message.reply_text("Пароль изменён!")
        user = get_user(user_id)
        await update.message.reply_text(f"Xlor Client Bot\n\nПривет, {user['username']}!\nID: {user['user_id']}\nРоль: {user['role']}\n{sub_text(user)}\nРегистрация: {user['reg_date']}", reply_markup=main_menu_kb(user))

    elif state == "gen_count":
        try:
            count = int(text)
            if count < 1 or count > 100:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Число от 1 до 100:")
            return
        duration = context.user_data["data"]["gen_duration"]
        now = datetime.now().strftime("%d.%m.%Y")
        keys = []
        for _ in range(count):
            k = gen_key()
            db("INSERT INTO keys (key_value,duration,status,created_at) VALUES (?,'{}','active',?)".format(duration), (k, now))
            keys.append(k)
        clear_state(context)
        dur_text = "навсегда" if duration == "forever" else f"{duration} дней"
        await update.message.reply_text(f"Сгенерировано {count} ключей ({dur_text}):\n\n" + "\n".join(keys))
        await update.message.reply_text("Admin Panel:", reply_markup=admin_kb())

    elif state == "give_role":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("Формат: ID роль\nПопробуйте снова:")
            return
        try:
            target_id = int(parts[0])
        except ValueError:
            await update.message.reply_text("ID должен быть числом:")
            return
        role = parts[1]
        if role not in ("user", "admin"):
            await update.message.reply_text("Допустимые роли: user, admin")
            return
        target = get_user(target_id)
        if not target:
            await update.message.reply_text("Пользователь не найден.")
            return
        db("UPDATE users SET role=? WHERE user_id=?", (role, target_id))
        clear_state(context)
        await update.message.reply_text(f"Роль {target['username']} изменена на {role}.")
        await update.message.reply_text("Admin Panel:", reply_markup=admin_kb())

    else:
        await update.message.reply_text("Используйте /start")


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Неизвестная команда. Используйте /start")


def main():
    init_db()
    log.info("DB initialized: %s", DB_PATH)

    r = db("SELECT COUNT(*) FROM users")
    log.info("Users in DB: %s", r[0][0])

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))

    app.add_handler(CallbackQueryHandler(cb_register, pattern="^register$"))
    app.add_handler(CallbackQueryHandler(cb_login, pattern="^login$"))
    app.add_handler(CallbackQueryHandler(cb_dashboard, pattern="^dashboard$"))
    app.add_handler(CallbackQueryHandler(cb_activate_key, pattern="^activate_key$"))
    app.add_handler(CallbackQueryHandler(cb_change_pass, pattern="^change_pass$"))
    app.add_handler(CallbackQueryHandler(cb_download, pattern="^download$"))
    app.add_handler(CallbackQueryHandler(cb_shop, pattern="^shop$"))
    app.add_handler(CallbackQueryHandler(cb_shop_plan, pattern="^shop_"))
    app.add_handler(CallbackQueryHandler(cb_back_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(cb_admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(cb_gen_key, pattern="^gen_key$"))
    app.add_handler(CallbackQueryHandler(cb_gen_duration, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(cb_list_keys, pattern="^list_keys$"))
    app.add_handler(CallbackQueryHandler(cb_list_users, pattern="^list_users$"))
    app.add_handler(CallbackQueryHandler(cb_give_role, pattern="^give_role$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Bot started!")
    print("Bot запущен! Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
