import feedparser
from html import unescape
from bs4 import BeautifulSoup
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import re
import requests

# Telegram bot token
TELEGRAM_TOKEN = 'telegram api'

# State definitions for conversation handler
CHOOSING, TYPING_KEYWORDS, TYPING_RSS = range(3)

# Temporary storage for user data
user_data = {}

# API URLs
EXCHANGE_RATE_API_URL = 'https://v6.exchangerate-api.com/v6/api_kodunuz/latest/USD'
COINGECKO_API_URL = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd'

def clean_html(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text()

def fetch_and_filter_posts(rss_urls, keywords):
    filtered_posts = []
    seen_titles = set()  # Başlıkları saklamak için set

    for rss_url in rss_urls:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            entry_text = (entry.title + ' ' + entry.summary).lower()
            if any(re.search(r'\b' + re.escape(keyword.lower()) + r'\b', entry_text) for keyword in keywords):
                title = unescape(entry.title)
                link = entry.link
                if title not in seen_titles:  # Daha önce görülmediyse ekle
                    seen_titles.add(title)
                    filtered_posts.append((title, link))
    return filtered_posts

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Merhaba! Anahtar kelimeleri ve RSS feed URL\'lerini eklemek için /set_keywords ve /set_rss komutlarını kullanabilirsiniz. '
        'Gönderileri kontrol etmek için /check komutunu kullanabilirsiniz.'
    )

async def set_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Lütfen anahtar kelimeleri virgülle ayırarak girin:')
    return TYPING_KEYWORDS

async def set_rss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Lütfen RSS feed URL\'lerini virgülle ayırarak girin:')
    return TYPING_RSS

async def received_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data['keywords'] = [kw.strip() for kw in update.message.text.split(',')]
    await update.message.reply_text(f"Anahtar kelimeler ayarlandı: {', '.join(user_data['keywords'])}")
    return ConversationHandler.END

async def received_rss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data['rss_urls'] = [url.strip() for url in update.message.text.split(',')]
    await update.message.reply_text(f"RSS feed URL'leri ayarlandı: {', '.join(user_data['rss_urls'])}")
    return ConversationHandler.END

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'keywords' in user_data and 'rss_urls' in user_data:
        posts = fetch_and_filter_posts(user_data['rss_urls'], user_data['keywords'])
        if posts:
            for title, link in posts:
                await update.message.reply_text(f"Başlık: {title}\nBağlantı: {link}\n")
        else:
            await update.message.reply_text('Hiçbir eşleşen gönderi bulunamadı.')
    else:
        await update.message.reply_text('Lütfen önce anahtar kelimeleri ve RSS feed URL\'lerini ayarlayın.')

async def kurlar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Döviz kurları
        exchange_rate_response = requests.get(EXCHANGE_RATE_API_URL)
        exchange_rate_data = exchange_rate_response.json()

        usd_to_try = exchange_rate_data['conversion_rates']['TRY']
        eur_to_usd = exchange_rate_data['conversion_rates']['EUR']
        gbp_to_usd = exchange_rate_data['conversion_rates']['GBP']

        eur_to_try = usd_to_try / eur_to_usd
        gbp_to_try = usd_to_try / gbp_to_usd

        # Bitcoin fiyatı
        coingecko_response = requests.get(COINGECKO_API_URL)
        coingecko_data = coingecko_response.json()

        btc_to_usd = coingecko_data['bitcoin']['usd']

        # Kullanıcıya mesaj gönder
        await update.message.reply_text(
            f"Güncel Kurlar:\n"
            f"Dolar: {usd_to_try:.2f} TRY\n"
            f"Euro: {eur_to_try:.2f} TRY\n"
            f"Sterlin: {gbp_to_try:.2f} TRY\n"
            f"Bitcoin: {btc_to_usd:.2f} USD"
        )

    except Exception as e:
        await update.message.reply_text('Kurları alırken bir hata oluştu.')

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('set_keywords', set_keywords),
                      CommandHandler('set_rss', set_rss)],
        states={
            TYPING_KEYWORDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_keywords)],
            TYPING_RSS: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_rss)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("kurlar", kurlar))

    application.run_polling()

if __name__ == '__main__':
    main()
