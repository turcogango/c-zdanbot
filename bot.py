import os
import requests
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")  # Bot tokeninizi buraya koyun

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

# Ücretsiz güvenilir döviz kuru
def get_price(pair):
    try:
        base = pair[:-3]
        target = pair[-3:]
        url = f"https://api.exchangerate.host/convert?from={base}&to={target}"
        r = requests.get(url, timeout=5).json()
        if r.get("success") and r.get("result"):
            return float(r["result"])
    except:
        pass
    return 0

# ---------------- ANALİZ ----------------
def analyze_tx(tx, tx_hash):
    try:
        # Zaman
        timestamp = tx.get("block_ts") or tx.get("timestamp")
        date = datetime.fromtimestamp(int(timestamp)/1000).strftime("%d %B %Y %H:%M:%S") if timestamp else "Bilinmiyor"

        sender = "UNKNOWN"
        receiver = "UNKNOWN"
        coin = "UNKNOWN"
        amount = 0
        tx_type = "UNKNOWN"

        # TRC20 işlemler (token)
        if tx.get("trc20TransferInfo") and len(tx["trc20TransferInfo"]) > 0:
            t = tx["trc20TransferInfo"][0]
            sender = t.get("from_address") or t.get("fromAddress") or "UNKNOWN"
            receiver = t.get("to_address") or t.get("toAddress") or "UNKNOWN"
            coin = t.get("symbol", "TOKEN")
            decimals = int(t.get("decimals", 6))
            raw_amount = t.get("amount_str") or t.get("amount") or "0"
            amount = float(raw_amount) / (10 ** decimals)
            tx_type = "TOKEN"

        # TRX işlemler
        elif tx.get("contractData") and "amount" in tx["contractData"]:
            sender = tx.get("ownerAddress") or tx.get("fromAddress") or "UNKNOWN"
            receiver = tx.get("toAddress") or "UNKNOWN"
            coin = "TRX"
            amount = tx["contractData"]["amount"] / 1_000_000
            tx_type = "TRX"

        # Güncel kur ve TL hesaplama
        usdt_try = get_price("USDTTRY")
        if usdt_try == 0:
            usdt_try = 44.05  # fallback

        if tx_type == "TOKEN":
            tl_total = amount * usdt_try
        elif tx_type == "TRX":
            trx_usdt = get_price("TRXUSDT")
            if trx_usdt == 0:
                trx_usdt = 0.062  # fallback
            tl_total = amount * trx_usdt * usdt_try
        else:
            tl_total = 0

        amount_str = f"{amount:,.2f} {coin}"
        tl_total_str = f"₺{tl_total:,.2f}"
        usdt_try_str = f"{usdt_try:,.3f} ₺"

        msg = f"""💰 TX Bilgisi:
{tx_hash}

💸 Güncel KUR: {usdt_try_str}
📅 {date} Tarihinde

👤 GÖNDEREN:
{sender}

👤 ALICI:
{receiver}

💵 {amount_str} gönderilmiş
💵 TL değeri: {tl_total_str}

🔹 İşlem Türü: {tx_type}"""
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
    print("✅ TRON TX ANALİZ BOTU AKTİF")
    app.run_polling()

if __name__ == "__main__":
    main()
