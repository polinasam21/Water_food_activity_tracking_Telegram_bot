from aiogram.fsm.state import State, StatesGroup

class UserProfile(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()

class Food(StatesGroup):
    calories_per_100_grams = State()
    number_of_grams = State()
