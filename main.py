import logging
import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Твой токен, полученный у BotFather
API_TOKEN = os.environ.get('API_TOKEN')

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Имя файла, в котором будут храниться рецепты
RECIPES_FILE = 'recipes.json'


def load_recipes():
    """Загружает рецепты из JSON-файла."""
    try:
        with open(RECIPES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_recipes(recipes):
    """Сохраняет рецепты в JSON-файл."""
    with open(RECIPES_FILE, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, ensure_ascii=False, indent=4)


# Временное хранилище для рецептов в памяти
RECIPES = load_recipes()


# Определяем состояния
class AddRecipeState(StatesGroup):
    name = State()
    ingredients = State()
    instructions = State()


class EditRecipeState(StatesGroup):
    name = State()
    part = State()
    new_value = State()


# Инициализируем бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# Клавиатура главного меню
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить рецепт", callback_data="add_recipe")],
        [InlineKeyboardButton(text="Смотреть рецепты", callback_data="view_recipes")],
        [InlineKeyboardButton(text="Редактировать рецепт", callback_data="edit_recipe")],
        [InlineKeyboardButton(text="Удалить рецепт", callback_data="delete_recipe")],
    ])


# Клавиатура для показа всех рецептов с кнопками
def get_recipe_list_keyboard(action):
    keyboard = []
    for name in RECIPES.keys():
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"{action}:{name}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Клавиатура для выбора части рецепта для редактирования
def get_edit_recipe_keyboard(recipe_name):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f"edit_part:{recipe_name}:name")],
        [InlineKeyboardButton(text="Ингредиенты", callback_data=f"edit_part:{recipe_name}:ingredients")],
        [InlineKeyboardButton(text="Инструкция", callback_data=f"edit_part:{recipe_name}:instructions")],
    ])


# Обработчик команды /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "Привет! Я — твоя книга рецептов. Выбери действие:",
        reply_markup=get_main_keyboard()
    )


# Обработчик для всех нажатий на кнопки
@dp.callback_query()
async def handle_callback_query(callback: types.CallbackQuery, state: FSMContext):
    # Обязательно отвечаем, чтобы убрать "часики" с кнопки
    await callback.answer()

    # Разбираем callback_data на части
    data = callback.data.split(':')
    action = data[0]

    if action == "add_recipe":
        await callback.message.answer("Отлично, давай добавим новый рецепт! Напиши его **название**.")
        await state.set_state(AddRecipeState.name)

    elif action == "view_recipes":
        if not RECIPES:
            await callback.message.answer("У тебя пока нет ни одного рецепта. Попробуй добавить его!")
        else:
            keyboard = get_recipe_list_keyboard("show_recipe")
            await callback.message.answer("Выбери рецепт, чтобы посмотреть его:", reply_markup=keyboard)

    elif action == "edit_recipe":
        if not RECIPES:
            await callback.message.answer("У тебя нет рецептов для редактирования.")
        else:
            keyboard = get_recipe_list_keyboard("select_to_edit")
            await callback.message.answer("Какой рецепт хочешь отредактировать?", reply_markup=keyboard)

    elif action == "delete_recipe":
        if not RECIPES:
            await callback.message.answer("У тебя нет рецептов для удаления.")
        else:
            keyboard = get_recipe_list_keyboard("delete_recipe_confirm")
            await callback.message.answer("Какой рецепт хочешь удалить?", reply_markup=keyboard)

    elif action == "show_recipe":
        recipe_name = data[1]
        recipe = RECIPES.get(recipe_name)
        if recipe:
            message_text = f"**{recipe_name}**\n\n**Ингредиенты:**\n{recipe['ingredients']}\n\n**Инструкция:**\n{recipe['instructions']}"
            await callback.message.answer(message_text, parse_mode='Markdown')
        else:
            await callback.message.answer("Извини, этот рецепт не найден.")

    elif action == "delete_recipe_confirm":
        recipe_name = data[1]
        if recipe_name in RECIPES:
            del RECIPES[recipe_name]
            save_recipes(RECIPES)
            await callback.message.answer(f"Рецепт '{recipe_name}' был успешно удалён. 🗑️")
        else:
            await callback.message.answer("Этот рецепт уже был удален.")

    elif action == "select_to_edit":
        recipe_name = data[1]
        if recipe_name in RECIPES:
            await state.update_data(recipe_name=recipe_name)
            keyboard = get_edit_recipe_keyboard(recipe_name)
            await callback.message.answer(f"Что ты хочешь изменить в рецепте '{recipe_name}'?", reply_markup=keyboard)
        else:
            await callback.message.answer("Этот рецепт не найден.")

    elif action == "edit_part":
        _, recipe_name, part = data
        await state.update_data(recipe_name=recipe_name, part_to_edit=part)
        await state.set_state(EditRecipeState.new_value)
        await callback.message.answer(f"Хорошо, введи новое значение для '{part}'.")


# Обработчики состояний для добавления и редактирования
@dp.message(AddRecipeState.name)
async def process_recipe_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddRecipeState.ingredients)
    await message.reply("Отлично! Теперь напиши **ингредиенты** (каждый с новой строки).")


@dp.message(AddRecipeState.ingredients)
async def process_ingredients(message: types.Message, state: FSMContext):
    await state.update_data(ingredients=message.text)
    await state.set_state(AddRecipeState.instructions)
    await message.reply("И последний шаг! Напиши **инструкцию по приготовлению**.")


@dp.message(AddRecipeState.instructions)
async def process_instructions(message: types.Message, state: FSMContext):
    await state.update_data(instructions=message.text)
    user_data = await state.get_data()
    recipe_name = user_data.get("name")

    RECIPES[recipe_name] = {
        "ingredients": user_data.get("ingredients"),
        "instructions": user_data.get("instructions")
    }
    save_recipes(RECIPES)
    await state.clear()
    await message.reply(f"Рецепт '{recipe_name}' успешно добавлен! 🎉")


@dp.message(EditRecipeState.new_value)
async def process_new_value(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    recipe_name = user_data.get('recipe_name')
    part_to_edit = user_data.get('part_to_edit')

    if recipe_name in RECIPES:
        if part_to_edit == 'name':
            new_name = message.text
            RECIPES[new_name] = RECIPES.pop(recipe_name)
            await message.reply(f"Название рецепта изменено на '{new_name}'!")
        else:
            RECIPES[recipe_name][part_to_edit] = message.text
            await message.reply(f"Значение для '{part_to_edit}' в рецепте '{recipe_name}' обновлено!")

        save_recipes(RECIPES)
    else:
        await message.reply("Извините, произошла ошибка. Рецепт не найден.")

    await state.clear()


# Основная асинхронная функция для запуска бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())
