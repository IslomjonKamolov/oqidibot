import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from datetime import datetime, timedelta
import pytz

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberOwner,
    ChatMemberAdministrator,
    ChatMemberBanned,
    ChatMemberMember,
    ChatMemberLeft,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest
from Keyboards import (
    delete_admin,
    user_menu_button,
    user_back,
    accepting,
    admin_panel,
    add_necessary_follow,
    add_necessary_follow_if_empty_list,
)
from dotenv import load_dotenv
from states import (
    SentToAdmin,
    addNewAdmin,
    Broadcast,
    PhotoSend,
    DeleteAdmin,
    add_necessary_follows,
    delete_necessary_follows,
    AddPost,
    Settings,
)
import os

load_dotenv()

firebase_credentials = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN"),
}

# Bot token can be obtained via https://t.me/BotFather
TOKEN = os.getenv("TOKEN")
cred = credentials.Certificate(firebase_credentials)
# cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
ADMIN_ID = os.getenv("ADMIN_ID")
# All handlers should be attached to the Router (or Dispatcher)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
users = {}

# WEB HOOK CODES
WEBHOOK_HOST = (
    "oqidibot-production-02bf.up.railway.app"  # ngrok’dan keyin yangilanadi
)
# WEBHOOK_HOST = (
#     "https://3e0a-188-113-198-250.ngrok-free.app"  # ngrok’dan keyin yangilanadi
# )
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = "0.0.0.0"  # Lokal server uchun
WEBAPP_PORT = 8000  # Siz tanlagan port

POSTS_PER_PAGE = 10


def get_admins():
    admins_ref = db.collection("admins").stream()
    admin_ids = [int(admin.to_dict()["admin_id"]) for admin in admins_ref]
    return admin_ids


def get_channels_list():
    channels_ref = db.collection("channels").stream()
    channels = [channel.to_dict() for channel in channels_ref]
    return channels


async def check_subscription(user_id: int, channel_id: int) -> bool:
    """Foydalanuvchining bitta kanalda a'zo ekanligini tekshiradi"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return isinstance(
            member, (ChatMemberOwner, ChatMemberAdministrator, ChatMemberMember)
        )
    except TelegramBadRequest:
        return False


async def check_subscriptions(user_id: int, channels: list) -> list:
    """Foydalanuvchining barcha kanallarga a'zo ekanligini tekshiradi"""
    not_subscribed = []  # Obuna bo‘lmagan kanallar
    for channel in channels:
        channel_id = channel["id"]
        if not await check_subscription(user_id, channel_id):
            not_subscribed.append(channel)  # Agar a'zo bo'lmasa, ro‘yxatga qo‘shamiz
    return not_subscribed  # Obuna bo‘lmagan kanallar ro‘yxati qaytadi


async def send_subscription_message(user_id: int, channels: list, user_name: str):
    """Obuna bo‘lmagan kanallar bo‘lsa, button bilan xabar yuboradi"""
    not_subscribed = await check_subscriptions(user_id, channels)

    if not not_subscribed:
        return (
            f"Assalomu aleykum <b>{user_name}</b>!\nMen sizga kunlik postlarni o'qishingizda yordam beraman 😃",
            user_menu_button,
            True,
        )

    # Inline button yasash
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[]
    )  # ✅ Bo‘sh inline_keyboard yaratish

    for channel in not_subscribed:
        btn = InlineKeyboardButton(
            text=f"➕ {channel['title']}",
            url=(
                channel["username"]
                if channel["username"].startswith("https://t.me/")
                else f"https://t.me/{channel['username']}"
            ),
        )
        keyboard.inline_keyboard.append([btn])  # ✅ Tugmani qo‘shish

    return (
        f"Assalomu aleykum {user_name}👋\n\nBotdan foydalanish uchun homiylarimizga obuna bo'ling❗\nBarcha homiylarga obuna bo'lgach /start buyrug'ini yuboring :)",
        keyboard,
        False,
    )


async def is_private_chat(message: Message) -> bool:
    """Foydalanuvchi bot bilan shaxsiy chatda gaplashayotganini tekshiradi."""
    return message.chat.type == "private"


