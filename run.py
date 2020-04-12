from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
import logging
import random
import string
from telegram import ForceReply

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

class ForceChoosePhrase(ForceReply):

    def __init__(self, group_id, options, **kwargs):
        super().__init__(**kwargs)
        self.group_id = group_id
        self.options = options


class Game:

    def __init__(self, lang, rounds):
        self.lang = lang
        self.rounds = rounds
        self.words = []
        self.participants = set()
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
        games[group_id].participants.add(update.effective_user)

def join_game(update, context):
    group_id = update.effective_chat.id
    user = update.effective_user
    if group_id not in games:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игры')
    games[group_id].participants.add(user)
    context.bot.send_message(chat_id=group_id, text=user_name(user) + ' присоединился к игре!')

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
    games[group_id].leader_id = leader.id
    context.bot.send_message(chat_id=group_id, text='Раунд начался, ведущим был выбран ' + user_name(leader))
    phrases_amount = 6
    options = get_phrases(phrases_amount)
    message_with_options = str(group_id) + '\n'
    message_with_options += 'Отправь мне цифру, соответствующую фразе, которую хочешь объяснять:\n'
    for i in range(phrases_amount):
        message_with_options += str(i + 1) + '. ' + options[i] + '\n'
    context.bot.send_message(chat_id=leader.id, text=message_with_options,
                             reply_markup=ForceChoosePhrase(group_id, options)) # TODO bot may be unathorized to send msg to that user

def stop_game(update, context):
    group_id = update.effective_chat.id
    if group_id in games:
        context.bot.send_message(chat_id=group_id, text='Игра окончена!')
        games.pop(group_id)
    else:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игра!')

def check_message(update, context):
    group_id = update.effective_chat.id
    if update.message.reply_to_message is not None and update.message.reply_to_message.from_user.id == BOT_ID:
        try:
            int_text = int(update.message.text)
        except ValueError:
            context.bot.send_message(chat_id=group_id, text='Выбор не является цифрой, выбираем 1')
            int_text = 1
        lines = update.message.reply_to_message.text.split('\n')
        choice_group_id = int(lines[0])
        if 1 <= int_text <= 6:
            games[choice_group_id].words = lines[int_text + 1][3:].split()
        else:
            context.bot.send_message(chat_id=group_id, text='Выбор не является цифрой от 1 до 6, выбираем 1')
            games[choice_group_id].words = lines[int_text + 1][3:].split()
        print(games[choice_group_id].words)
        print(choice_group_id)
        return
    if group_id not in games:
        return
    if not games[group_id].round_going:
        return
    user_id = update.effective_user.id
    text = update.message.text.split()
    for i in range(len(text)):
        text[i].translate(str.maketrans('', '', string.punctuation))
        text[i] = text[i].lower()
    if user_id == games[group_id].leader_id:
        must_do = 'something'
        # TODO leader logic
    elif update.effective_user in games[group_id].participants:
        if update.message.text.lower() == ' '.join(games[group_id].words):
            games[group_id].round_going = False
            context.bot.send_message(chat_id=group_id, text=user_name(update.effective_user) + ' угадал!')
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

updater.start_polling()