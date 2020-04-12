from telegram.ext import Updater
from telegram.ext import CommandHandler
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

token_file = open("token.txt", "r")
token = token_file.readline().rstrip('\n')
updater = Updater(token=token, use_context=True)
token_file.close()
dispatcher = updater.dispatcher

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

updater.start_polling()