@dp.message(F.text == "⬅️ Ortga")
async def back(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    await state.clear()
    await message.answer("Murojat bekor qilindi.", reply_markup=user_menu_button)


# Start command
@dp.message(Command("start"))
async def start_fun(message: Message):
    user_id = message.from_user.id
    channels = get_channels_list()
    user_name = message.from_user.full_name

    text, keyboard, subscribed = await send_subscription_message(
        user_id, channels, user_name
    )
    if not await is_private_chat(message):
        return
    await message.answer(f"{text}", reply_markup=keyboard, parse_mode="html")

    # Foydalanuvchi ma'lumotlarini saqlash yoki yangilash
    user_ref = db.collection("Users").document(str(user_id))
    user_data = user_ref.get().to_dict() or {}

    # Agar user yangi bo'lsa, standart sozlamalar qo'shiladi
    if not user_data:
        user_data = {
            "id": user_id,
            "name": user_name,
            "username": message.from_user.username or "Noma'lum",
            "notification_frequency": "daily",  # Standart qiymat
            "last_sent_date": None,
        }
    else:
        # Eski foydalanuvchi bo'lsa, faqat asosiy ma'lumotlarni yangilaymiz
        user_data.update(
            {
                "id": user_id,
                "name": user_name,
                "username": message.from_user.username or "Noma'lum",
            }
        )

    user_ref.set(user_data)


@dp.message(F.text == "📖 Yuborilgan postlar")
async def show_sent_posts(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_ref = db.collection("Users").document(str(user_id))
    user_data = user_ref.get().to_dict()
    if not user_data:
        await message.answer("Sizga hali postlar yuborilmagan :(")
        return

    if "sent_posts" not in user_data:
        await message.answer("Sizga hali postlar yuborilmagan ☹")
        return
    sent_posts = user_data["sent_posts"]

    if not sent_posts:
        await message.answer("Yuborilgan postlar topilmadi 🙄")
        return
    await state.update_data(sent_posts=sent_posts, current_page=0)
    await display_page(message, sent_posts, 0)


async def display_page(message: Message, sent_posts: list, page: int):
    start_idx = page * POSTS_PER_PAGE
    end_idx = start_idx + POSTS_PER_PAGE
    page_posts = sent_posts[start_idx:end_idx]

    if not page_posts:
        await message.answer("Postlar topilmadi 😫")
        return

    # Ro‘yxat matnini shakllantirish
    response = "\n".join(
        [f"🎐{i+1+start_idx}) {post['title']}" for i, post in enumerate(page_posts)]
    )

    # Tugmalar
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Tugmalarni 5 tadan ikki qator qilib joylashtirish
    buttons_rows = []
    current_row = []
    for i, post in enumerate(page_posts):
        current_row.append(
            InlineKeyboardButton(
                text=str(i + 1 + start_idx), callback_data=f"post_{post['id']}"
            )
        )
        if len(current_row) == 5:  # Har bir qatorda 5 ta tugma
            buttons_rows.append(current_row)
            current_row = []
    if current_row:  # Qolgan tugmalarni qatorga qo‘shish
        buttons_rows.append(current_row)

    # Tugma qatorlarini keyboard’ga qo‘shish
    keyboard.inline_keyboard.extend(buttons_rows)

    # Oldingi/Keyingi tugmalari
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅ Oldingi", callback_data=f"prev_{page}")
        )
    if end_idx < len(sent_posts):
        nav_buttons.append(
            InlineKeyboardButton(text="Keyingi ➡", callback_data=f"next_{page}")
        )
    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)

    # Xabarni yangilash yoki yuborish
    if message.text.startswith("📑 Yuborilgan postlar"):
        await message.edit_text(
            f"📑 Yuborilgan postlar ro'yxati:\n\n{response}", reply_markup=keyboard
        )
    else:
        await message.answer(
            f"📑 Yuborilgan postlar ro'yxati:\n\n{response}", reply_markup=keyboard
        )


@dp.callback_query(F.data.startswith(("post_", "prev_", "next_")))
async def handle_callbacks(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    user_data = await state.get_data()
    sent_posts = user_data.get("sent_posts", [])

    if data.startswith("post_"):
        post_id = data.split("_")[1]
        post_ref = db.collection("posts").document(post_id)
        post_data = post_ref.get().to_dict()

        if not post_data:
            await callback.message.answer("Bu post topilmadi")
            print(post_data)
            return

        if post_data["type"] == "text":
            await callback.message.answer(
                post_data["content"], parse_mode="html", disable_web_page_preview=True
            )
        elif post_data["type"] == "photo":
            await callback.message.answer_photo(
                post_data["content"],
                caption=post_data.get("caption", ""),
                parse_mode="html",
            )
        elif post_data["type"] == "video":
            await callback.message.answer_video(
                post_data["content"],
                caption=post_data.get("caption", ""),
                parse_mode="html",
            )

    elif data.startswith("prev_") or data.startswith("next_"):
        current_page = int(data.split("_")[1])
        new_page = current_page - 1 if data.startswith("prev_") else current_page + 1
        await state.update_data(current_page=new_page)
        await display_page(callback.message, sent_posts, new_page)

    await callback.answer()


@dp.message(F.text == "🛠 Sozlamalar")
async def settings_menu(message: Message, state: FSMContext):
    await message.answer(
        "Postlarni qachon olishni hohlaysiz❓\nBulardan birini tanlashingiz mumkin 👇",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Har kuni", callback_data="daily")],
                [
                    InlineKeyboardButton(
                        text="Har ikki kunda", callback_data="every_two_days"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Muayyan kunlar", callback_data="specific_days"
                    )
                ],
            ]
        ),
    )
    await message.answer(
        "🔙 Orqaga qaytish uchun ⬅️ Ortga tugmasini bosing!", reply_markup=user_back
    )
    await state.set_state(Settings.frequency)


