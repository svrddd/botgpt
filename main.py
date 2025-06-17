import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

API_TOKEN = '7621100705:AAHJ7R4N4ihthLUjV7cvcP95WrAo4GQOvl8'
ADMIN_CHAT_ID = '2105766790'
MENU_FILE = 'menu.json'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

class OrderFSM(StatesGroup):
    choosing_item = State()
    choosing_time = State()
    choosing_payment = State()
    confirming_payment = State()

class FeedbackFSM(StatesGroup):
    writing_feedback = State()

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

def main_menu_kb(user_id=None):
    buttons = [
        [KeyboardButton(text='☕ Меню'), KeyboardButton(text='📍 Где мы находимся?')],
        [KeyboardButton(text='📞 Контакты'), KeyboardButton(text='✉️ Обратная связь')],
    ]
    if str(user_id) == ADMIN_CHAT_ID:
        buttons.append([KeyboardButton(text='🛠 Редактировать меню')])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def menu_buttons_kb():
    keyboard = []
    row = []
    for i, item in enumerate(menu_data):
        row.append(KeyboardButton(text=item))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton(text='🔙 Назад')])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def time_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='Как можно скорее')],
        [KeyboardButton(text='Указать время')],
        [KeyboardButton(text='🔙 Назад')]
    ], resize_keyboard=True)

def payment_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='СБП')],
        [KeyboardButton(text='Картой')],
        [KeyboardButton(text='🔙 Назад')]
    ], resize_keyboard=True)

@dp.message(F.text.lower().in_(['start', '/start']))
async def cmd_start(message: Message):
    await message.answer("Добро пожаловать в кофейню! ☕\nВыберите действие:", reply_markup=main_menu_kb(message.from_user.id))

@dp.message(F.text == '☕ Меню')
async def show_menu(message: Message):
    if not menu_data:
        await message.answer("Меню пока пустое.", reply_markup=main_menu_kb(message.from_user.id))
        return

    # Формируем текст меню с ценами
    text_menu = "📋 Меню:\n\n"
    for item, data in menu_data.items():
        text_menu += f"{item} - <b>{data['price']}₽</b>\n"
    await message.answer(text_menu, reply_markup=menu_buttons_kb())
    await OrderFSM.choosing_item.set()

@dp.message(OrderFSM.choosing_item)
async def order_item(message: Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await state.clear()
        await message.answer("Главное меню:", reply_markup=main_menu_kb(message.from_user.id))
        return

    item_name = message.text.strip()
    if item_name not in menu_data:
        await message.answer("Пожалуйста, выберите товар из меню или нажмите '🔙 Назад'.")
        return

    price = menu_data[item_name]['price']
    await state.update_data(item=item_name)
    await OrderFSM.choosing_time.set()
    await message.answer(
        f"Вы выбрали: <b>{item_name}</b> за <b>{price}₽</b>\n\n"
        "Когда приготовить заказ?",
        reply_markup=time_kb()
    )

@dp.message(OrderFSM.choosing_time)
async def choose_time(message: Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await OrderFSM.choosing_item.set()
        await message.answer("Выберите товар:", reply_markup=menu_buttons_kb())
        return

    if message.text == 'Как можно скорее':
        await state.update_data(time='как можно скорее')
        await OrderFSM.choosing_payment.set()
        await message.answer("Выберите способ оплаты:", reply_markup=payment_kb())
    elif message.text == 'Указать время':
        await message.answer("Введите время, к которому приготовить заказ (например, 15:30):")
        await OrderFSM.next()
    else:
        await message.answer("Пожалуйста, выберите вариант времени из клавиатуры.")

@dp.message(OrderFSM.choosing_payment)
async def set_custom_time(message: Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await OrderFSM.choosing_time.set()
        await message.answer("Когда приготовить заказ?", reply_markup=time_kb())
        return

    await state.update_data(time=message.text)
    await OrderFSM.confirming_payment.set()
    await message.answer("Выберите способ оплаты:", reply_markup=payment_kb())

@dp.message(OrderFSM.confirming_payment)
async def choose_payment(message: Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await OrderFSM.choosing_payment.set()
        await message.answer("Выберите способ оплаты:", reply_markup=payment_kb())
        return

    if message.text not in ['СБП', 'Картой']:
        await message.answer("Пожалуйста, выберите способ оплаты из клавиатуры.")
        return

    payment_method = 'sbp' if message.text == 'СБП' else 'card'
    await state.update_data(payment=payment_method)

    data = await state.get_data()
    item = data.get('item')
    time = data.get('time')
    pay_text = message.text

    confirm_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='✅ Подтвердить')],
        [KeyboardButton(text='🔙 Назад')]
    ], resize_keyboard=True)

    await message.answer(
        f"Вы выбрали: <b>{item}</b>\n"
        f"Время приготовления: <b>{time}</b>\n"
        f"Способ оплаты: <b>{pay_text}</b>\n\n"
        "Нажмите \"✅ Подтвердить\" для отправки заказа.",
        reply_markup=confirm_kb
    )

