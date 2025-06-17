import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

API_TOKEN = '7621100705:AAHJ7R4N4ihthLUjV7cvcP95WrAo4GQOvl8'
ADMIN_CHAT_ID = '2105766790'
MENU_FILE = 'menu.json'

logging.basicConfig(level=logging.INFO)

# Создаём объект бота с указанием parse_mode напрямую
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# ... остальной код без изменений ...


# STATES
class OrderFSM(StatesGroup):
    choosing_item = State()
    choosing_time = State()
    choosing_payment = State()
    confirming_payment = State()

class FeedbackFSM(StatesGroup):
    writing_feedback = State()

# LOAD MENU
def load_menu():
    try:
        with open(MENU_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_menu(menu):
    with open(MENU_FILE, 'w', encoding='utf-8') as f:
        json.dump(menu, f, indent=2, ensure_ascii=False)

menu_data = load_menu()

# MARKUPS
def main_menu_kb(user_id=None):
    buttons = [
        [
            InlineKeyboardButton(text='☕ Меню', callback_data='menu'),
            InlineKeyboardButton(text='📍 Где мы находимся?', callback_data='location')
        ],
        [
            InlineKeyboardButton(text='📞 Контакты', callback_data='contacts'),
            InlineKeyboardButton(text='✉️ Обратная связь', callback_data='feedback')
        ]
    ]
    if str(user_id) == ADMIN_CHAT_ID:
        buttons.append([
            InlineKeyboardButton(text='🛠 Редактировать меню', callback_data='edit_menu')
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def menu_kb():
    keyboard = []
    row = []
    for i, item in enumerate(menu_data):
        row.append(InlineKeyboardButton(text=f"{item} - {menu_data[item]['price']}₽", callback_data=f"order:{item}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def time_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Как можно скорее', callback_data='time:soon')],
        [InlineKeyboardButton(text='Указать время', callback_data='time:custom')]
    ])

def payment_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='СБП', callback_data='pay:sbp')],
        [InlineKeyboardButton(text='Картой', callback_data='pay:card')]
    ])

# HANDLERS
@dp.message(F.text, F.text.lower().in_(['start', '/start']))
async def cmd_start(message: Message):
    await message.answer("Добро пожаловать в кофейню! ☕\nВыберите действие:", reply_markup=main_menu_kb(message.from_user.id))

@dp.callback_query(F.data == 'menu')
async def show_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("📋 Меню:", reply_markup=menu_kb())

@dp.callback_query(F.data.startswith('order:'))
async def order_item(callback: CallbackQuery, state: FSMContext):
    item_name = callback.data.split(':')[1]
    item = menu_data.get(item_name)
    if item:
        await state.set_state(OrderFSM.choosing_time)
        await state.update_data(item=item_name)
        await callback.answer()
        await callback.message.edit_text(
            f"Вы выбрали: <b>{item_name}</b> за <b>{item['price']}₽</b>\n\n"
            "Когда приготовить заказ?",
            reply_markup=time_kb()
        )

@dp.callback_query(F.data.startswith('time:'))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(':')[1]
    await callback.answer()
    if choice == 'soon':
        await state.update_data(time='как можно скорее')
        await state.set_state(OrderFSM.choosing_payment)
        await callback.message.edit_text("Выберите способ оплаты:", reply_markup=payment_kb())
    elif choice == 'custom':
        await state.set_state(OrderFSM.choosing_payment)
        await callback.message.edit_text("Введите время, к которому приготовить заказ (например, 15:30):")

@dp.message(OrderFSM.choosing_payment)
async def set_custom_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await state.set_state(OrderFSM.confirming_payment)
    await message.answer("Выберите способ оплаты:", reply_markup=payment_kb())

@dp.callback_query(F.data.startswith('pay:'))
async def choose_payment(callback: CallbackQuery, state: FSMContext):
    payment_method = callback.data.split(':')[1]
    await state.update_data(payment=payment_method)
    data = await state.get_data()
    item = data.get('item')
    time = data.get('time')
    pay_text = 'СБП' if payment_method == 'sbp' else 'Картой'
    await callback.answer()
    await callback.message.edit_text(
        f"Вы выбрали: <b>{item}</b>\n"
        f"Время приготовления: <b>{time}</b>\n"
        f"Способ оплаты: <b>{pay_text}</b>\n\n"
        "Нажмите \"Подтвердить\" для отправки заказа.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Подтвердить', callback_data='confirm_payment')],
            [InlineKeyboardButton(text='🔙 Назад', callback_data='menu')]
        ])
    )

@dp.callback_query(F.data == 'confirm_payment')
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    item = data.get('item')
    time = data.get('time')
    payment = 'СБП' if data.get('payment') == 'sbp' else 'Картой'
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"📥 Новый заказ:\nТовар: <b>{item}</b>\nВремя: {time}\nОплата: {payment}")
    await callback.answer()
    await callback.message.edit_text("Спасибо за заказ! ☕\nОн скоро будет готов.", reply_markup=main_menu_kb(callback.from_user.id))
    await state.clear()

@dp.callback_query(F.data == 'location')
async def show_location(callback: CallbackQuery):
    yandex_link = "https://yandex.ru/maps/org/playa_coffee/63770758952/?ll=37.468172%2C56.141086&utm_source=share&z=18"
    await callback.answer()
    await callback.message.edit_text(
        "📍 Мы находимся по адресу: Playa Coffee\n"
        f"<a href='{yandex_link}'>Открыть в Яндекс.Картах</a>",
        reply_markup=main_menu_kb(callback.from_user.id),
        disable_web_page_preview=True
    )

@dp.callback_query(F.data == 'contacts')
async def show_contacts(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📞 Наши контакты:\nTelegram-канал: @playacoffee\nhttps://t.me/playacoffee",
        reply_markup=main_menu_kb(callback.from_user.id)
    )

@dp.callback_query(F.data == 'feedback')
async def feedback_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("✍️ Напишите ваш отзыв или вопрос:", reply_markup=main_menu_kb(callback.from_user.id))
    await state.set_state(FeedbackFSM.writing_feedback)

@dp.message(FeedbackFSM.writing_feedback)
async def receive_feedback(message: Message, state: FSMContext):
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"✉️ Обратная связь от @{message.from_user.username}:\n{message.text}")
    await message.answer("Спасибо! Мы учтём ваш отзыв.", reply_markup=main_menu_kb(message.from_user.id))
    await state.clear()

@dp.callback_query(F.data == 'edit_menu')
async def edit_menu(callback: CallbackQuery):
    if str(callback.from_user.id) != ADMIN_CHAT_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "Редактирование меню:\nДобавьте товар в формате: <название>;<цена>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔙 Назад', callback_data='menu')]
        ])
    )

@dp.message(F.text.regexp(r'^.+;\d+$'))
async def add_menu_item(message: Message):
    if str(message.from_user.id) != ADMIN_CHAT_ID:
        return
    try:
        name, price = message.text.split(';')
        menu_data[name.strip()] = {'price': int(price)}
        save_menu(menu_data)
        await message.answer(f"Добавлен новый товар: {name.strip()} за {price}₽", reply_markup=main_menu_kb(message.from_user.id))
    except Exception as e:
        await message.answer("Ошибка добавления. Убедитесь, что формат такой: название;цена")

# ENTRY POINT
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

