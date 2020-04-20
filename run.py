import logging
import random
import json
import string
import threading
import urllib.request
import spacy
from tinydb import TinyDB, Query
from tinydb.operations import add
from urllib.parse import quote
from urllib.error import HTTPError
import pymorphy2
from operator import itemgetter
from telegram import InlineKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram import ParseMode
from telegram import ForceReply
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
from telegram.ext import CallbackQueryHandler

BOT_ID = 1105629394
START_STRING = ', введи язык и количество раундов в формате "<ru или en\> <число от 1 до 100000\>"\. Прочитать' \
               ' правила игры: /rules'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

token_file = open("token.txt", "r")
token = token_file.readline().rstrip('\n')
updater = Updater(token=token, use_context=True)
token_file.close()
dispatcher = updater.dispatcher

morph = pymorphy2.MorphAnalyzer()
nlp = spacy.load('en_core_web_sm')

phrases_ru = []
phrases_file = open('phrases_ru.txt', 'r', encoding='utf-8')
for line in phrases_file:
    phrases_ru.append(line.rstrip('\n'))
phrases_file.close()
print('Done reading phrases from file')

phrases_en = []
phrases_file = open('phrases_en.txt', 'r', encoding='utf-8')
for line in phrases_file:
    phrases_en.append(line.rstrip('\n'))
phrases_file.close()
print('Done reading phrases from file')


def get_phrase(lang):
    if lang == 'ru':
        return phrases_ru[random.randint(0, len(phrases_ru) - 1)]
    else:
        return phrases_en[random.randint(0, len(phrases_en) - 1)]


def get_phrases(amount, lang):
    res = []
    try:
        req = urllib.request.urlopen('https://play-name.com/PlayEngine/api/', data=str.encode('lang=' + lang))
        words = json.loads(req.read().decode('utf-8'))
        for word in words[lang].keys():
            res.append(word)
            if len(res) == amount:
                break
    except (HTTPError, json.JSONDecodeError) as e:
        for i in range(amount):
            res.append(get_phrase(lang))
    return res


games = dict()
db = TinyDB('db.json')
if not db.search(Query().groups.exists()):
    db.insert({'groups': 1})
if not db.search(Query().games.exists()):
    db.insert({'games': 0})
if not db.search(Query().rounds.exists()):
    db.insert({'rounds': 0})
if not db.search(Query().joins.exists()):
    db.insert({'joins': 0})

def escape_markdown(s, escape_star=True):
    markdown = '_*[]()~`>#+-=|{}.!'
    res = ''
    for c in s:
        if c == '*' and not escape_star:
            res += '*'
            continue
        if c in markdown:
            res += '\\'
        res += c
    return res


def user_name(user, mention=False):
    res = user.first_name
    if user.last_name is not None:
        res += ' ' + user.last_name
    if mention:
        return '[' + escape_markdown(res) + '](tg://user?id=' + str(user.id) + ')'
    else:
        return res


def normalize(s):
    return s.translate(str.maketrans(dict.fromkeys(string.punctuation))).lower()


def get_normal_form(s, lang):
    if lang == 'ru':
        return morph.parse(s.lower())[0].normal_form
    elif lang == 'en':
        return nlp(s.lower())[0].lemma_


def get_roots(s, lang):
    norm = get_normal_form(s, lang)
    if lang == 'en':
        return norm
    if len(norm) == 0:
        return []
    try:
        url = 'http://morphemeonline.ru/' + quote(norm[0].upper() + '/' + norm)
        req = urllib.request.urlopen(url)
    except HTTPError:
        return []
    page_code = req.read().decode('utf-8')
    index = 0
    roots = []
    while index < len(page_code):
        pos = page_code.find('title="корень"', index)
        if pos == -1:
            break
        pos += len('title="корень"') + 1
        root = ''
        while page_code[pos] != '<':
            root += page_code[pos]
            pos += 1
        index = pos
        roots.append(root)
    return roots


def check_roots(root1, root2, lang):
    if lang == 'ru':
        TOO_SHORT = 3
        min_len = min(len(root1), len(root2))
        if min_len <= TOO_SHORT:
            return root1 == root2
        else:
            lcp = 0
            while lcp < min_len:
                if root1[lcp] == root2[lcp]:
                    lcp += 1
                else:
                    break
            return lcp + 1 >= min_len
    elif lang == 'en':
        return root1 == root2
