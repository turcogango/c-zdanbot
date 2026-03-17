import os
import requests
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
BALINA_LIMIT = 10000  # 10k$ üzeri balina

# ---------------- API ----------------
def get_tx(tx_hash):
    try:
        url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={tx_hash}"
        r = requests.get(url, timeout=5)
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
        # timestamp fix
        timestamp = tx.get("block_ts") or tx.get("timestamp") or 0
        if timestamp == 0:
            date = "Bilinmiyor"
        else:
            timestamp = int(timestamp) / 1000
            date = datetime.fromtimestamp(timestamp).strftime("%d %B %Y %H:%M:%S")

        # adresler fallback
        sender = tx.get("ownerAddress") or tx.get("fromAddress") or "UNKNOWN"
        receiver = tx.get("toAddress") or "UNKNOWN"

        coin = "UNKNOWN"
        amount = 0

        # TRC20
        if "trc20TransferInfo" in tx and len(tx["trc20TransferInfo"]) > 0:
            t = tx["trc20TransferInfo"][0]
            coin = t.get("symbol", "TOKEN")
            decimals = int(t.get("decimals", 6))
            amount = float(t["amount_str"]) / (10 ** decimals)

        # TRX
        elif "contractData" in tx and "amount" in tx["contractData"]:
            coin = "TRX"
            amount = tx["contractData"]["amount"] / 1_000_000

        # fiyatlar
        usdt_try = get_price("USDTTRY")
        if coin in ["USDT", "USDC"]:
            usd_value = amount
        else:
            trx_price = get_price("TRXUSDT")
            usd_value = amount * trx_price
        tl_value = usd_value * usdt_try

        whale = "🐋 BALİNA!" if usd_value >= BALINA_LIMIT else ""

        msg = f"""
🏦 TX Bilgisi: {tx_hash}

💵 Güncel KUR: {usdt_try:,.3f} ₺
📅 {date} Tarihinde

{sender} adresinden
{receiver} adresine

💵 ${usd_value:,.2f} {coin} gönderilmiş
💵 ${usd_value:,.2f} Güncel kur ile kom hariç: ₺{tl_value:,.2f}

{whale}

https://tronscan.org/#/transaction/{tx_hash}
"""
        return msg

    except Exception as e:
        return f"⚠️ Hata: {e}"

# ---------------- MESAJ YAKALAMA ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # hash veya linkten TX hash ayıkla
    match = re.search(r'(?:transaction/)?([a-fA-F0-9]{64})', text)
    if match:
        tx_hash = match.group(1)
        tx = get_tx(tx_hash)
        if not tx or "hash" not in tx:
            await update.message.reply_text("❌ TX bulunamadı veya geçersiz")
            return
        msg = analyze_tx(tx, tx_hash)
        await update.message.reply_text(msg)

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    print("✅ SAĞLAM TX ANALİZ BOTU AKTİF")
    app.run_polling()

if __name__ == "__main__":
    main()
