from aiogram.fsm.state import State, StatesGroup

class SentToAdmin(StatesGroup):
    message = State()
    send = State()

class addNewAdmin(StatesGroup):
    ID = State()
    Name = State()

class Broadcast(StatesGroup):
    message = State()

class PhotoSend(StatesGroup):
    photo = State()
    group_photo = State()

class DeleteAdmin(StatesGroup):
    delete = State()

class add_necessary_follows(StatesGroup):
    title = State()
    follow_id = State()
    username = State()

class delete_necessary_follows(StatesGroup):
    delete_id = State()

class AddPost(StatesGroup):
    content = State()

class Settings(StatesGroup):
    frequency = State()