# TODO improve


def print_top(update, context, top):
    group_id = update.effective_chat.id
    message_text = 'Топ 10 по количеству очков:\n'
    for place in top:
        message_text += user_name(place[0]) + ' — ' + str(place[1]) + '\n'
    context.bot.send_message(chat_id=group_id, text=message_text)


def send_start_game_message(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=user_name(update.effective_user, mention=True) + START_STRING,
                             reply_markup=ForceReply(selective=True),
                             parse_mode=ParseMode.MARKDOWN_V2)


def end_round(group_id):
    game = games[group_id]
    game.round_going = False
    game.words_options = []
    game.words = []
    game.guessed = []
    game.roots = []
    if game.timer is not None:
        game.timer.cancel()


def restart_round(update, context):
    group_id = update.effective_chat.id
    context.bot.send_message(chat_id=group_id, text='Ведущий слишком долго был неактивным, начинаем новый раунд')
    end_round(group_id)
    start_round(update, context, True)


def add_points(group_id, user, score):
    game = games[group_id]
    game.participants[user] += score
    found = False
    for i in range(len(game.top)):
        if game.top[i][0].id == user.id:
            game.top[i][1] += score
            found = True
            break
    if not found:
        game.top.append([user, game.participants[user]])
    game.top.sort(key=itemgetter(1), reverse=True)
    game.top = game.top[:10]


class Game:

    def __init__(self, lang, rounds):
        self.lang = lang
        self.rounds = rounds
        self.words_options = []
        self.words = []
        self.guessed = []
        self.roots = []
        self.participants = dict()  # user to wins
        self.top = []
        self.leader_candidates = set()
        self.leader = None
        self.round_going = False
        self.starter_id = None
        self.timer = None


def start_game(update, context):
    group_id = update.effective_chat.id
    if group_id in games:
        context.bot.send_message(chat_id=group_id, text='Игра уже идет в этом чате!')
    else:
        db.update(add('games', 1), Query().games.exists())
        send_start_game_message(update, context)


def join_game(update, context, secondary=False, callback_user=None):
    group_id = update.effective_chat.id
    if secondary:
        user = callback_user
    else:
        user = update.effective_user
    if group_id not in games:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игры')
        return
    game = games[group_id]
    if user in game.participants:
        context.bot.send_message(chat_id=group_id, text=user_name(user) + ', ты уже в игре')
        return
    game.participants[update.effective_user] = 0
    game.leader_candidates.add(user)
    db.update(add('joins', 1), Query().joins.exists())
    context.bot.send_message(chat_id=group_id, text=user_name(user) + ' присоединился к игре!')


def start_round(update, context, secondary=False):
    group_id = update.effective_chat.id
    user = update.effective_user
    if group_id not in games:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игры!')
        return
    game = games[group_id]
    if game.round_going:
        context.bot.send_message(chat_id=group_id, text='В этом чате уже идет раунд!')
        return
    if not secondary and user not in game.participants:
        context.bot.send_message(chat_id=group_id, text=user_name(user) + ', сначала присоединись к игре!')
        return
    if not secondary:
        db.update(add('rounds', 1), Query().rounds.exists())
    if len(game.leader_candidates) == 0:
        game.leader_candidates = set(game.participants.keys())
    leader = random.choice(tuple(game.leader_candidates))
    game.leader_candidates.remove(leader)
    game.leader = leader
    phrases_amount = 6
    options = get_phrases(phrases_amount, game.lang)
    keyboard_markup = InlineKeyboardMarkup([[], []])
    for i in range(phrases_amount):
        game.words_options.append(str(i + 1) + '. ' + options[i])
        keyboard_markup.inline_keyboard[1].append(InlineKeyboardButton(str(i + 1), callback_data=str(i + 1)))
    keyboard_markup.inline_keyboard[0].append(InlineKeyboardButton("Посмотреть слова",
                                                                   callback_data="words"))
    context.bot.send_message(chat_id=group_id,
                             text='Раунд начался, ведущим был выбран ' + user_name(leader, mention=True),
                             reply_markup=keyboard_markup, parse_mode=ParseMode.MARKDOWN_V2)
    game.timer = threading.Timer(60.0, restart_round, args=[update, context])
    game.timer.start()


