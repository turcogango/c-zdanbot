import os
import requests
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
BALINA_LIMIT = 10000  # $10k üstü balina uyarısı

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
        return float(requests.get(url, timeout=5).json()["price"])
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

        # ADRESLER - TRC20 transferlerde doğru adresleri çek
        sender = "UNKNOWN"
        receiver = "UNKNOWN"

        if tx.get("trc20TransferInfo") and len(tx["trc20TransferInfo"]) > 0:
            t = tx["trc20TransferInfo"][0]
            sender = t.get("from_address") or t.get("fromAddress") or "UNKNOWN"
            receiver = t.get("to_address") or t.get("toAddress") or "UNKNOWN"
        else:
            sender = tx.get("ownerAddress") or tx.get("fromAddress") or "UNKNOWN"
            receiver = tx.get("toAddress") or "UNKNOWN"

        # COİN ve MİKTAR
        coin = "UNKNOWN"
        amount = 0

        if tx.get("trc20TransferInfo") and len(tx["trc20TransferInfo"]) > 0:
            t = tx["trc20TransferInfo"][0]
            coin = t.get("symbol", "TOKEN")
            decimals = int(t.get("decimals", 6))
            raw_amount = t.get("amount_str") or t.get("amount") or "0"
            amount = float(raw_amount) / (10 ** decimals)
        elif tx.get("contractData") and "amount" in tx["contractData"]:
            coin = "TRX"
            amount = tx["contractData"]["amount"] / 1_000_000

        # FİYAT
        usdt_try = get_price("USDTTRY")
        trx_price = get_price("TRXUSDT")

        if coin in ["USDT", "USDC"]:
            usd_value = amount
        else:
            usd_value = amount * trx_price

        tl_value = usd_value * usdt_try

        whale = "🐋 BALİNA TRANSFERİ!" if usd_value >= BALINA_LIMIT else ""

        msg = f"""
🔍 TRON TX ANALİZ

🆔 {tx_hash}

📅 {date}

👤 GÖNDEREN:
{sender}

👤 ALICI:
{receiver}

💰 MİKTAR:
{amount:,.6f} {coin}

💵 USD:
${usd_value:,.2f}

🇹🇷 TL:
₺{tl_value:,.2f}

{whale}

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