@dp.callback_query(F.data.in_(["daily", "every_two_days", "specific_days"]))
async def set_frequency(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    frequency = callback.data
    if callback.data == "every_two_days":
        text = "Sizga postlar endi har ikki kunda bittadan yuboriladi ✅"
    elif callback.data == "daily":
        text = "Sizga endi postlar har kuni bittadan yuboriladi 🌟"
    if frequency == "specific_days":
        await callback.message.answer(
            "Qaysi kunlarda post olishni xohlaysiz? Kunlarni vergul bilan ajrating❗ (masalan: Dushanba, Chorshanba, Juma)",
            reply_markup=user_back,
        )
        await state.set_state(Settings.frequency)
    else:
        user_ref = db.collection("Users").document(str(user_id))
        user_ref.update({"notification_frequency": frequency})
        await callback.message.answer(f"{text}", reply_markup=user_menu_button)
        await state.clear()
    await callback.answer()


@dp.message(Settings.frequency)
async def set_specific_days(message: Message, state: FSMContext):
    if message.text == "⬅️ Ortga":
        await state.clear()
        await message.answer("Sozlamalar bekor qilindi!", reply_markup=user_menu_button)
        return

    days = [day.strip() for day in message.text.split(",")]
    valid_days = [
        "Dushanba",
        "Seshanba",
        "Chorshanba",
        "Payshanba",
        "Juma",
        "Shanba",
        "Yakshanba",
    ]
    if all(day in valid_days for day in days):
        user_ref = db.collection("Users").document(str(message.from_user.id))
        user_ref.update({"notification_frequency": {"specific_days": days}})
        await message.answer(
            f"Postlar {', '.join(days)} kunlari yuboriladi!",
            reply_markup=user_menu_button,
        )
    else:
        await message.answer(
            "Noto‘g‘ri kunlar kiritildi! Iltimos, o'zbekcha kun nomlarini vergul bilan kiriting va hammasini imloviy xatolarsiz yozganingizni tekshiring!"
        )
    await state.clear()


@dp.message(F.text == "🆕 Yangi postlar qo'shish 🆕")
async def add_post_start(message: Message, state: FSMContext):
    admin_list = get_admins()
    if message.from_user.id not in admin_list and message.from_user.id != int(ADMIN_ID):
        await message.answer("Siz admin emassiz!")
        return
    await message.answer(
        "Yangi post uchun matn, rasm yoki video yuboring!\nOrqaga qaytish uchun ⬅️ Ortga tugmasini bosing.",
        reply_markup=user_back,
    )
    await state.set_state(AddPost.content)


@dp.message(AddPost.content)
async def save_post(message: Message, state: FSMContext):
    if message.text == "⬅️ Ortga":
        await state.clear()
        await message.answer("Post qo‘shish bekor qilindi!", reply_markup=admin_panel)
        return

    post_data = {
        "created_at": datetime.now().isoformat(),
        "admin_id": message.from_user.id,
    }

    if message.html_text:
        post_data["type"] = "text"
        post_data["content"] = message.html_text
    elif message.photo:
        post_data["type"] = "photo"
        post_data["content"] = message.photo[-1].file_id
        post_data["caption"] = message.html_text or ""
    elif message.video:
        post_data["type"] = "video"
        post_data["content"] = message.video.file_id
        post_data["caption"] = message.html_text or ""
    else:
        await message.answer("Faqat matn, rasm yoki video yuborishingiz mumkin!")
        return

    # Firestore'ga saqlash
    await state.update_data(post_data=post_data)
    await state.set_state(AddPost.title)
    await message.answer(
        "Post uchun sarlavha kiriting!\n<blockquote>Bu sarlavha ro'yxatda ko'rinish uchun kerak</blockquote>"
    )


@dp.message(AddPost.title)
async def save_post_title(message: Message, state: FSMContext):
    if message.text == "⬅️ Ortga":
        await state.clear()
        await message.answer("Post qo‘shish bekor qilindi!", reply_markup=admin_panel)
        return

    # Avval saqlangan post ma'lumotlarini olish
    data = await state.get_data()
    post_data = data.get("post_data", {})

    # Title’ni qo‘shish
    post_data["title"] = message.text

    # Firestore’ga saqlash
    post_ref = db.collection("posts").document()
    post_data["id"] = post_ref.id
    post_ref.set(post_data)

    await message.answer(
        f"Post (ID: {post_ref.id}) muvaffaqiyatli saqlandi!", reply_markup=admin_panel
    )
    await state.clear()


@dp.message(F.text == "🗂 Barcha Postlar 🗂")
async def show_all_posts(message: Message, state: FSMContext):
    all_posts = [(post.id, post.to_dict()) for post in db.collection("posts").stream()]
    all_posts = sorted(
        all_posts, key=lambda x: x[1]["created_at"]
    )  # Vaqt bo‘yicha tartiblash

    if not all_posts:
        await message.answer("Postlar topilmadi!")
        return

    await state.update_data(all_posts=all_posts, current_page=0)
    await display_all_posts_page(message, all_posts, 0)


async def display_all_posts_page(message: Message, all_posts: list, page: int):
    start_idx = page * POSTS_PER_PAGE
    end_idx = start_idx + POSTS_PER_PAGE
    page_posts = all_posts[start_idx:end_idx]

    if not page_posts:
        await message.edit_text("Postlar topilmadi!")
        return

    # Ro‘yxat matnini shakllantirish
    response = "\n".join(
        [f"✏{i+1+start_idx}. {post[1]['title']}" for i, post in enumerate(page_posts)]
    )

    # Tugmalar
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Tugmalarni 5 tadan ikki qator qilib joylashtirish
    buttons_rows = []
    current_row = []
    for i, (post_id, _) in enumerate(page_posts):
        current_row.append(
            InlineKeyboardButton(
                text=str(i + 1 + start_idx), callback_data=f"allpost_{post_id}"
            )
        )
        if len(current_row) == 5:  # Har bir qatorda 5 ta tugma
            buttons_rows.append(current_row)
            current_row = []
    if current_row:  # Qolgan tugmalarni qatorga qo‘shish
        buttons_rows.append(current_row)

    # Tugma qatorlarini keyboard’ga qo‘shish
    keyboard.inline_keyboard.extend(buttons_rows)

    # Oldingi/Keyingi tugmalari
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅ Oldingi", callback_data=f"allprev_{page}")
        )
    if end_idx < len(all_posts):
        nav_buttons.append(
            InlineKeyboardButton(text="Keyingi ➡", callback_data=f"allnext_{page}")
        )
    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)

    # Xabarni yangilash yoki yuborish
    if message.text.startswith("✏"):
        await message.edit_text(response, reply_markup=keyboard)
    else:
        await message.answer(response, reply_markup=keyboard)