def leave_game(update, context):
    group_id = update.effective_chat.id
    if group_id not in games:
        return
    game = games[group_id]
    user = update.effective_user
    res = game.participants.pop(user, None)
    game.leader_candidates.discard(user)
    if res is not None:
        context.bot.send_message(chat_id=group_id, text=user_name(user) + ' покинул игру')
        if len(game.participants) == 0:
            context.bot.send_message(chat_id=group_id, text='Последний игрок покинул игру, завершаемся :(')
            stop_game(update, context, secondary=True)
            return
        if user.id == game.starter_id:
            new_starter = random.choice(tuple(game.participants.keys()))
            game.starter_id = new_starter.id
            context.bot.send_message(chat_id=group_id,
                                     text='Администратор игры ее покинул, теперь это '
                                          + user_name(new_starter, mention=True), parse_mode=ParseMode.MARKDOWN_V2)
        if user.id == game.leader.id:
            end_round(group_id)
            context.bot.send_message(chat_id=group_id, text=user_name(user) + ' был ведущим, начинаем новый раунд')
            start_round(update, context, secondary=True)


def stop_game(update, context, secondary=False):
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    if group_id in games:
        game = games[group_id]
        if secondary:
            user_id = game.starter_id
        allowed = False
        if user_id == game.starter_id:
            allowed = True
        else:
            admins = context.bot.get_chat_administrators(chat_id=group_id)
            for admin in admins:
                if user_id == admin.user.id:
                    allowed = True
                    break
        if allowed:
            if game.timer is not None:
                game.timer.cancel()
            context.bot.send_message(chat_id=group_id, text='Игра окончена!')
            games.pop(group_id)
        else:
            context.bot.send_message(chat_id=group_id, text='Игру может завершить только '
                                                            'администратор игры или чата')
    else:
        context.bot.send_message(chat_id=group_id, text='В этом чате не идет игра!')


def rules(update, context):
    rules_msg = '*Правила игры:* 🐊 \n\n' \
                '*1.* Все команды доступны при введении символа / \n' \
                '*2.* Чтобы начать игру, напишите /start_game и следуйте инструкциям \n' \
                '*3.* Чтобы присоединиться к игре, напишите /join_game \n' \
                '*4.* Минимальное количество людей: 2 пользователя \n' \
                '*5.* Начать раунд: /start_round \n' \
                '*6.* *Правила игры*: После этого случайным образом выберется ведущий. Ему нужно будет посмотреть' \
                ' предложенные ему словосочетания, нажав на кнопку *"Посмотреть слова"*, а затем выбрать одно из них, ' \
                'нажав на кнопку с соответствующей цифрой. После этого сменить выбор будет нельзя, а выбранное ' \
                'словосочетание можно будет посмотреть, нажав на любую из кнопок. \n' \
                '*7.* Если ведущий не выберет слово в течение *одной минуты*, случайным образом выберется другой ведущий.\n' \
                '*8.* Сама игра происходит таким образом: игроки могут спрашивать у ведущего про выбранное ' \
                'им словосочетание, а ведущий может отвечать на них, *не используя однокоренные с загаданными слова*. ' \
                'Если он использует однокоренное, то раунд закончится, а ведущим станет другой игрок. \n' \
                '*9.* *Альтернативный вариант:* ведущий может просто объяснять загаданные слова, а игроки пытаться угадать.\n' \
                '*10.* Как только кто-то из игроков написал несколько из загаданных слов, ему начислится столько же очков, ' \
                'а отгаданные слова откроются. Если кто-то из игроков произнесет уже угаданные слова, ' \
                'то ему ничего за них не начислится. Как только будут отгаданы все слова, ведущему за старания ' \
                'начислится одно очко, и автоматически начнется следующий раунд, где будет выбран уже другой ведущий. \n' \
                '*11.* Если ведущий больше не может объяснять, и хочет сдаться, он может написать /give_up' \
                '*12.* Если ведущий ничего не будет писать в течение 5 минут, он посчитается покинувшим игру и ' \
                'будет выбран другой ведущий.' \
                '*13.* Для того, чтобы покинуть игру, наберите /leave_game  ' \
                '(если кому-то надоело играть и чтобы его не выбирало ведущим)\n' \
                '*14.* Если вдруг понадобилось досрочно закончить игру, администраторы чата и игрок, стартовавший игру, ' \
                '("администратор игры") могут сделать это с помощью /stop_game'
    context.bot.send_message(chat_id=update.effective_chat.id, text=escape_markdown(rules_msg, escape_star=False),
                             parse_mode=ParseMode.MARKDOWN_V2)


