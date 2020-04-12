from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
import logging
import random

phrases = ["вещий сон", "вечный сон", "несбывшаяся надежда",
           "пальмовое масло", "прогрессивная любовь", "реверсивная психология",
           "литературный хулиган", "солнечный луч", "голый король"]

games = dict()

class Game:

    def __init__(self, phrase):
        self.words = phrase.split()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

token_file = open("token.txt", "r")
token = token_file.readline().rstrip('\n')
updater = Updater(token=token, use_context=True)
token_file.close()
dispatcher = updater.dispatcher

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

def echo(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

def get_phrase():
    return phrases[random.randint(0, len(phrases) - 1)]

def get_phrases(amount):
    res = []
    for i in range(amount):
        res.append(get_phrase())

def start_game(update, context):
    group_id = update.effective_chat.id
    if group_id in games:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Игра уже идет в этом чате!")
    else:
        games[group_id] = Game(get_phrase())
        context.bot.send_message(chat_id=update.effective_chat.id, text="Игра началась!")

def get_word(update, context):
    group_id = update.effective_chat.id
    if group_id not in games:
        context.bot.send_message(chat_id=update.effective_chat.id, text='В этом чате не идет игры!')
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=' '.join(games[group_id].words))

def stop_game(update, context):
    group_id = update.effective_chat.id
    if group_id in games:
        context.bot.send_message(chat_id=update.effective_chat.id, text='Игра окончена!')
        games.pop(group_id)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text='В этом чате не идет игра!')

start_game_handler = CommandHandler('start_game', start_game)
dispatcher.add_handler(start_game_handler)
stop_game_handler = CommandHandler('stop_game', stop_game)
dispatcher.add_handler(stop_game_handler)
get_word_handler = CommandHandler('get_word', get_word)
dispatcher.add_handler(get_word_handler)

# echo_handler = MessageHandler(Filters.text, echo)
# dispatcher.add_handler(echo_handler)

updater.start_polling()