@dp.message(OrderFSM.confirming_payment)
async def confirm_payment(message: Message, state: FSMContext):
    if message.text == '✅ Подтвердить':
        data = await state.get_data()
        item = data.get('item')
        time = data.get('time')
        payment = 'СБП' if data.get('payment') == 'sbp' else 'Картой'

        await bot.send_message(chat_id=ADMIN_CHAT_ID,
                               text=f"📥 Новый заказ:\nТовар: <b>{item}</b>\nВремя: {time}\nОплата: {payment}")

        await message.answer("Спасибо за заказ! ☕\nОн скоро будет готов.", reply_markup=main_menu_kb(message.from_user.id))
        await state.clear()
    elif message.text == '🔙 Назад':
        await OrderFSM.choosing_payment.set()
        await message.answer("Выберите способ оплаты:", reply_markup=payment_kb())
    else:
        await message.answer("Пожалуйста, нажмите '✅ Подтвердить' или '🔙 Назад'.")

@dp.message(F.text == '📍 Где мы находимся?')
async def show_location(message: Message):
    yandex_link = "https://yandex.ru/maps/org/playa_coffee/63770758952/?ll=37.468172%2C56.141086&utm_source=share&z=18"
    await message.answer(
        "📍 Мы находимся по адресу: Playa Coffee\n"
        f"<a href='{yandex_link}'>Открыть в Яндекс.Картах</a>",
        reply_markup=main_menu_kb(message.from_user.id),
        disable_web_page_preview=True
    )

@dp.message(F.text == '📞 Контакты')
async def show_contacts(message: Message):
    await message.answer(
        "📞 Наши контакты:\nTelegram-канал: @playacoffee\nhttps://t.me/playacoffee",
        reply_markup=main_menu_kb(message.from_user.id)
    )

@dp.message(F.text == '✉️ Обратная связь')
async def feedback_start(message: Message, state: FSMContext):
    await message.answer("✍️ Напишите ваш отзыв или вопрос:", reply_markup=main_menu_kb(message.from_user.id))
    await state.set_state(FeedbackFSM.writing_feedback)

@dp.message(FeedbackFSM.writing_feedback)
async def receive_feedback(message: Message, state: FSMContext):
    username = message.from_user.username or message.from_user.full_name
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"✉️ Обратная связь от @{username}:\n{message.text}")
    await message.answer("Спасибо! Мы учтём ваш отзыв.", reply_markup=main_menu_kb(message.from_user.id))
    await state.clear()

@dp.message(F.text == '🛠 Редактировать меню')
async def edit_menu(message: Message):
    if str(message.from_user.id) != ADMIN_CHAT_ID:
        await message.answer("Доступ запрещён", reply_markup=main_menu_kb(message.from_user.id))
        return
    await message.answer(
        "Редактирование меню:\nДобавьте товар в формате: <название>;<цена>",
        reply_markup=main_menu_kb(message.from_user.id)
    )

@dp.message(F.text.regexp(r'^.+;\d+$'))
async def add_menu_item(message: Message):
    if str(message.from_user.id) != ADMIN_CHAT_ID:
        return
    try:
        name, price = message.text.split(';')
        name = name.strip()
        price = int(price.strip())
        menu_data[name] = {'price': price}
        save_menu(menu_data)
        await message.answer(f"Добавлен новый товар: {name} за {price}₽", reply_markup=main_menu_kb(message.from_user.id))
    except Exception:
        await message.answer("Ошибка добавления. Убедитесь, что формат такой: название;цена")

@dp.message(F.text == '🔙 Назад')
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_kb(message.from_user.id))

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