def check_message(update, context):
    group_id = update.effective_chat.id
    if group_id not in games:
        replied = update.effective_message.reply_to_message
        if replied is not None:
            if replied.from_user.id == BOT_ID and replied.text.find(START_STRING) != 0:
                text = update.effective_message.text.split()
                if len(text) != 2:
                    send_start_game_message(update, context)
                else:
                    lang = text[0].lower()
                    if lang != "ru" and lang != "en":
                        send_start_game_message(update, context)
                        return
                    try:
                        wins = int(text[1])
                    except ValueError:
                        send_start_game_message(update, context)
                        return
                    if wins < 1 or wins > 100000:
                        send_start_game_message(update, context)
                        return
                    context.bot.send_message(chat_id=group_id, text='Игра на языке ' + lang + ' началась!',
                                             reply_markup=InlineKeyboardMarkup
                                             ([[InlineKeyboardButton('Присоединиться', callback_data='join')]]))
                    games[group_id] = Game(lang, wins)
                    game = games[group_id]
                    game.starter_id = update.effective_user.id
                    game.participants[update.effective_user] = 0
                    game.leader_candidates.add(update.effective_user)
        return
    game = games[group_id]
    if not game.round_going:
        return
    user_id = update.effective_user.id
    text = update.message.text.split()
    for i in range(len(text)):
        text[i] = normalize(text[i])
        text[i] = text[i].lower()
    if user_id == game.leader.id:
        game.timer.cancel()
        game.timer = threading.Timer(300, restart_round, args=[update, context])
        game.timer.start()
        for word in text:
            banned = False
            for root in get_roots(word, game.lang):
                for game_root in game.roots:
                    if check_roots(root, game_root, game.lang):
                        banned = True
                        break
            if banned:
                context.bot.send_message(chat_id=group_id, text='Ведущий использовал однокоренное слово :(\n' +
                                                                'Было загадано: ' + ' '.join(games[group_id].words)
                                                                + '\nНачинаем новый раунд')
                end_round(group_id)
                start_round(update, context, secondary=True)
    elif update.effective_user in game.participants:
        score = 0
        for word in text:
            norm_word = get_normal_form(word, game.lang)
            for i in range(len(game.words)):
                norm_game_word = get_normal_form(game.words[i], game.lang)
                if norm_word == norm_game_word:
                    if not game.guessed[i]:
                        score += 1
                        game.guessed[i] = True
                        for root in get_roots(game.words[i], game.lang):
                            try:
                                game.roots.remove(root)
                            except ValueError:
                                pass
        if score > 0:
            msg = user_name(update.effective_user) + ' угадал ' + str(score)
            if score == 1:
                msg += ' слово'
            elif 2 <= score <= 4:
                msg += ' слова'
            else:
                msg += ' слов'
            add_points(group_id, update.effective_user, score)
            context.bot.send_message(chat_id=group_id, text=msg)
            msg = 'На данный момент отгадано '
            for i in range(len(game.words)):
                if game.guessed[i]:
                    msg += game.words[i]
                else:
                    msg += '????'
                msg += ' '
            context.bot.send_message(chat_id=group_id, text=msg)
        if sum(game.guessed) == len(game.words):
            game.rounds -= 1
            end_round(group_id)
            context.bot.send_message(chat_id=group_id, text='Все слова отгаданы! Осталось раундов: ' + str(game.rounds))
            add_points(group_id, game.leader, 1)
            print_top(update, context, game.top)
            if game.rounds == 0:
                context.bot.send_message(chat_id=group_id, text='Игра окончена, ' +
                                                                user_name(game.top[0][0]) + ' победил!')
                stop_game(update, context, secondary=True)
            else:
                start_round(update, context, secondary=True)
            return


