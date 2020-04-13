import logging
import random
import string
from operator import itemgetter
from telegram import InlineKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
from telegram.ext import CallbackQueryHandler

BOT_ID = 1105629394

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

token_file = open("token.txt", "r")
token = token_file.readline().rstrip('\n')
updater = Updater(token=token, use_context=True)
token_file.close()
dispatcher = updater.dispatcher

phrases = ["вещий сон", "вечный сон", "несбывшаяся надежда",
           "пальмовое масло", "прогрессивная любовь", "реверсивная психология",
           "литературный хулиган", "солнечный луч", "голый король",
           "героиновый сон", "водяной пистолет", "цыганский табор",
           "коварный сон", "идеальный люди", "долбаная жизнь",
           "мебельный гипермаркет", "черно-белый фильм", "кислотные вставки",
           "жуткая ночь", "теплая пасть", "героиновый торч",
           "наглядный пример", "высокая ставка", "грубая ошибка"]

def get_phrase():
    return phrases[random.randint(0, len(phrases) - 1)]

def get_phrases(amount):
    res = []
    for i in range(amount):
        res.append(get_phrase())
    return res

games = dict()

def user_name(user):
    res = user.first_name
    if user.last_name is not None:
        res += ' ' + user.last_name
    return res

def print_top(update, context, top):
    group_id = update.effective_chat.id
    message_text = 'Топ 10 по количеству побед:\n'
    for place in top:
        message_text += user_name(place[0]) + ' — ' + str(place[1]) + '\n'
    context.bot.send_message(chat_id=group_id, text=message_text)

class Game:

    def __init__(self, lang, rounds):
        self.lang = lang
        self.rounds = rounds
        self.words_options = []
        self.words = []
        self.participants = dict() # user to wins
        self.top = []
        self.leader_candidates = set()
        self.leader_id = None
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
        games[group_id].participants[update.effective_user] = 0
        games[group_id].leader_candidates.add(update.effective_user)

def join_game(update, context):
    group_id = update.effective_chat.id
    user = update.effective_user
    if group_id not in games:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игры')
        return
    if user in games[group_id].participants:
        context.bot.send_message(chat_id=group_id, text=user_name(user) + ', ты уже в игре')
        return
    games[group_id].participants[update.effective_user] = 0
    games[group_id].leader_candidates.add(user)
    context.bot.send_message(chat_id=group_id, text=user_name(user) + ' присоединился к игре!')

def start_round(update, context):
    group_id = update.effective_chat.id
    user = update.effective_user
    if group_id not in games:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игры!')
        return
    if games[group_id].round_going:
        context.bot.send_message(chat_id=group_id, text='В этом чате уже идет раунд!')
        return
    if user not in games[group_id].participants:
        context.bot.send_message(chat_id=group_id, text=user_name(user) + ', сначала присоединись к игре!')
        return
    games[group_id].round_going = True
    if len(games[group_id].leader_candidates) == 0:
        games[group_id].leader_candidates = set(games[group_id].participants.keys())
    leader = random.choice(tuple(games[group_id].leader_candidates))
    games[group_id].leader_candidates.remove(leader)
    games[group_id].leader_id = leader.id
    phrases_amount = 6
    options = get_phrases(phrases_amount)
    keyboard_markup = InlineKeyboardMarkup([[], []])
    for i in range(phrases_amount):
        games[group_id].words_options.append(str(i + 1) + '. ' + options[i])
        keyboard_markup.inline_keyboard[1].append(InlineKeyboardButton(str(i + 1), callback_data=str(i + 1)))
    keyboard_markup.inline_keyboard[0].append(InlineKeyboardButton("Посмотреть слова",
                                                                   callback_data="words"))
    context.bot.send_message(chat_id=group_id, text='Раунд начался, ведущим был выбран ' + user_name(leader),
                                 reply_markup=keyboard_markup)

def stop_game(update, context):
    group_id = update.effective_chat.id
    if group_id in games:
        context.bot.send_message(chat_id=group_id, text='Игра окончена!')
        games.pop(group_id)
    else:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игра!')

