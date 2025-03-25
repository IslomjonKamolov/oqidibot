from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

delete_admin = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Adminni o'chirish", callback_data="delete_admin")]
    ],
    resize_keyboard=True,
    row_width=2,
)

add_necessary_follow = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Majburiy obuna qo'shish", callback_data="follow_necessary"),
            InlineKeyboardButton(text="Majburiy obuna o'chirish", callback_data="delete_necessary_follows"),
        ]
    ],
    resize_keyboard=True,
    row_width=2,
)
add_necessary_follow_if_empty_list = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Majburiy obuna qo'shish", callback_data="follow_necessary"),
        ]
    ],
    resize_keyboard=True,
    row_width=2,
)

user_menu_button = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📖 Yuborilgan postlar"),
            KeyboardButton(text="ℹ️ Biz haqimizda"),
        ],
        [
            KeyboardButton(text="📩 Adminga murojaat"),
            KeyboardButton(text="🛠 Sozlamalar"),
        ],
    ],
    resize_keyboard=True,
    selective=True,
)

user_back = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Ortga")]],
    selective=True,
    resize_keyboard=True,
    one_time_keyboard=True,
)

accepting = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm"),
            InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="cancel"),
        ]
    ],
)

admin_panel = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🆕 Yangi postlar qo'shish 🆕"),
            KeyboardButton(text="📊 Foydalanuvchilar soni 📊"),
            KeyboardButton(text="🗂 Barcha Postlar 🗂")
        ],
        [
            KeyboardButton(text="👤 Yangi admin qo'shish"),
            KeyboardButton(text="📋 Adminlar ro'yxati"),
            KeyboardButton(text="🏙 Rasmli xabar yuborish"),
        ],
        [
            KeyboardButton(text="📝 Userlarga xabar yuborish"),
            KeyboardButton(text="💢 Paneldan chiqish"),
            KeyboardButton(text="📄 Majburiy obuna ro'yxati"),
        ],
    ],
    resize_keyboard=True,
)