def check_callback(update, context):
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    callback = update.callback_query
    if group_id not in games:
        context.bot.answer_callback_query(callback_query_id=callback.id, text='Игра кончилась!', show_alert=True)
        return
    game = games[group_id]
    if callback.data is None:
        return
    if callback.data == 'join':
        join_game(update, context, secondary=True, callback_user=update.effective_user)
        return
    if user_id != game.leader.id:
        context.bot.answer_callback_query(callback_query_id=callback.id, text='Ты не ведущий!', show_alert=True)
        return
    if callback.data == "words":
        if len(game.words) == 0:
            context.bot.answer_callback_query(callback_query_id=callback.id,
                                              text='\n'.join(game.words_options), show_alert=True)
        else:
            context.bot.answer_callback_query(callback_query_id=callback.id,
                                              text='Ты должен объяснить \"' + ' '.join(game.words) + '\"',
                                              show_alert=True)
    elif len(game.words) > 0:
        context.bot.answer_callback_query(callback_query_id=callback.id,
                                          text='Ты должен объяснить \"' + ' '.join(game.words) + '\"',
                                          show_alert=True)
    else:
        choice = int(callback.data) - 1
        game.words = game.words_options[choice].split()[1:]
        context.bot.answer_callback_query(callback_query_id=callback.id,
                                          text='Теперь ты должен объяснить \"' + ' '.join(game.words) + '\"',
                                          show_alert=True)
        game.timer.cancel()
        game.timer = threading.Timer(300, restart_round, args=[update, context])
        game.timer.start()
        game.round_going = True
        for word in game.words:
            for root in get_roots(word, game.lang):
                game.roots.append(root)
        for word in game.words:
            game.guessed.append(False)


def give_up(update, context):
    group_id = update.effective_chat.id
    if group_id not in games:
        return
    game = games[group_id]
    user_id = update.effective_user.id
    if user_id != game.leader.id:
        context.bot.send_message(chat_id=group_id, text=user_name(user_id) + ', ты не ведущий...')
    end_round(group_id)
    start_round(update, context, secondary=True)


def start(update, context):
    if update.effective_chat.id < 0:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Привет! Чтобы узнать, как играть со мной, напиши /rules')
        db.update(add('groups', 1), Query().groups.exists())
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Добавить бота в чат: https://t.me/playnamegame_bot?startgroup=true')


def get_stats(update, context):
    msg = 'Добавлений в группы: '
    msg += str(db.search(Query().groups.exists())[0]['groups']) + '\n'
    msg += 'Начато игр: '
    msg += str(db.search(Query().games.exists())[0]['games']) + '\n'
    msg += 'Начато раундов (вручную): '
    msg += str(db.search(Query().rounds.exists())[0]['rounds']) + '\n'
    msg += 'Количество присоединений к игре: '
    msg += str(db.search(Query().joins.exists())[0]['joins'])
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)
start_game_handler = CommandHandler('start_game', start_game)
dispatcher.add_handler(start_game_handler)
join_game_handler = CommandHandler('join_game', join_game)
dispatcher.add_handler(join_game_handler)
start_round_handler = CommandHandler('start_round', start_round)
dispatcher.add_handler(start_round_handler)
leave_game_handler = CommandHandler('leave_game', leave_game)
dispatcher.add_handler(leave_game_handler)
stop_game_handler = CommandHandler('stop_game', stop_game)
dispatcher.add_handler(stop_game_handler)
give_up_handler = CommandHandler('give_up', give_up)
dispatcher.add_handler(give_up_handler)
rules_handler = CommandHandler('rules', rules)
dispatcher.add_handler(rules_handler)
get_stats_handler = CommandHandler('get___stats', get_stats)
dispatcher.add_handler(get_stats_handler)
msg_handler = MessageHandler(Filters.text, check_message)
dispatcher.add_handler(msg_handler)
callback_handler = CallbackQueryHandler(check_callback)
dispatcher.add_handler(callback_handler)

updater.start_polling()