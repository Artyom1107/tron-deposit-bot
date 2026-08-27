import os
import re
import logging
import httpx
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from httpx import URL

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение переменных окружения
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TRONSCAN_API_KEY = os.environ.get('TRONSCAN_API_KEY', '')
PROXY_URL = os.environ.get('PROXY_URL')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is required")
if not PROXY_URL:
    raise ValueError("PROXY_URL environment variable is required")

# Паттерн для TRON TXID (начинается с T, затем 62 hex-символа)
TRON_TXID_PATTERN = re.compile(r'^T[A-Za-z0-9]{33}$')

# Tronscan API endpoint
TRONSCAN_API_URL = "https://apilist.tronscan.org/api/transaction-info"

def get_proxy_dict() -> dict:
    """Конвертирует PROXY_URL в формат, понятный библиотеке requests"""
    return {'http': PROXY_URL, 'https': PROXY_URL}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    welcome_message = (
        "🤖 <b>TRON Deposit Checker Bot</b>\n\n"
        "Send me a TRON transaction ID to check its deposit status.\n\n"
        "<b>How to use:</b>\n"
        "• Simply send a TRON transaction ID (starts with T)\n"
        "• Example: Txxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n\n"
        "I will check the status and provide details about the transaction."
    )
    await update.message.reply_text(welcome_message, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /help"""
    help_message = (
        "❓ <b>Help - TRON Deposit Checker</b>\n\n"
        "<b>Supported commands:</b>\n"
        "• /start - Show welcome message\n"
        "• /help - Show this help message\n\n"
        "<b>Usage:</b>\n"
        "• Send a valid TRON transaction ID (34 characters, starts with T)\n"
        "• I will fetch and display the transaction details\n\n"
        "<b>Information provided:</b>\n"
        "• Status (Confirmed/Pending/Reverted)\n"
        "• Block Height\n"
        "• Confirmations\n"
        "• From Address\n"
        "• To Address\n"
        "• Timestamp"
    )
    await update.message.reply_text(help_message, parse_mode='HTML')

async def check_tron_transaction(txid: str) -> str:
    """Проверяет статус транзакции через Tronscan API через прокси"""
    try:
        params = {'hash': txid}
        if TRONSCAN_API_KEY:
            params['api_key'] = TRONSCAN_API_KEY
            
        response = requests.get(
            TRONSCAN_API_URL, 
            params=params, 
            proxies=get_proxy_dict(),
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if not data or 'confirmed' not in data:
            return f"❌ Transaction {txid} not found or invalid."
            
        status = "✅ Confirmed" if data.get('confirmed') else "⏳ Pending"
        if data.get('revert'):
            status = " Reverted"
            
        block = data.get('block', 'N/A')
        confirmations = data.get('confirmations', 0)
        from_addr = data.get('fromAddress', 'N/A')[:10] + "..."
        to_addr = data.get('toAddress', 'N/A')[:10] + "..."
        timestamp = data.get('timestamp', 0)
        
        return (
            f" <b>Transaction Report</b>\n\n"
            f"<b>Txid:</b> <code>{txid}</code>\n"
            f"<b>Status:</b> {status}\n"
            f"<b>Block:</b> {block}\n"
            f"<b>Confirmations:</b> {confirmations}\n"
            f"<b>From:</b> {from_addr}\n"
            f"<b>To:</b> {to_addr}\n"
            f"<b>Time:</b> {timestamp}"
        )
    except requests.exceptions.ProxyError:
        return "❌ Proxy connection failed. Please check PROXY_URL."
    except requests.exceptions.Timeout:
        return "❌ Tronscan API timeout. Try again later."
    except Exception as e:
        logger.error(f"Error checking transaction {txid}: {e}")
        return f"❌ Error: {str(e)}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (TXID)"""
    text = update.message.text.strip()
    
    if TRON_TXID_PATTERN.match(text):
        await update.message.reply_text("⏳ Checking transaction status...")
        result = await check_tron_transaction(text)
        await update.message.reply_text(result, parse_mode='HTML')
    else:
        await update.message.reply_text(
            "❌ Invalid TRON Transaction ID.\n"
            "Please send a valid ID starting with 'T' (34 characters total)."
        )

def main():
    """Запуск бота с правильной инициализацией прокси"""
    # КРИТИЧЕСКИ ВАЖНО: Оборачиваем строку прокси в объект URL для httpx
    httpx_request = HTTPXRequest(proxy=URL(PROXY_URL))
    
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .request(httpx_request)
        .build()
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot started successfully with SOCKS5 proxy support.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()