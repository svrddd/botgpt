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

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

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
    keyboard.append([InlineKeyboardButton(text='🛒 Перейти к оформлению', callback_data='checkout')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def time_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Как можно скорее', callback_data='time:soon')],
        [InlineKeyboardButton(text='Указать время', callback_data='time:custom')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='menu')]
    ])

def payment_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='СБП', callback_data='pay:sbp')],
        [InlineKeyboardButton(text='Картой', callback_data='pay:card')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='menu')]
    ])

def delete_menu_kb():
    keyboard = [
        [InlineKeyboardButton(text=item, callback_data=f"delete_item:{item}")] for item in menu_data
    ]
    keyboard.append([InlineKeyboardButton(text='🔙 Назад', callback_data='edit_menu')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# FSM Helpers
def format_cart(cart):
    if not cart:
        return 'Корзина пуста.'
    text = '🛍 Ваша корзина:\n'
    for item in cart:
        price = menu_data.get(item, {}).get('price', '?')
        text += f"- {item} ({price}₽)\n"
    return text

# ORDER FLOW
@dp.callback_query(F.data == 'menu')
async def show_menu(callback: CallbackQuery):
    await callback.message.edit_text("📋 Меню:", reply_markup=menu_kb())

@dp.callback_query(F.data.startswith('order:'))
async def add_to_cart(callback: CallbackQuery, state: FSMContext):
    item = callback.data.split(':')[1]
    data = await state.get_data()
    cart = data.get('cart', [])
    cart.append(item)
    await state.update_data(cart=cart)
    await callback.answer(f"Добавлено в корзину: {item}")

@dp.callback_query(F.data == 'checkout')
async def proceed_checkout(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get('cart', [])
    if not cart:
        await callback.answer("Корзина пуста!", show_alert=True)
        return
    await state.set_state(OrderFSM.choosing_time)
    await callback.message.edit_text(
        format_cart(cart) + "\n\nКогда приготовить заказ?",
        reply_markup=time_kb()
    )

@dp.callback_query(F.data.startswith('time:'))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(':')[1]
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
    cart = data.get('cart', [])
    time = data.get('time')
    pay_text = 'СБП' if payment_method == 'sbp' else 'Картой'
    await callback.message.edit_text(
        f"{format_cart(cart)}\nВремя приготовления: <b>{time}</b>\nОплата: <b>{pay_text}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Подтвердить', callback_data='confirm_payment')],
            [InlineKeyboardButton(text='🔙 Назад', callback_data='menu')]
        ])
    )

@dp.callback_query(F.data == 'confirm_payment')
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get('cart', [])
    time = data.get('time')
    payment = 'СБП' if data.get('payment') == 'sbp' else 'Картой'
    order_text = format_cart(cart)
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"📥 Новый заказ:\n{order_text}\nВремя: {time}\nОплата: {payment}")
    await callback.message.edit_text("Спасибо за заказ! ☕ Он скоро будет готов.", reply_markup=main_menu_kb(callback.from_user.id))
    await state.clear()

@dp.callback_query(F.data == 'edit_menu')
async def edit_menu(callback: CallbackQuery):
    if str(callback.from_user.id) != ADMIN_CHAT_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    await callback.message.edit_text(
        "Редактирование меню:\nДобавьте товар в формате: <название>;<цена>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🗑 Удалить позицию', callback_data='delete_menu')],
            [InlineKeyboardButton(text='🔙 Назад', callback_data='menu')]
        ])
    )

@dp.callback_query(F.data == 'delete_menu')
async def choose_item_to_delete(callback: CallbackQuery):
    if str(callback.from_user.id) != ADMIN_CHAT_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    if not menu_data:
        await callback.message.edit_text("Меню пусто.", reply_markup=main_menu_kb(callback.from_user.id))
        return
    await callback.message.edit_text("Выберите позицию для удаления:", reply_markup=delete_menu_kb())

@dp.callback_query(F.data.startswith('delete_item:'))
async def delete_menu_item(callback: CallbackQuery):
    if str(callback.from_user.id) != ADMIN_CHAT_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    item = callback.data.split(':')[1]
    if item in menu_data:
        del menu_data[item]
        save_menu(menu_data)
        await callback.message.edit_text(f"Позиция '{item}' удалена.", reply_markup=main_menu_kb(callback.from_user.id))
    else:
        await callback.answer("Позиция не найдена", show_alert=True)

# ENTRY POINT
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
