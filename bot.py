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

# CoinGecko fiyat
def get_coingecko_price(coin_id, vs="try"):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={vs}"
        r = requests.get(url, timeout=5).json()
        return float(r[coin_id][vs])
    except:
        return 0

# ---------------- ANALİZ ----------------
def analyze_tx(tx, tx_hash):
    try:
        timestamp = tx.get("block_ts") or tx.get("timestamp")
        date = datetime.fromtimestamp(int(timestamp)/1000).strftime("%d %B %Y %H:%M:%S") if timestamp else "Bilinmiyor"

        sender = "UNKNOWN"
        receiver = "UNKNOWN"
        coin = "UNKNOWN"
        amount = 0

        # TRC20 token
        if tx.get("trc20TransferInfo") and len(tx["trc20TransferInfo"]) > 0:
            t = tx["trc20TransferInfo"][0]
            sender = t.get("from_address") or t.get("fromAddress") or "UNKNOWN"
            receiver = t.get("to_address") or t.get("toAddress") or "UNKNOWN"
            coin = t.get("symbol", "TOKEN")
            decimals = int(t.get("decimals", 6))
            raw_amount = t.get("amount_str") or t.get("amount") or "0"
            amount = float(raw_amount) / (10 ** decimals)

        # TRX işlemi
        elif tx.get("contractData") and "amount" in tx["contractData"]:
            sender = tx.get("ownerAddress") or tx.get("fromAddress") or "UNKNOWN"
            receiver = tx.get("toAddress") or "UNKNOWN"
            coin = "TRX"
            amount = tx["contractData"]["amount"] / 1_000_000

        # TL hesaplama
        tl_total = 0
        cur_str = "Bilinmiyor"

        if coin.upper() == "USDT":
            price = get_coingecko_price("tether")
            if price == 0:
                price = 44.40
            tl_total = amount * price
            cur_str = f"{price:,.3f} ₺"

        elif coin.upper() == "USDC":
            price = get_coingecko_price("usd-coin")
            if price == 0:
                price = 44.40
            tl_total = amount * price
            cur_str = f"{price:,.3f} ₺"

        elif coin.upper() == "TRX":
            price = get_coingecko_price("tron")
            if price == 0:
                price = 2.73
            tl_total = amount * price
            cur_str = f"{price:,.3f} ₺"

        amount_str = f"{amount:,.2f} {coin}"
        tl_total_str = f"₺{tl_total:,.2f}"

        msg = f"""💰 TX Bilgisi:
{tx_hash}

💸 Güncel KUR: {cur_str}
📅 {date} Tarihinde

👤 GÖNDEREN:
{sender}

👤 ALICI:
{receiver}

💵 {amount_str} gönderilmiş
💵 TL değeri: {tl_total_str}"""
        return msg

    except Exception as e:
        return f"⚠️ Hata: {e}"

# ---------------- MESAJ ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
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
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("✅ TRON TX ANALİZ BOTU AKTİF (CoinGecko)")
    app.run_polling()

if __name__ == "__main__":
    main()
