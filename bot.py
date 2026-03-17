import os
import requests
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# ---------------- API ----------------
def get_tx(tx_hash):
    try:
        url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={tx_hash}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

def get_price(pair):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
        price = float(requests.get(url, timeout=5).json()["price"])
        return price
    except:
        return 0

# ---------------- ANALİZ ----------------
def analyze_tx(tx, tx_hash):
    try:
        # ZAMAN
        timestamp = tx.get("block_ts") or tx.get("timestamp")
        if timestamp:
            date = datetime.fromtimestamp(int(timestamp)/1000).strftime("%d %B %Y %H:%M:%S")
        else:
            date = "Bilinmiyor"

        # ADRESLER - TRC20 işlemlerde doğru adresleri çek
        sender = "UNKNOWN"
        receiver = "UNKNOWN"

        if tx.get("trc20TransferInfo") and len(tx["trc20TransferInfo"]) > 0:
            t = tx["trc20TransferInfo"][0]
            sender = t.get("from_address") or t.get("fromAddress") or "UNKNOWN"
            receiver = t.get("to_address") or t.get("toAddress") or "UNKNOWN"
            coin = t.get("symbol", "TOKEN")
            decimals = int(t.get("decimals", 6))
            raw_amount = t.get("amount_str") or t.get("amount") or "0"
            amount = float(raw_amount) / (10 ** decimals)
        elif tx.get("contractData") and "amount" in tx["contractData"]:
            sender = tx.get("ownerAddress") or tx.get("fromAddress") or "UNKNOWN"
            receiver = tx.get("toAddress") or "UNKNOWN"
            coin = "TRX"
            amount = tx["contractData"]["amount"] / 1_000_000
        else:
            coin = "UNKNOWN"
            amount = 0

        # GÜNCEL KUR
        usdt_try = get_price("USDTTRY")
        if usdt_try == 0:
            usdt_try = 25.50  # fallback

        tl_total = amount * usdt_try

        msg = f"""
🔍 TRON TX ANALİZ

🆔 {tx_hash}

📅 {date}

👤 GÖNDEREN:
{sender}

👤 ALICI:
{receiver}

💵 GÜNCEL KUR:
1 USDT = ₺{usdt_try:,.2f}

💵 TL TOPLAM:
₺{tl_total:,.2f}

🔗 https://tronscan.org/#/transaction/{tx_hash}
"""
        return msg

    except Exception as e:
        return f"⚠️ Hata: {e}"

# ---------------- MESAJ ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # TX HASH yakala (link veya sadece hash)
    match = re.search(r'([a-fA-F0-9]{64})', text)
    if not match:
        return

    tx_hash = match.group(1)

    await update.message.reply_text("⏳ İşlem analiz ediliyor...")

    tx = get_tx(tx_hash)

    if not tx or "hash" not in tx:
        await update.message.reply_text("❌ TX bulunamadı veya geçersiz")
        return

    msg = analyze_tx(tx, tx_hash)
    await update.message.reply_text(msg)

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Grup ve özel mesajlarda çalışır
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("✅ TRON TX ANALİZ BOTU AKTİF")
    app.run_polling()

if __name__ == "__main__":
    main()
