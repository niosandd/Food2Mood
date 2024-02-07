import asyncio
import datetime
import time
import logging
from datetime import datetime
from aiogram.utils import exceptions

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor


from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, \
    ReplyKeyboardMarkup, InlineQuery, InputTextMessageContent, InlineQueryResultArticle
from pytz import timezone
import ccxt.async_support as ccxt
import json
import requests

from my_libraries import Tools
from help import config
from db import Database
import chat_gpt

db = Database('files/db_users.db')

"""
Загрузка глобальных переменных.
"""

log = Tools.Log('log.log')
reviews = config()['telegram']['reviews']

icons = {
    "Салаты и закуски": "🥗",
    "Первые блюда": "🍲",
    "Горячие блюда": "🍛",
    "Гарниры": "🍚",
    "Десерты": "🍰",
    "Напитки": "☕",
    "Завтрак": "🧑🏻‍🍳",
    "Ужин": "🍽️",
    "Японская кухня": "🍣",
    "Поке": "🥢",
    "Хлеб": "🍞",
    "Соус": "🧉",
    "Дары моря": "🦞",
    "Мясо и птица": "🥩",
    "Радость": "🤩",
    "Печаль": "😢",
    "Гнев": "😡",
    "Спокойствие": "😌",
    "Волнение": "😬",
    "Нутрициолог": "👩🏻‍💻",
    "Пользователи": "🙋🏻‍♀️",
    "Обломов": "⭐",
    "Ивлев": "⭐",
}

try:
    bot = Bot(token=config()['telegram']['api'], parse_mode='HTML',
              protect_content=False)
except:
    print("Заполните файл config.json правильно!")
    time.sleep(10000000)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
main_loop = asyncio.get_event_loop()

last_time = {}
time_wait = 1000  # Задержка в мс

"""
Работа с командами ТГ-бота.
"""

import handlers.menu_start as m_start
import handlers.menu_client as m_settings
import handlers.menu_food as m_food


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user = message.from_user.id
    if db.check_users_user_exists(message.from_user.id):
        print(f"│ [{Tools.timenow()}] {message.from_user.first_name} → Меню")
        if not db.get_users_ban(message.from_user.id):
            await m_start.start(message)
        else:
            await bot.send_message(
                chat_id=user,
                text="\n🚫 <b>Ваш аккаунт был временно заблокирован!</b>"
                        "\n"
                        "\n<i>Уважаемый пользователь,"
                        "\nМы заметили некоторую подозрительную активность, связанную с вашей учетной записью, и в целях обеспечения безопасности мы временно приостановили доступ к вашему аккаунту.</i>"
            )
    else:
        print(f"│ [{Tools.timenow()}] NEW {message.from_user.first_name} → Меню")
        await m_start.start(message)


@dp.inline_handler()
async def food_restaurant_search(inline_query: InlineQuery):
    user = inline_query.from_user.id
    mode = db.get_users_mode(user)

    # Поиск ресторана
    if mode['key'] == 'food_inline_handler':
        if len(str(inline_query.query)) > 0:
            print(f'│ [{Tools.timenow()}] Пользователь ищет ресторан... {str(inline_query.query)}')
            posts = db.restaurants_find_all(str(inline_query.query).lower().capitalize())
        else:
            posts = db.restaurants_get_all()

        results = []
        if posts == []:
            result = InlineQueryResultArticle(
                id='0',
                title=f"Ресторана в базе нет 😔",
                description="Нажмите, чтобы добавить ресторан ⬅",
                input_message_content=InputTextMessageContent(f'Ресторана в базе нет 😔'),
            )
            results.append(result)
            db.set_users_mode(user, db.get_users_mode(user)['id'], 'food_inline_handler_empty')
        else:
            for post in posts:
                result = InlineQueryResultArticle(
                    id=post[0],
                    title=f"«{post[1]}»",
                    description=post[2],
                    input_message_content=InputTextMessageContent(f'{post[1]}:{post[2]}'),
                )
                results.append(result)
            db.set_users_mode(user, db.get_users_mode(user)['id'], 'food_inline_handler')

        await inline_query.answer(results, cache_time=1)

    # Поиск блюда
    elif mode['key'] == 'wrire_review':
        rest_name = db.get_client_temp_rest(user).split(':')[0]
        if len(str(inline_query.query)) > 0:
            print(f'│ [{Tools.timenow()}] Пользователь ищет блюдо... {str(inline_query.query)}')
            posts = db.restaurants_find_dish(rest_name, str(inline_query.query).lower().capitalize())
        else:
            posts = db.restaurants_get_all_dish(rest_name)

        results = []
        if len(posts) == 0:
            result = InlineQueryResultArticle(
                id='0',
                title=f"Такого блюда в базе нет 🤔",
                description="Попробуйте ввести другое название",
                input_message_content=InputTextMessageContent(f'Такого блюда в базе нет 🤔\nПопробуйте ввести другое название'),
            )
            results.append(result)
            await inline_query.answer(results, cache_time=1)
        else:
            for post in posts:
                result = InlineQueryResultArticle(
                    id=post[0],
                    title=f"«{post[1]}»: «{post[3]}»",
                    description=post[2],
                    input_message_content=InputTextMessageContent(f'{post[1]}:{post[2]}:{post[3]}'),
                )
                results.append(result)
            await inline_query.answer(results[:10], cache_time=1)


