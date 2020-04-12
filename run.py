from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
import logging
import random

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

token_file = open("token.txt", "r")
token = token_file.readline().rstrip('\n')
updater = Updater(token=token, use_context=True)
token_file.close()
dispatcher = updater.dispatcher

phrases = ["вещий сон", "вечный сон", "несбывшаяся надежда",
           "пальмовое масло", "прогрессивная любовь", "реверсивная психология",
           "литературный хулиган", "солнечный луч", "голый король"]

def get_phrase():
    return phrases[random.randint(0, len(phrases) - 1)]

def get_phrases(amount):
    res = []
    for i in range(amount):
        res.append(get_phrase())
    return res

games = dict()

class Game:

    def __init__(self, lang, rounds):
        self.lang = lang
        self.rounds = rounds
        self.words = []
        self.participants = set()
        self.round_going = False

def start_game(update, context):
    group_id = update.effective_chat.id
    if group_id in games:
        context.bot.send_message(chat_id=group_id, text='Игра уже идет в этом чате!')
    else:
        if len(context.args) < 2:
            context.bot.send_message(chat_id=group_id, text='Введите язык и кол-во раундов')
            return
        lang = context.args[0]
        if lang != "ru":
            context.bot.send_message(chat_id=group_id, text='Введите другой язык (пока поддерживаем только ru)')
            return
        try:
            wins = int(context.args[1])
        except ValueError:
            context.bot.send_message(chat_id=group_id, text='Число раундов не является числом')
            return
        if wins < 1 or wins > 100000:
            context.bot.send_message(chat_id=group_id, text='Число раундов должно быть от 1 до 100000')
            return
        context.bot.send_message(chat_id=group_id, text='Игра на языке ' + lang +
                                                        ' до ' + str(wins) + ' побед началась!')
        games[group_id] = Game(lang, wins)

def join_game(update, context):
    group_id = update.effective_chat.id
    user = update.effective_user
    if group_id not in games:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игры')
    games[group_id].participants.add(user)

def start_round(update, context):
    group_id = update.effective_chat.id
    if group_id not in games:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игры!')
        return
    if games[group_id].round_going:
        context.bot.send_message(chat_id=group_id, text='В этом чате уже идет раунд!')
        return
    games[group_id].round_going = True
    user = update.effective_user
    games[group_id].participants.add(user)
    leader = list(games[group_id].participants)[random.randint(0, len(games[group_id].participants) - 1)]
    user_name = user.first_name
    if user.last_name is not None:
        user_name += ' ' + user.last_name
    context.bot.send_message(chat_id=group_id, text='Раунд начался, ведущим был выбран ' + user_name)
    phrases_amount = 6
    options = get_phrases(phrases_amount)
    message_with_options = 'Отправь мне цифру, соответствующую фразе, которую хочешь объяснять:\n'
    for i in range(phrases_amount):
        message_with_options += str(i + 1) + '. ' + options[i] + '\n'
    context.bot.send_message(chat_id=user.id, text=message_with_options)

def stop_game(update, context):
    group_id = update.effective_chat.id
    if group_id in games:
        context.bot.send_message(chat_id=group_id, text='Игра окончена!')
        games.pop(group_id)
    else:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игра!')

start_game_handler = CommandHandler('start_game', start_game)
dispatcher.add_handler(start_game_handler)
join_game_handler = CommandHandler('join_game', join_game)
dispatcher.add_handler(join_game_handler)
start_round_handler = CommandHandler('start_round', start_round)
dispatcher.add_handler(start_round_handler)
stop_game_handler = CommandHandler('stop_game', stop_game)
dispatcher.add_handler(stop_game_handler)

# echo_handler = MessageHandler(Filters.text, echo)
# dispatcher.add_handler(echo_handler)

updater.start_polling()