def check_message(update, context):
    group_id = update.effective_chat.id
    if group_id not in games:
        return
    if not games[group_id].round_going:
        return
    user_id = update.effective_user.id
    text = update.message.text.split()
    for i in range(len(text)):
        text[i] = text[i].translate(str.maketrans(dict.fromkeys(string.punctuation)))
        text[i] = text[i].lower()
    if user_id == games[group_id].leader_id:
        must_do = 'something'
        # TODO leader logic
    elif update.effective_user in games[group_id].participants:
        if update.message.text.lower() == ' '.join(games[group_id].words):
            games[group_id].round_going = False
            games[group_id].words_options = []
            games[group_id].words = []
            context.bot.send_message(chat_id=group_id, text=user_name(update.effective_user) + ' угадал!')
            games[group_id].participants[update.effective_user] += 1
            found = False
            for i in range(len(games[group_id].top)):
                if games[group_id].top[i][0].id == user_id:
                    games[group_id].top[i][1] += 1
                    found = True
                    break
            if not found:
                games[group_id].top.append([update.effective_user, games[group_id].participants[update.effective_user]])
            games[group_id].top.sort(key=itemgetter(1), reverse=True)
            games[group_id].top = games[group_id].top[:10]
            print_top(update, context, games[group_id].top)
            if games[group_id].top[0][1] == games[group_id].rounds:
                context.bot.send_message(chat_id=group_id, text=user_name(games[group_id].top[0][0]) + 'победил!')
                stop_game(update, context)
            else:
                start_round(update, context)
            return
        guessed = 0
        for word in text:
            if word in games[group_id].words:
                guessed += 1
        if guessed > 0:
            msg = user_name(update.effective_user) + ' угадал ' + str(guessed)
            if guessed == 1:
                msg += ' слово!'
            elif 2 <= guessed <= 4:
                msg += ' слова!'
            else:
                msg += ' слов!'
            context.bot.send_message(chat_id=group_id, text=msg)

def check_callback(update, context):
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    callback = update.callback_query
    if group_id not in games:
        context.bot.answer_callback_query(callback_query_id=callback.id, text='Игра кончилась!', show_alert=True)
        return
    if user_id != games[group_id].leader_id:
        context.bot.answer_callback_query(callback_query_id=callback.id, text='Ты не ведущий!', show_alert=True)
        return
    if callback.data is None:
        return
    if callback.data == "words":
        if len(games[group_id].words) == 0:
            print('\n'.join(games[group_id].words_options))
            context.bot.answer_callback_query(callback_query_id=callback.id,
                                              text='\n'.join(games[group_id].words_options), show_alert=True)
        else:
            context.bot.answer_callback_query(callback_query_id=callback.id,
                                              text='Ты должен объяснить \"' + ' '.join(games[group_id].words) + '\"',
                                              show_alert=True)
    elif len(games[group_id].words) > 0:
        context.bot.answer_callback_query(callback_query_id=callback.id, text='Ты уже выбрал слово!', show_alert=True)
    else:
        choice = int(callback.data) - 1
        games[group_id].words = games[group_id].words_options[choice].split()[1:]
        context.bot.answer_callback_query(callback_query_id=callback.id,
                                 text='Теперь ты должен объяснить \"' + ' '.join(games[group_id].words) + '\"',
                                          show_alert=True)

start_game_handler = CommandHandler('start_game', start_game)
dispatcher.add_handler(start_game_handler)
join_game_handler = CommandHandler('join_game', join_game)
dispatcher.add_handler(join_game_handler)
start_round_handler = CommandHandler('start_round', start_round)
dispatcher.add_handler(start_round_handler)
stop_game_handler = CommandHandler('stop_game', stop_game)
dispatcher.add_handler(stop_game_handler)
msg_handler = MessageHandler(Filters.text, check_message)
dispatcher.add_handler(msg_handler)
callback_handler = CallbackQueryHandler(check_callback)
dispatcher.add_handler(callback_handler)

updater.start_polling()