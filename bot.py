import os
import requests
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ---------------- AYARLAR ----------------
TOKEN = os.getenv("BOT_TOKEN")
WALLETS = ["TSjQYavgJBGPr8iV3zH7qo1bx927qKVMwA"]
SLEEP = 10
MAX_TX_CHECK = 5
BALINA_LIMIT = 10000  # 10k$ üstü balina

# ---------------- DURUM ----------------
group_chat_id = None
last_tx = {wallet: None for wallet in WALLETS}

# ---------------- API ----------------
def get_price(pair):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
        return float(requests.get(url, timeout=5).json()["price"])
    except:
        return 0

def get_transactions(wallet):
    try:
        url = f"https://apilist.tronscanapi.com/api/transaction?address={wallet}&limit={MAX_TX_CHECK}"
        return requests.get(url, timeout=5).json()["data"]
    except:
        return []

# ---------------- ANALİZ ----------------
def analyze_tx(tx):
    try:
        tx_hash = tx["hash"]

        timestamp = int(tx["timestamp"]) / 1000
        date = datetime.fromtimestamp(timestamp).strftime("%d %B %Y %H:%M:%S")

        sender = tx.get("ownerAddress", "UNKNOWN")
        receiver = tx.get("toAddress", "UNKNOWN")

        coin = "UNKNOWN"
        amount = 0

        # TRC20 (USDT vs)
        if "trc20TransferInfo" in tx and len(tx["trc20TransferInfo"]) > 0:
            t = tx["trc20TransferInfo"][0]
            coin = t.get("symbol", "TOKEN")
            decimals = int(t.get("decimals", 6))
            amount = float(t["amount_str"]) / (10 ** decimals)

        # TRX
        elif "contractData" in tx and "amount" in tx["contractData"]:
            coin = "TRX"
            amount = tx["contractData"]["amount"] / 1_000_000

        # Fiyatlar
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

# ---------------- TELEGRAM ----------------
async def register_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global group_chat_id
    if group_chat_id is None:
        group_chat_id = update.effective_chat.id
        await update.message.reply_text("✅ Bot aktif! Cüzdan izleniyor...")
        asyncio.create_task(monitor(context.application))

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
🤖 KOMUTLAR
/bakiye → (yakında)
/islemler → (yakında)
""")

# ---------------- MONITOR ----------------
async def monitor(app):
    global group_chat_id
    bot = app.bot

    while True:
        if group_chat_id is None:
            await asyncio.sleep(5)
            continue

        for wallet in WALLETS:
            txs = get_transactions(wallet)

            if not txs:
                continue

            for tx in txs:
                txid = tx["hash"]

                if last_tx[wallet] is None:
                    last_tx[wallet] = txid
                    break

                if txid == last_tx[wallet]:
                    break

                msg = analyze_tx(tx)
                await bot.send_message(group_chat_id, msg)

            last_tx[wallet] = txs[0]["hash"]

        await asyncio.sleep(SLEEP)

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("yardim", yardim))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), register_group))

    print("✅ BOT ÇALIŞIYOR")
    app.run_polling()

if __name__ == "__main__":
    main()
