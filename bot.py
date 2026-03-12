import os
import requests
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ---------------- AYARLAR ----------------
TOKEN = os.getenv("BOT_TOKEN")
WALLETS = ["TSjQYavgJBGPr8iV3zH7qo1bx927qKVMwA"]  # İzlenecek cüzdanlar
SLEEP = 10
MAX_TX_CHECK = 5
BALINA_LIMIT = 1000  # USD değeri üzeri işlemler balina sayılır

# ---------------- DURUMLAR ----------------
group_chat_id = None
last_tx = {wallet: None for wallet in WALLETS}
daily_in = {wallet: 0 for wallet in WALLETS}
daily_out = {wallet: 0 for wallet in WALLETS}
daily_token_in = {wallet: {} for wallet in WALLETS}
daily_token_out = {wallet: {} for wallet in WALLETS}
current_day = datetime.now().date()

# ---------------- API FONKSİYONLARI ----------------
def get_price(pair):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
        r = requests.get(url, timeout=5).json()
        return float(r["price"])
    except:
        return 0

def get_balance(wallet):
    try:
        url = f"https://apilist.tronscanapi.com/api/account?address={wallet}"
        r = requests.get(url, timeout=5).json()
        trx = r.get("balance", 0) / 1_000_000
        balances = {"TRX": trx, "USDT": 0, "USDC": 0}
        tokens = r.get("trc20token_balances", [])
        for t in tokens:
            balances[t["tokenAbbr"]] = float(t["balance"]) / 1_000_000
        return balances
    except:
        return {"TRX":0, "USDT":0, "USDC":0}

def get_transactions(wallet):
    try:
        url = f"https://apilist.tronscanapi.com/api/transaction?address={wallet}&limit={MAX_TX_CHECK}"
        r = requests.get(url, timeout=5).json()
        return r["data"]
    except:
        return []

# ---------------- İŞLEM ANALİZ ----------------
def analyze_tx(tx, wallet):
    coin = "UNKNOWN"
    amount = 0
    if "contractData" in tx and "amount" in tx["contractData"]:
        amount = tx["contractData"]["amount"]/1_000_000
        coin = "TRX"
    elif "trc20TransferInfo" in tx and len(tx["trc20TransferInfo"])>0:
        transfer = tx["trc20TransferInfo"][0]
        amount = float(transfer["amount_str"])/1_000_000
        coin = transfer["symbol"]

    sender = tx["ownerAddress"]
    receiver = tx["toAddress"]

    if receiver == wallet:
        direction = "📥 GELEN"
        daily_in[wallet] += 1
        daily_token_in[wallet][coin] = daily_token_in[wallet].get(coin,0) + amount
    else:
        direction = "📤 GİDEN"
        daily_out[wallet] += 1
        daily_token_out[wallet][coin] = daily_token_out[wallet].get(coin,0) + amount

    usd_price = get_price("TRXUSDT") if coin=="TRX" else 1
    usdt_try = get_price("USDTTRY")
    usd_value = amount * usd_price
    tl_value = usd_value * usdt_try
    whale_alert = "🐋 BALİNA HAREKETİ!" if usd_value >= BALINA_LIMIT else ""

    balances = get_balance(wallet)

    msg = f"""
🏦 TRON CÜZDAN HAREKETİ

Adres: {wallet}
{direction}

💰 Coin: {coin}
💵 Miktar: {amount:,.2f}
💵 USD: ${usd_value:,.2f}
💵 TL: ₺{tl_value:,.2f}
{whale_alert}

📊 Cüzdan Bakiyesi
TRX: {balances['TRX']:,.2f}
USDT: {balances['USDT']:,.2f}
USDC: {balances['USDC']:,.2f}

🔗 İşlem Linki:
https://tronscan.org/#/transaction/{tx['hash']}
"""
    return msg

# ---------------- Z RAPORU ----------------
def generate_z_report(wallet):
    msg = f"📊 GÜNLÜK Z RAPORU\n\nCüzdan: {wallet}\n\n"
    msg += f"Gelen İşlem Sayısı: {daily_in[wallet]}\nGiden İşlem Sayısı: {daily_out[wallet]}\n\n"
    msg += "Token Bazında Gelen:\n"
    for coin, amt in daily_token_in[wallet].items():
        msg += f"{coin}: {amt:,.2f}\n"
    msg += "\nToken Bazında Giden:\n"
    for coin, amt in daily_token_out[wallet].items():
        msg += f"{coin}: {amt:,.2f}\n"
    msg += f"\nRapor Saati: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return msg

# ---------------- TELEGRAM ----------------
async def register_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global group_chat_id
    if group_chat_id is None:
        group_chat_id = update.effective_chat.id
        await update.message.reply_text("✅ TRON takip botu aktif! Artık grup işlemleri izleniyor.")
        # Grup kaydedildikten hemen sonra monitor başlat
        asyncio.create_task(monitor(context.application))

# ---------------- KOMUTLAR ----------------
async def bakiye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for wallet in WALLETS:
        balances = get_balance(wallet)
        msg = f"📊 CÜZDAN BAKİYESİ\n\nCüzdan: {wallet}\nTRX: {balances['TRX']:,.2f}\nUSDT: {balances['USDT']:,.2f}\nUSDC: {balances['USDC']:,.2f}"
        await update.message.reply_text(msg)

async def zrapor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for wallet in WALLETS:
        msg = generate_z_report(wallet)
        await update.message.reply_text(msg)

async def islemler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for wallet in WALLETS:
        txs = get_transactions(wallet)
        msg = "📜 SON İŞLEMLER\n\n"
        for tx in txs[:5]:
            msg += f"https://tronscan.org/#/transaction/{tx['hash']}\n"
        await update.message.reply_text(msg)

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
🤖 BOT KOMUTLARI
/bakiye   → Cüzdan bakiyesi
/zrapor   → Günlük Z raporu
/islemler → Son işlemler
/yardim   → Komut listesi
"""
    await update.message.reply_text(msg)

# ---------------- MONITOR ----------------
async def monitor(app):
    global current_day
    bot = app.bot
    while True:
        if group_chat_id is None:
            await asyncio.sleep(5)
            continue

        now = datetime.now()
        if now.date() != current_day:
            for wallet in WALLETS:
                await bot.send_message(group_chat_id, generate_z_report(wallet))
                daily_in[wallet] = 0
                daily_out[wallet] = 0
                daily_token_in[wallet] = {}
                daily_token_out[wallet] = {}
            current_day = now.date()

        for wallet in WALLETS:
            txs = get_transactions(wallet)
            if len(txs) == 0:
                continue
            tx = txs[0]
            txid = tx["hash"]
            if last_tx[wallet] is None:
                last_tx[wallet] = txid
                continue
            if txid != last_tx[wallet]:
                last_tx[wallet] = txid
                msg = analyze_tx(tx, wallet)
                await bot.send_message(group_chat_id, msg)

        await asyncio.sleep(SLEEP)

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("bakiye", bakiye))
    app.add_handler(CommandHandler("zrapor", zrapor))
    app.add_handler(CommandHandler("islemler", islemler))
    app.add_handler(CommandHandler("yardim", yardim))

    # Sadece ilk mesajla grubu kaydet
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), register_group))

    print("✅ TRON BOT AKTİF")
    app.run_polling()

if __name__ == "__main__":
    main()