@dp.message_handler(content_types=["any"])
async def bot_message(message):
    user = message.from_user.id
    mode = db.get_users_mode(user)
    if message.text != '/start':

        # Чёрный список продуктов
        if mode['key'] == 'client_register_blacklist':
            await client_register_blacklist(user, message)

        # Запросить заведение
        if mode['key'] == 'food_inline_handler_empty':
            await bot.send_message(
                chat_id=user,
                text="Пришлите интересующее вас заведение в наш чат @jul_lut, мы будем вам очень благодарны ✨",
                reply_markup=buttons_00()
            )

        # Выбор ресторана из поиска
        if mode['key'] == 'food_inline_handler':
            await m_food.food_rec_get(user, message)

        # Выбор блюда из поиска
        if mode['key'] == 'wrire_review':
            dish = message.text.split(':')
            dish_id = db.restaurants_get_dish(dish[0], dish[1], dish[2])[0]
            db.set_client_temp_dish_id(user, dish_id)
            await choose_dish(dish_id, message)

        # Отправить отзыв
        if mode['key'] == 'review':
            await bot.send_message(
                chat_id=reviews,
                text=f"⭐️ Новый отзыв от id<code>{user}</code>:\n"
                     f"\n"
                     f"<i>{message.text}</i>"
            )
            db.restaurants_set_review(db.get_client_temp_dish_id(user), message.text)
            await bot.edit_message_text(
                chat_id=user,
                message_id=mode['id'],
                text=f"Спасибо за отзыв! ⭐️",
                reply_markup=buttons_02()
            )
            db.set_users_mode(user, mode['id'], '')

    try:
        await bot.delete_message(user, message.message_id)
    except:
        pass

async def client_register_blacklist(user, message: types.Message):
    message_obj = await message.answer(
        text=f"Одну секунду... ⏳"
    )
    products = chat_gpt.send_message(message.text)
    db.set_client_blacklist(user, products)
    await bot.edit_message_text(
        chat_id=user,
        message_id=message_obj.message_id,
        text=f"Эти продукты вы НЕ едите:\n"
             f"<code>{products}</code>\n"
             f"\n"
             f"Всё верно?",
        reply_markup=buttons_01()
    )


def buttons_00():
    menu = InlineKeyboardMarkup(row_width=1)

    btn1 = InlineKeyboardButton(text="Хорошо! Удалить это сообщение.",
                                callback_data="temp_del")

    menu.add(btn1)

    return menu

def buttons_01():
    menu = InlineKeyboardMarkup(row_width=1)

    btn1 = InlineKeyboardButton(text="Да, всё верно 👍🏻",
                                callback_data="client_register_ready")

    btn2 = InlineKeyboardButton(text="Нет! Сейчас напишу заново 👎🏻",
                                callback_data="client_register_notready")

    menu.add(btn1)
    menu.add(btn2)

    return menu

def buttons_02():
    menu = InlineKeyboardMarkup(row_width=1)

    btn1 = InlineKeyboardButton(text="« Вернуться на главную",
                                callback_data="menu_start")

    menu.add(btn1)

    return menu


"""
Вспомогательные функции.
"""

@dp.callback_query_handler(text_contains=f"temp_del")
async def temp_del(call: types.CallbackQuery):
    user = call.from_user.id
    data = call.data.split('_')
    await bot.delete_message(user, call.message.message_id)


async def checker():
    while True:
        await asyncio.sleep(60 - time.time() % 60)
        # await asyncio.sleep(10)

        for client in db.all_client():
            try:
                client_id = client[0]
                client_alert = client[-1]
                if client_alert == 0:
                    continue

                if round(time.time()) > client_alert + 60*30 - 60:
                # if True:
                    mode = db.get_users_mode(client_id)
                    message_obj = await bot.send_message(
                        chat_id=client_id,
                        text=f"Благодарим, что воспользовались рекомендациями food mood! 🤌🏻\n"
                             f"\n"
                             f"Оцените блюдо, которое вы взяли в данном заведении! "
                             f"Это поможет нам с анализом ваших вкусовых предпочтений "
                             f"и окажет влияние на ваши персональные рекомендации "
                             f"в будущем 😏🔮",
                        reply_markup=buttons_03()
                    )
                    db.set_client_can_alert(client_id, 0)
                    db.set_users_mode(client_id, message_obj.message_id, 'wrire_review')
            except BaseException as ex:
                print(f"│ Не получилось попросить отзыв: {ex}")

