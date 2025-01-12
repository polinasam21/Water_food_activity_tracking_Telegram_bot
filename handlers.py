from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import UserProfile, Food
from config import API_KEY
import datetime
import requests

router = Router()

users = {}

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Добро пожаловать! Я ваш бот.\nВведите /help для списка команд.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.reply(
        "Доступные команды:\n"
        "/set_profile - Заполнение профиля\n"
        "/log_water <количество (мл)> - Ввод воды\n"
        "/log_food <название продукта> - Ввод еды\n"
        "/log_workout <тип тренировки> <время (мин)> - Ввод тренировки\n"
        "/check_progress - Отображение прогресса\n"
    )

@router.message(Command("set_profile"))
async def start_form(message: Message, state: FSMContext):
    await message.reply("Введите ваш вес (в кг):")
    await state.set_state(UserProfile.weight)

@router.message(UserProfile.weight)
async def process_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await message.reply("Введите ваш рост (в см):")
    await state.set_state(UserProfile.height)

@router.message(UserProfile.height)
async def process_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text)
    await message.reply("Введите ваш возраст:")
    await state.set_state(UserProfile.age)

@router.message(UserProfile.age)
async def process_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.reply("Сколько минут активности у вас в день?")
    await state.set_state(UserProfile.activity)

@router.message(UserProfile.activity)
async def process_activity(message: Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.reply("В каком городе вы находитесь?")
    await state.set_state(UserProfile.city)


def get_temperature(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temperature = data['main']['temp']
        return temperature
    else:
        print(f"Ошибка: {response.status_code}")
        return None

@router.message(UserProfile.city)
async def process_age(message: Message, state: FSMContext):
    await state.update_data(city=message.text)

    data = await state.get_data()
    weight = float(data.get("weight"))
    height = float(data.get("height"))
    age = float(data.get("age"))
    activity = float(data.get("activity"))
    city = message.text

    water_goal = weight * 30 + (activity / 30) * 500
    temperature = get_temperature(city)
    if temperature is not None and temperature > 25:
        water_goal += 500
    calorie_goal = 10 * weight + 6.25 * height - 5 * age + (activity / 30) * 200

    user_id = message.from_user.id
    users[user_id] = {
        "weight": weight,
        "height": height,
        "age": age,
        "activity": activity,
        "city": city,
        "water_goal": water_goal,
        "calorie_goal": calorie_goal,
        "logged_water": 0,
        "logged_calories": 0,
        "burned_calories": 0,
        "date": datetime.date.today()
    }

    await message.reply("Профиль заполнен!\n"
                        f"Ваша дневная норма воды — {water_goal} мл\n"
                        f"Ваша дневная норма калорий — {calorie_goal} ккал")
    await state.clear()

def check_date(user_id):
    current_date = datetime.date.today()
    if users[user_id]["date"] != current_date:
        users[user_id]["logged_water"] = 0
        users[user_id]["logged_calories"] = 0
        users[user_id]["burned_calories"] = 0
        users[user_id]["date"] = current_date

@router.message(Command("log_water"))
async def log_water(message: Message):
    user_id = message.from_user.id
    check_date(user_id)

    if user_id not in users:
        await message.reply("Сначала настройте свой профиль с помощью /set_profile")
        return

    try:
        amount_of_water = float(message.text.split()[1])
        users[user_id]['logged_water'] += amount_of_water
        remaining_amount_of_water = users[user_id]['water_goal'] - users[user_id]['logged_water']
        await message.reply(f"Записано: {amount_of_water} мл\n"
                            f"Осталось {remaining_amount_of_water} мл до достижения дневной нормы")
    except (IndexError, ValueError):
        await message.reply("Используйте команду в формате: /log_water <количество (мл)>")



def get_food_info(product_name):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        if products:
            first_product = products[0]
            return {
                'name': first_product.get('product_name', 'Неизвестно'),
                'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
            }
        return None
    print(f"Ошибка: {response.status_code}")
    return None


@router.message(Command("log_food"))
async def log_food(message: Message, state: FSMContext):
    user_id = message.from_user.id
    check_date(user_id)

    if user_id not in users:
        await message.reply("Сначала настройте профиль с помощью команды /set_profile")
        return

    try:
        type_of_food = message.text.split()[1]
        calories_per_100_grams = get_food_info(type_of_food)["calories"]

        if calories_per_100_grams is None:
            await message.reply("Калорийность для данного продукта не найдена.")
            return

        await state.set_state(Food.calories_per_100_grams)
        await state.update_data(calories_per_100_grams=calories_per_100_grams)
        await message.reply(f"{type_of_food} — {calories_per_100_grams} ккал на 100 г. Сколько грамм вы съели?")
        await state.set_state(Food.number_of_grams)
    except (IndexError, ValueError):
        await message.reply("Используйте команду в формате: /log_food <название продукта>")


@router.message(Food.number_of_grams)
async def process_food(message: Message, state: FSMContext):
    user_id = message.from_user.id
    food_amount = float(message.text)

    data = await state.get_data()
    calories_per_100_grams = data['calories_per_100_grams']

    calories = (food_amount / 100) * calories_per_100_grams
    users[user_id]["logged_calories"] += calories

    await message.answer(f"Записано: {calories} ккал.")
    await state.clear()

@router.message(Command("log_workout"))
async def log_workout(message: Message):
    user_id = message.from_user.id
    check_date(user_id)
    if user_id not in users:
        await message.reply("Сначала настройте профиль с помощью команды /set_profile")
        return

    try:
        workout_info = message.text.split()
        workout_type = workout_info[1]
        workout_time = float(workout_info[2])
        calories_burned = workout_time * 10
        users[user_id]['burned_calories'] += calories_burned

        additional_water = (workout_time / 30) * 200
        await message.reply(f"{workout_type.capitalize()} {workout_time} минут — {calories_burned} ккал. Дополнительно: выпейте {additional_water} мл воды.")
    except (IndexError, ValueError):
        await message.reply("Используйте команду в формате: /log_workout <тип тренировки> <время (мин)>")

@router.message(Command("check_progress"))
async def check_progress(message: Message):
    user_id = message.from_user.id
    check_date(user_id)
    if user_id not in users:
        await message.answer("Сначала настройте профиль с командой /set_profile.")
        return

    user = users[user_id]
    remaining_water = user['water_goal'] - user['logged_water']
    balance_calories = user['logged_calories'] - user['burned_calories']

    await message.reply(f"Прогресс:\n\n"
                       f"Вода:\n- Выпито: {user['logged_water']} мл из {user['water_goal']} мл\n"
                       f"- Осталось: {remaining_water} мл\n\n"
                       f"Калории:\n- Потреблено: {user['logged_calories']} ккал из {user['calorie_goal']} ккал\n"
                       f"- Сожжено: {user['burned_calories']} ккал\n"
                       f"- Баланс: {balance_calories} ккал")


def setup_handlers(dp):
    dp.include_router(router)