@dp.callback_query(lambda c: c.data.startswith(("allpost_", "allprev_", "allnext_")))
async def handle_all_posts_callbacks(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    user_data = await state.get_data()
    all_posts = user_data.get("all_posts", [])

    if data.startswith("allpost_"):
        post_id = data.split("_")[1]
        post_ref = db.collection("posts").document(post_id)
        post_data = post_ref.get().to_dict()

        if not post_data:
            await callback.message.answer("Post topilmadi!")
            return

        if post_data["type"] == "text":
            await callback.message.answer(
                post_data["content"], parse_mode="html", disable_web_page_preview=True
            )
        elif post_data["type"] == "photo":
            await callback.message.answer_photo(
                post_data["content"],
                caption=post_data.get("caption", ""),
                parse_mode="html",
            )
        elif post_data["type"] == "video":
            await callback.message.answer_video(
                post_data["content"],
                caption=post_data.get("caption", ""),
                parse_mode="html",
            )

    elif data.startswith("allprev_") or data.startswith("allnext_"):
        current_page = int(data.split("_")[1])
        new_page = current_page - 1 if data.startswith("allprev_") else current_page + 1
        await state.update_data(current_page=new_page)
        await display_all_posts_page(callback.message, all_posts, new_page)

    await callback.answer()


@dp.message(Command("admin"))
async def admin_panel_fun(message: Message):
    if not await is_private_chat(message):
        return
    admin_list = get_admins()
    if message.from_user.id in admin_list or message.from_user.id == int(ADMIN_ID):
        await message.answer(
            "Admin paneliga xush kelibsiz 🎊\n\nBugun nima qilmoqchisiz?\n\n",
            reply_markup=admin_panel,
        )
    else:
        await message.answer("Siz admin emassiz❗❗❗")


@dp.message(F.text == "👤 Yangi admin qo'shish")
async def add_new_admin_function(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    admin_list = get_admins()
    if message.from_user.id == int(ADMIN_ID) or message.from_user.id in admin_list:
        await message.answer(
            "<b>Yangi adminni qo'shish uchun admin ID raqamini yuboring!</b>\n\n<i>Namuna:</i> 1234567890\n\n<b>Ortiqcha bitta belgi yoki raqam ham kiritmang ⚠️</b>",
            reply_markup=user_back,
        )
        await state.set_state(addNewAdmin.ID)
    else:
        await message.answer("Siz admin emassiz 💥💢")


@dp.message(addNewAdmin.ID)
async def save_new_admin_id(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    if message.text != "⬅️ Ortga":
        await state.update_data(admin_id=int(message.text))
        await message.answer(
            f"Yangi admin ID raqami {message.text}\n<b>Adminni ismini yuboring bu ro'yxat uchun zaruriy ma'lumot!!!</b>",
            parse_mode="html",
        )
        await state.set_state(addNewAdmin.Name)
    else:
        await message.answer("Murojat bekor qilindi!", reply_markup=admin_panel)
        await state.clear()


@dp.message(addNewAdmin.Name)
async def save_new_admin_id(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    if message.text != "⬅️ Ortga":
        await state.update_data(admin_name=message.text)
        data = await state.get_data()
        admin_id = data.get("admin_id")
        admin_name = data.get("admin_name", "No'malum")
        db.collection("admins").document(str(admin_id)).set(
            {
                "admin_id": admin_id,
                "admin_name": admin_name,
            }
        )
        await message.answer(
            f'User <a href="tg://user?id={admin_id}">{admin_name}</a> admin etib tayinlandi ✅',
            reply_markup=admin_panel,
            parse_mode="html",
        )
        await state.clear()
    else:
        await message.answer("Murojat bekor qilindi!", reply_markup=admin_panel)
        await state.clear()


@dp.message(F.text == "📋 Adminlar ro'yxati")
async def get_admins_list(message: Message):
    if not await is_private_chat(message):
        return
    admins_ref = db.collection("admins").stream()
    admins = [admin.to_dict() for admin in admins_ref]
    if not admins:
        await message.answer("Hali adminlar mavjud emas :(")
        return

    text = "<b>👑 Adminlar ro'yxati:</b>\n\n"
    for admin in admins:
        admin_id = admin.get("admin_id")
        admin_name = admin.get("admin_name", "Noma'lum")
        text += f'<b>Ism:</b> <a href="tg://user?id={admin_id}">{admin_name}</a>\n<b>Id:</b> <code>{admin_id}</code>\n\n'

    await message.answer(text, parse_mode="html", reply_markup=delete_admin)


@dp.callback_query(F.data == "delete_admin")
async def delete_admin_from_admin_list(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Adminni adminlikdan o'chirish uchun uning Id raqamini yuboring!"
    )
    await state.set_state(DeleteAdmin.delete)
    await callback.answer()


@dp.message(DeleteAdmin.delete)
async def delete_admin_from_list(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    admin_id = message.text.strip()
    admin_ref = db.collection("admins").document(admin_id)
    admin_data = admin_ref.get()

    if admin_data.exists:
        admin_ref.delete()
        await message.answer(
            f"Admin <code>{admin_id}</code> o'chirildi.", parse_mode="html"
        )
    else:
        await message.answer(f"Bunday Idga ega Admin topilmadi :(")

    await state.clear()


# About us message
@dp.message(F.text == "ℹ️ Biz haqimizda")
async def about_us(message: Message):
    if not await is_private_chat(message):
        return
    await message.answer(
        f"ℹ️ Biz haqimizda ✅\n\nBu bot sizga ajoyib fikrlar va xulosalar yozilgan foydali postlarni ulashish uchun yaratilgan.\n\nHar kuni postlar qabul qilib o'zingizni rivojlantiring, yangi fikrlar orqali dunyo qarashingizni kengaytiring.\n\n<b>🥷🏻 Loyiha asoschisi:</b> <a href='https://t.me/ikamolov_blog'>Islomjon Kamolov</a>\n\nBiz sizni eng yaqin do'stingiz bo'lamiz 🫂",
        parse_mode="html",
    )


# Message to admin
@dp.message(F.text == "📩 Adminga murojaat")
async def message_to_admin(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    user_id = message.from_user.id
    channels = get_channels_list()
    user_name = message.from_user.full_name

    text, keyboard, bool = await send_subscription_message(user_id, channels, user_name)
    if bool:
        keyboard = user_back
        text = "Murojatingizni yuboring!\n\nFaqat matn yozing aks holda xabaringiz adminga yuborilmaydi❗❗❗\n\nOrqaga qaytish uchun ⬅️ Ortga tugmasini bosing!"
    await message.answer(
        text,
        reply_markup=keyboard,
    )
    await state.set_state(SentToAdmin.message)


@dp.message(F.text == "📝 Userlarga xabar yuborish")
async def send_ads_to_users(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    admin_list = get_admins()
    if message.from_user.id not in admin_list and message.from_user.id != int(ADMIN_ID):
        await message.answer("Siz admin emasiz :(")
        return

    await message.answer(
        "Foydalanuvchiga yuborish uchun xabar matnini yuboring!", reply_markup=user_back
    )
    await state.set_state(Broadcast.message)


@dp.message(F.text == "💢 Paneldan chiqish")
async def exit_from_panel(message: Message):
    if not await is_private_chat(message):
        return
    await message.answer("Paneldan chiqildi!", reply_markup=user_menu_button)


@dp.message(F.text == "📄 Majburiy obuna ro'yxati")
async def get_follows_list(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    channels_ref = db.collection("channels").stream()
    channels = [channel.to_dict() for channel in channels_ref]

    if not channels:
        await message.answer(
            "Hali majburiy obunalar mavjud emas :(\nHohlasangiz pastdagi tugma orqali qo'shishingiz mumkin :)",
            reply_markup=add_necessary_follow_if_empty_list,
        )
        await state.clear()
        return

    text = "<b>Majburiy obunalar ro'yxati:</b>\n\n"
    for channel in channels:
        channel_name = channel.get("title", "Noma'lum kanal")
        channel_url = channel.get("username", "Noma'lum kanal")
        channel_id = channel.get("id", "Noma'lum ID")
        text += f'<b>Kanal:</b> <a href="{channel_url}">{channel_name}</a>\n<b>Id:</b> <code>{channel_id}</code>\n\n'

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=add_necessary_follow,
        disable_web_page_preview=True,
    )
    await state.clear()


@dp.callback_query(F.data == "follow_necessary")
async def add_obligation_follow(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "Majburiy obuna qo'shish uchun kanalning username yoki invite link yuboring!\n\n<b>Namuna:</b> <i>https://t.me/ikamolov_blog</i>\n<b>Namuna:</b> <i>https://t.me/+UpB2BKBumoIzN2Qy</i>",
        parse_mode="html",
        disable_web_page_preview=True,
        reply_markup=user_back,
    )
    await state.set_state(add_necessary_follows.username)


@dp.message(add_necessary_follows.username)
async def follow_necessary_channel(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    await state.update_data(username=message.text)
    await message.answer(
        "Majburiy obunani nomini yuboring!\n\n<b>Namuna:</b> <i>Islomjon Kamolov 🍁</i>",
        parse_mode="html",
    )
    await state.set_state(add_necessary_follows.title)


@dp.message(add_necessary_follows.title)
async def set_obligation_title(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    await state.update_data(title=message.text)
    await message.answer(
        "Majburiy obunani Id raqamini yuboring!\n\nID raqamni @getidsbot orqli bilib olishingiz mumkin."
    )
    await state.set_state(add_necessary_follows.follow_id)


@dp.message(add_necessary_follows.follow_id)
async def set_obligation_id(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    await state.update_data(follow_id=int(message.text))
    data_ref = await state.get_data()
    title = data_ref.get("title")
    follow_id = data_ref.get("follow_id")
    username = data_ref.get("username")
    db.collection("channels").document(f"{follow_id}").set(
        {
            "title": title,
            "id": follow_id,
            "username": username,
        }
    )
    await message.answer(
        f'Majburiy obuna <a href="{username}">{title}</a> qo\'shildi!',
        parse_mode="html",
        reply_markup=admin_panel,
    )
    await state.clear()


@dp.callback_query(F.data == "delete_necessary_follows")
async def delete_necessary_follow_fun(callback: CallbackQuery, state: FSMContext):
    await callback.message.reply(
        "Majburiy obunani o'chirib tashlash uchun uning <b>ID</b> raqamini yuboring!",
        parse_mode="html",
    )
    await state.set_state(delete_necessary_follows.delete_id)


@dp.message(delete_necessary_follows.delete_id)
async def delete_necessary_follow(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    delete_id = message.text
    channel_ref = db.collection("channels").document(delete_id)
    channel = channel_ref.get().to_dict().get("username", "Unknown")
    await message.answer(
        f"Majburiy obuna <a href='{channel}'>{delete_id}</a> raqamida o'chirib tashlandi!",
        parse_mode="html",
    )
    db.collection("channels").document(str(delete_id)).delete()
    await state.clear()


@dp.message(Broadcast.message)
async def send_message_to_all_users(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    if message.text != "⬅️ Ortga":
        users_ref = db.collection("Users").stream()
        user_ids = [
            user.to_dict().get("id") for user in users_ref if user.to_dict().get("id")
        ]

        text = message.html_text
        reply_markup = message.reply_markup if message.reply_markup else None

        if not user_ids:
            await message.answer("⚠️ Hali hech qanday foydalanuvchi yo‘q!")
            await state.clear()
            return

        batch_size = 100  # Har bir batchda 100 ta foydalanuvchi bo'ladi

        for i in range(0, len(user_ids), batch_size):
            batch_users = user_ids[i : i + batch_size]

            # Xabarlarni parallel yuborish
            tasks = [
                bot.send_message(
                    user_id, text, reply_markup=reply_markup, parse_mode="html"
                )
                for user_id in batch_users
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Firestore'ga batch orqali ma'lumotni yangilash
            batch = db.batch()
            for user_id in batch_users:
                doc_ref = db.collection("Users").document(str(user_id))
                batch.update(doc_ref, {"last_message": text})
            batch.commit()

            await asyncio.sleep(1.5)  # Flood limitdan qochish uchun kichik delay

        await message.answer(
            "✅ Xabar barcha foydalanuvchilarga yuborildi!", reply_markup=admin_panel
        )
        await state.clear()
    else:
        await message.answer("Murojat bekor qilindi!", reply_markup=admin_panel)
        await state.clear()


@dp.message(F.text == "🏙 Rasmli xabar yuborish")
async def send_ads_to_users(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    admin_list = get_admins()
    if message.from_user.id not in admin_list and message.from_user.id != int(ADMIN_ID):
        await message.answer("Siz admin emasiz :(")
        return

    await message.answer(
        "<b>Foydalanuvchiga yuborish uchun rasmni yuboring!</b>\n\n<i>Rasmlarga caption ham yozing!</i>",
        parse_mode="html",
        reply_markup=user_back,
    )
    await state.set_state(PhotoSend.photo)


@dp.message(StateFilter(PhotoSend.photo), F.photo)
async def send_photo_to_all_users(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    users_ref = db.collection("Users").stream()
    user_ids = [
        user.to_dict().get("id") for user in users_ref if user.to_dict().get("id")
    ]

    if not user_ids:
        await message.answer("⚠️ Hali hech qanday foydalanuvchi yo‘q!")
        await state.clear()
        return

    photo = message.photo[-1].file_id  # Eng yuqori sifatli rasmni olish
    caption = (
        message.html_text if message.html_text else ""
    )  # Agar caption bo'lsa, uni olish
    reply_markup = message.reply_markup if message.reply_markup else None

    batch_size = 100  # Har bir batchda 100 ta foydalanuvchi bo'ladi

    for i in range(0, len(user_ids), batch_size):
        batch_users = user_ids[i : i + batch_size]

        # Xabarlarni parallel yuborish
        tasks = [
            bot.send_photo(
                user_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="html",
            )
            for user_id in batch_users
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Firestore'ga batch orqali ma'lumotni yangilash
        batch = db.batch()
        for user_id in batch_users:
            doc_ref = db.collection("Users").document(str(user_id))
            batch.update(doc_ref, {"last_photo": photo, "last_caption": caption})
        batch.commit()

        await asyncio.sleep(0.5)  # Flood limitdan qochish uchun kichik delay

    await message.answer(
        "✅ Rasm barcha foydalanuvchilarga yuborildi!", reply_markup=admin_panel
    )
    await state.clear()


@dp.message(SentToAdmin.message)
async def write_message_to_admin(message: Message, state: FSMContext):
    if not await is_private_chat(message):
        return
    state_data = await state.get_state()  # Hozirgi holatni tekshiramiz
    if (
        state_data == SentToAdmin.message.state
    ):  # Faqat adminga yozish rejimida ishlaydi
        if message.text == "⬅️ Ortga":
            await state.clear()
            await message.answer(
                "Murojat bekor qilindi.", reply_markup=user_menu_button
            )
        else:
            await state.update_data(text=message.text)
            await message.answer(
                f"<b>Sizning xabaringiz:</b>\n\n{message.text},\n\n ✅ Yuborish uchun 'Tasdiqlash' tugmasini bosing yoki 🚫 Bekor qilish tugmasini tanlang.",
                reply_markup=accepting,
            )


@dp.callback_query(F.data == "confirm")
async def confirm_message(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    text = data.get("text")
    user_id = callback.from_user.id
    for_admin_message = await bot.send_message(
        ADMIN_ID,
        f"<b>Sizga <a href='tg://user?id={user_id}'>{callback.from_user.full_name}</a>dan murojat keldi!</b>\n\n<i>{text}</i>\n\n#murojat",
        parse_mode="html",
    )
    users[for_admin_message.message_id] = user_id
    await callback.message.delete()
    await callback.message.answer(
        "Murojatingiz qabul qilindi ✅\n\nAgar savol yuborgan bo'lsangiz tez orada adminlar javob berishadi.",
        reply_markup=user_menu_button,
    )
    # await callback.message.answer(
    #     "Murojat bekor qilindi.", reply_markup=user_menu_button
    # )
    await state.clear()


@dp.callback_query(F.data == "cancel")
async def cancel_message(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        "Murojatingiz bekor qilindi.", reply_markup=user_menu_button
    )
    await state.clear()


# reply to message which user sent
@dp.message(F.reply_to_message)
async def reply_to_user(message: Message):
    if not await is_private_chat(message):
        return
    org_msg_id = message.reply_to_message.message_id
    user_id = users.get(org_msg_id)
    if user_id:
        await bot.send_message(
            user_id,
            f"<b>📬 Sizga admindan javob keldi:</b>\n\n<i>{message.text}</i>",
            parse_mode="html",
        )
    else:
        await message.answer("Javob berilayotganda xatolik ro'y berdi!")


@dp.message(F.text == "📊 Foydalanuvchilar soni 📊")
async def get_user_count(message: Message):
    users_ref = db.collection("Users").stream()
    user_count = len([user for user in users_ref if user.to_dict().get("id")])
    if not await is_private_chat(message):
        return
    admin_list = get_admins()
    if message.from_user.id in admin_list or message.from_user.id == int(ADMIN_ID):
        await message.answer(
            f"Hozircha bizda <b>{user_count} ta</b> foydalanuvchi mavjud 🌟",
            parse_mode="html",
        )
    else:
        await message.answer("Siz admin emassiz❗❗❗")


UZ_TIMEZONE = pytz.timezone("Asia/Tashkent")

DAY_MAPPING = {
    "Dushanba": "Monday",
    "Seshanba": "Tuesday",
    "Chorshanba": "Wednesday",
    "Payshanba": "Thursday",
    "Juma": "Friday",
    "Shanba": "Saturday",
    "Yakshanba": "Sunday",
}


# async def send_scheduled_posts():
#     while True:
#         now_uz = datetime.now(UZ_TIMEZONE)
#         today_8_11_uz = now_uz.replace(hour=6, minute=00, second=59, microsecond=0)

#         if now_uz > today_8_11_uz:
#             next_run = today_8_11_uz + timedelta(days=1)
#         else:
#             next_run = today_8_11_uz

#         seconds_until_next_run = max((next_run - now_uz).total_seconds(), 0)
#         print(
#             f"Joriy vaqt: {now_uz}, Keyingi yuborish: {next_run}, Kutish soniyalari: {seconds_until_next_run}"
#         )

#         await asyncio.sleep(seconds_until_next_run)

#         current_day_en = datetime.now(UZ_TIMEZONE).strftime("%A")
#         users_ref = db.collection("Users").stream()

#         # Barcha postlarni yaratilish vaqti bo‘yicha tartib bilan olish
#         all_posts = sorted(
#             [post.to_dict() for post in db.collection("posts").stream()],
#             key=lambda x: x["created_at"],
#         )

#         if not all_posts:
#             print("Post topilmadi!")
#             await asyncio.sleep(3600)
#             continue

#         batch_size = 100
#         users_to_send = {}

#         for user in users_ref:
#             user_data = user.to_dict()
#             user_id = user_data["id"]
#             frequency = user_data.get("notification_frequency", "daily")
#             last_sent = user_data.get("last_sent_date")
#             last_post_id = user_data.get("last_post_id", None)

#             should_send = False
#             if frequency == "daily":
#                 should_send = True  # Har kuni yuboriladi, lekin keyingi post olinadi
#             elif frequency == "every_two_days":
#                 if last_sent is None:
#                     should_send = True
#                 else:
#                     last_sent_date = datetime.fromisoformat(last_sent)
#                     if (datetime.now(UZ_TIMEZONE) - last_sent_date).days >= 2:
#                         should_send = True
#             elif isinstance(frequency, dict) and "specific_days" in frequency:
#                 specific_days_en = [
#                     DAY_MAPPING[day] for day in frequency["specific_days"]
#                 ]
#                 if current_day_en in specific_days_en:
#                     should_send = True

#             if should_send:
#                 # Oxirgi postdan keyingi postni topamiz
#                 if last_post_id is None:
#                     # Birinchi postni yuboramiz
#                     post_to_send = all_posts[0]
#                 else:
#                     # Oxirgi postdan keyingi postni topamiz
#                     last_post_index = next(
#                         (i for i, p in enumerate(all_posts) if p["id"] == last_post_id),
#                         -1,
#                     )
#                     next_post_index = last_post_index + 1
#                     if next_post_index < len(all_posts):
#                         post_to_send = all_posts[next_post_index]
#                     else:
#                         # Agar keyingi post bo‘lmasa, o‘tkazib yuboramiz
#                         continue
#                 users_to_send[user_id] = {"data": user_data, "post": post_to_send}

#         print(f"Yuboriladigan foydalanuvchilar soni: {len(users_to_send)}")
#         if not users_to_send:
#             print("Yuborish uchun foydalanuvchi yoki yangi post topilmadi!")
#             await asyncio.sleep(86400)  # 86400
#             continue

#         # Batch qilib yuborish
#         user_ids = list(users_to_send.keys())
#         for i in range(0, len(user_ids), batch_size):
#             batch_users = user_ids[i : i + batch_size]
#             tasks = []

#             for user_id in batch_users:
#                 user_info = users_to_send[user_id]
#                 post_data = user_info["post"]
#                 if post_data["type"] == "text":
#                     task = bot.send_message(
#                         user_id,
#                         post_data["content"],
#                         parse_mode="html",
#                         disable_web_page_preview=True,
#                     )
#                 elif post_data["type"] == "photo":
#                     task = bot.send_photo(
#                         user_id,
#                         post_data["content"],
#                         caption=post_data.get("caption", ""),
#                         parse_mode="html",
#                         disable_web_page_preview=True,
#                     )
#                 elif post_data["type"] == "video":
#                     task = bot.send_video(
#                         user_id,
#                         post_data["content"],
#                         caption=post_data.get("caption", ""),
#                         parse_mode="html",
#                         disable_web_page_preview=True,
#                     )
#                 tasks.append(task)

#             results = await asyncio.gather(*tasks, return_exceptions=True)
#             for result in results:
#                 if isinstance(result, Exception):
#                     print(f"Xato yuz berdi: {result}")

#             # Firestore’ni yangilash
#             batch = db.batch()
#             for user_id in batch_users:
#                 user_info = users_to_send[user_id]
#                 doc_ref = db.collection("Users").document(str(user_id))
#                 batch.update(
#                     doc_ref,
#                     {
#                         "last_sent_date": datetime.now(UZ_TIMEZONE).isoformat(),
#                         "last_post_id": user_info["post"]["id"],
#                         "sent_posts": firestore.ArrayUnion(
#                             [
#                                 {
#                                     "id": user_info["post"]["id"],
#                                     "title": user_info["post"]["title"],
#                                 }
#                             ]
#                         ),
#                     },
#                 )
#             batch.commit()

#             await asyncio.sleep(1.5)

#         await asyncio.sleep(86400)  # 86400


async def send_scheduled_posts():
    while True:
        now_uz = datetime.now(UZ_TIMEZONE)
        today_8_11_uz = now_uz.replace(hour=6, minute=0, second=0, microsecond=0)
 
        print(f"Joriy vaqt: {now_uz}, 06:00:00 vaqti: {today_8_11_uz}")

        # Vaqtdan qat'i nazar, har doim xabar yuborish
        next_run = today_8_11_uz if now_uz < today_8_11_uz else now_uz

        seconds_until_next_run = max((next_run - now_uz).total_seconds(), 0)
        print(
            f"Keyingi yuborish: {next_run}, Kutish soniyalari: {seconds_until_next_run}"
        )

        await asyncio.sleep(seconds_until_next_run)

        # Xabar yuborish jarayoni
        current_day_en = datetime.now(UZ_TIMEZONE).strftime("%A")
        print(f"Bugungi kun (EN): {current_day_en}")

        users_ref = db.collection("Users").stream()
        all_posts = sorted(
            [post.to_dict() for post in db.collection("posts").stream()],
            key=lambda x: x["created_at"],
        )
        print(f"Postlar soni: {len(all_posts)}")

        if not all_posts:
            print("Post topilmadi! 1 soatdan keyin qayta tekshiriladi.")
            await asyncio.sleep(3600)
            continue

        batch_size = 100
        users_to_send = {}

        for user in users_ref:
            user_data = user.to_dict()
            user_id = user_data["id"]
            frequency = user_data.get("notification_frequency", "daily")
            last_sent = user_data.get("last_sent_date")
            last_post_id = user_data.get("last_post_id", None)

            should_send = False
            if frequency == "daily":
                should_send = True
            elif frequency == "every_two_days":
                if last_sent is None:
                    should_send = True
                else:
                    try:
                        last_sent_date = datetime.fromisoformat(last_sent)
                        days_diff = (datetime.now(UZ_TIMEZONE) - last_sent_date).days
                        if days_diff >= 2:
                            should_send = True
                    except (ValueError, TypeError) as e:
                        print(f"Foydalanuvchi {user_id}: last_sent format xatosi: {e}")
            elif isinstance(frequency, dict) and "specific_days" in frequency:
                specific_days_en = [
                    DAY_MAPPING[day] for day in frequency["specific_days"]
                ]
                if current_day_en in specific_days_en:
                    should_send = True

            if should_send:
                if last_post_id is None:
                    post_to_send = all_posts[0]
                else:
                    last_post_index = next(
                        (i for i, p in enumerate(all_posts) if p["id"] == last_post_id),
                        -1,
                    )
                    next_post_index = last_post_index + 1
                    if next_post_index < len(all_posts):
                        post_to_send = all_posts[next_post_index]
                    else:
                        continue
                users_to_send[user_id] = {"data": user_data, "post": post_to_send}

        if not users_to_send:
            print("Yuborish uchun foydalanuvchi yoki yangi post topilmadi!")
            await asyncio.sleep(86400)
            continue

        user_ids = list(users_to_send.keys())
        for i in range(0, len(user_ids), batch_size):
            batch_users = user_ids[i : i + batch_size]
            tasks = []

            for user_id in batch_users:
                user_info = users_to_send[user_id]
                post_data = user_info["post"]

                if post_data["type"] == "text":
                    task = bot.send_message(
                        user_id,
                        post_data["content"],
                        parse_mode="html",
                        disable_web_page_preview=True,
                    )
                elif post_data["type"] == "photo":
                    task = bot.send_photo(
                        user_id,
                        post_data["content"],
                        caption=post_data.get("caption", ""),
                        parse_mode="html",
                        disable_web_page_preview=True,
                    )
                elif post_data["type"] == "video":
                    task = bot.send_video(
                        user_id,
                        post_data["content"],
                        caption=post_data.get("caption", ""),
                        parse_mode="html",
                        disable_web_page_preview=True,
                    )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"Foydalanuvchi {batch_users[j]} uchun xato: {result}")
                else:
                    print(
                        f"Foydalanuvchi {batch_users[j]} ga xabar muvaffaqiyatli yuborildi"
                    )

            batch = db.batch()
            for user_id in batch_users:
                user_info = users_to_send[user_id]
                doc_ref = db.collection("Users").document(str(user_id))
                batch.update(
                    doc_ref,
                    {
                        "last_sent_date": datetime.now(UZ_TIMEZONE).isoformat(),
                        "last_post_id": user_info["post"]["id"],
                        "sent_posts": firestore.ArrayUnion(
                            [
                                {
                                    "id": user_info["post"]["id"],
                                    "title": user_info["post"].get("title", ""),
                                }
                            ]
                        ),
                    },
                )
            batch.commit()
            print(f"Batch {i // batch_size + 1}: Firestore yangilandi")

            await asyncio.sleep(1.5)

        await asyncio.sleep(86400)  # Har kuni qayta ishga tushadi


# 24 soat kutish


# MAIN FUNCTIONS !!!! DON'T TOUCH !!!!

# Webhook sozlash uchun startup va shutdown (YANGI)
app = web.Application()
webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
webhook_requests_handler.register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)


async def handle(request):
    return await webhook_requests_handler.handle(request)


app.router.add_post("/api/webhook", handle)
app.router.add_get(
    "/api/webhook", handle
)  # Vercel uchun GET so‘rovlarini qo‘llab-quvvatlash


# Webhook’ni sozlash
async def on_startup():
    await bot.set_webhook(url=WEBHOOK_URL)
    print(f"Webhook sozlandi: {WEBHOOK_URL}")
    asyncio.create_task(send_scheduled_posts())


async def on_shutdown():
    await bot.delete_webhook()
    print("Webhook o‘chirildi")


dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)


if __name__ == "__main__":
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