async def choose_dish(dish_id, message: types.Message):
    user = message.from_user.id
    if db.get_users_ban(user):
        return None

    # Действие:
    mode = db.get_users_mode(user)
    dish = db.restaurants_get_by_id(dish_id)

    message_obj = await bot.edit_message_text(
        chat_id=user,
        message_id=mode['id'],
        text=f"🍤 <b>Ресторан:</b>\n"
             f"<i>«{dish[1]}», {dish[2]}</i>\n"
             f"\n"
             f"💫 Блюдо:\n"
             f"<i>«{dish[4]}»</i>\n"
             f"\n"
             f"Оцените блюдо по шкале от 1 до 5 👇🏻",
        reply_markup=buttons_04(dish_id)
    )
    db.set_users_mode(user, mode['id'], 'review')


def buttons_03():
    menu = InlineKeyboardMarkup(row_width=1)

    btn1 = InlineKeyboardButton(text="🔎 Выбрать блюдо", switch_inline_query_current_chat='')

    menu.add(btn1)

    return menu

def buttons_04(dish_id):
    menu = InlineKeyboardMarkup(row_width=1)

    btn1 = InlineKeyboardButton(text="1 ⭐",
                                callback_data=f"review_star_1_{dish_id}")

    btn2 = InlineKeyboardButton(text="2 ⭐",
                                callback_data=f"review_star_2_{dish_id}")

    btn3 = InlineKeyboardButton(text="3 ⭐",
                                callback_data=f"review_star_3_{dish_id}")

    btn4 = InlineKeyboardButton(text="4 ⭐",
                                callback_data=f"review_star_4_{dish_id}")

    btn5 = InlineKeyboardButton(text="5 ⭐",
                                callback_data=f"review_star_5_{dish_id}")

    menu.row(btn1, btn2, btn3, btn4, btn5)

    return menu


@dp.callback_query_handler(text_contains=f"review_end")
async def review_end(call: types.CallbackQuery):
    user = call.from_user.id
    data = call.data.split('_')
    if db.get_users_ban(user):
        return None

    mode = db.get_users_mode(user)
    await bot.edit_message_text(
        chat_id=user,
        message_id=call.message.message_id,
        text=f"Спасибо за отзыв! ⭐️",
        reply_markup=buttons_02()
    )
    db.set_users_mode(user, mode['id'], '')



@dp.callback_query_handler(text_contains=f"review_star")
async def review_star(call: types.CallbackQuery):
    user = call.from_user.id
    data = call.data.split('_')
    if db.get_users_ban(user):
        return None

    # Действие:
    mode = db.get_users_mode(user)
    dish_id = int(data[-1])
    dish = db.restaurants_get_by_id(dish_id)
    db.restaurants_set_rating(dish_id, int(data[-2]))

    message_obj = await bot.edit_message_text(
        chat_id=user,
        message_id=mode['id'],
        text=f"🍤 <b>Ресторан:</b>\n"
             f"<i>«{dish[1]}», {dish[2]}</i>\n"
             f"\n"
             f"💫 Блюдо:\n"
             f"<i>«{dish[4]}»</i>\n"
             f"\n"
             f"Если хотите оставить письменный отзыв, напиши его в ответ на это сообщение 🙏🏻\n"
             f"\n"
             f"Спасибо!",
        reply_markup=buttons_05()
    )
    db.set_users_mode(user, mode['id'], 'review')


def buttons_05():
    menu = InlineKeyboardMarkup(row_width=1)

    btn1 = InlineKeyboardButton(text="Пропустить",
                                callback_data=f"review_end")

    menu.row(btn1)

    return menu
"""
Запуск.
"""


async def main():
    print(Tools.Color().send_contact())
    print("╭─")
    asyncio.create_task(checker())


if __name__ == '__main__':
    try:
        from handlers import dp

        loop = asyncio.get_event_loop()
        loop.create_task(main())
        executor.start_polling(dp)
    except BaseException as ex:
        print("╰─")
        print(Tools.Color().red("╭─"))
        print(Tools.Color().red(f"│ Ошибка: {ex}."))
        print(Tools.Color().red(f"│ Устраните проблему и перезапустите бота."))
        print(Tools.Color().red(f"│ По всем вопросам: @Oleg_TheSure"))
        print(Tools.Color().red("╰─"))
        log.log_critical('DUMP!!!', True)
        time.sleep(1000000)
