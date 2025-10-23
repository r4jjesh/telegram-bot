
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set TELEGRAM_TOKEN in your .env file")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

# Simple storage for scheduled jobs per chat (in memory)
chat_jobs = {}

# Conversation states for scheduling
WHEN = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm GrowthHelperBot.\n"
        "I can give content tips, schedule reminders, and help you post consistently.\n\n"
        "Commands:\n"
        "/tips - get content ideas\n"
        "/schedule - schedule a daily reminder to post\n"
        "/cancel - cancel scheduling conversation\n"
    )

async def tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ideas = [
        "Share a 'behind the scenes' short about how you make your content.",
        "Post a quick tip your audience can use in under 30 seconds.",
        "Share a before/after transformation or result.",
        "Ask a question: 'What’s one thing you want to learn this week?'",
        "Make a quick tutorial (3 steps)."
    ]
    # Rotate or pick randomly
    import random
    idea = random.choice(ideas)
    await update.message.reply_text(f"Content idea: {idea}")

async def schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me the time you want a daily reminder in HH:MM (24-hour) format, e.g. 18:30.",
        parse_mode="Markdown"
    )
    return WHEN

async def schedule_time_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.message.chat.id
    try:
        hh, mm = text.split(":")
        hh = int(hh); mm = int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError()
    except Exception:
        await update.message.reply_text("Time format invalid. Please send HH:MM (24-hour). Try again or /cancel.")
        return WHEN

    # Remove existing job for chat if any
    if chat_id in chat_jobs:
        job = chat_jobs[chat_id]
        job.remove()

    # Schedule a job with APScheduler (daily at hh:mm)
    trigger = CronTrigger(hour=hh, minute=mm)
    def send_reminder(context_chat_id=chat_id):
        # We must use bot to send message from scheduler function
        from telegram import Bot
        bot = Bot(TOKEN)
        try:
            bot.send_message(chat_id=context_chat_id, text="⏰ Reminder: time to create/post something! Need a tip? Use /tips")
        except Exception as e:
            logger.exception("Failed to send scheduled message")

    job = scheduler.add_job(send_reminder, trigger)
    chat_jobs[chat_id] = job

    await update.message.reply_text(f"Okay — scheduled a daily reminder at {text}. You can /canceljob to remove it.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Scheduling cancelled.")
    return ConversationHandler.END

async def cancel_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if chat_id in chat_jobs:
        job = chat_jobs.pop(chat_id)
        job.remove()
        await update.message.reply_text("Your scheduled reminder was cancelled.")
    else:
        await update.message.reply_text("You have no scheduled reminders.")
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that. Use /tips or /schedule.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # set bot commands shown in Telegram UI
    app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("tips", "Get a content tip"),
        BotCommand("schedule", "Schedule a daily reminder"),
        BotCommand("canceljob", "Cancel scheduled reminder")
    ])

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('schedule', schedule_start)],
        states={
            WHEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_time_received)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tips", tips))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("canceljob", cancel_job))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("Bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()