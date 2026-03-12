import requests
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ---------------- AYARLAR ----------------
TOKEN = "TELEGRAM_BOT_TOKEN"
WALLETS = ["TRON_ADRESI"]    # Birden fazla cüzdan ekleyebilirsin
SLEEP = 5                     # Kontrol aralığı (saniye)
MAX_TX_CHECK = 10

# ----------------------------------------
last_tx = {wallet: None for wallet in WALLETS}
daily_count_in = {wallet:0 for wallet in WALLETS}
daily_count_out = {wallet:0 for wallet in WALLETS}
daily_token_in = {wallet:{} for wallet in WALLETS}
daily_token_out = {wallet:{} for wallet in WALLETS}
daily_swap_fees = {wallet:{} for wallet in WALLETS}
current_day = datetime.now().date()

# ---------- FONKSİYONLAR -----------------
def get_price(pair):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
        return float(requests.get(url, timeout=5).json()["price"])
    except:
        return 0

def get_balance(wallet):
    try:
        url = f"https://apilist.tronscanapi.com/api/account?address={wallet}"
        r = requests.get(url, timeout=5).json()
        trx = r.get("balance",0)/1000000
        tokens = r.get("trc20token_balances",[])
        balances = {"TRX": trx}
        for t in tokens:
            balances[t["tokenAbbr"]] = float(t["balance"])/1000000
        for t in ["USDT","USDC"]:
            if t not in balances:
                balances[t] = 0
        return balances
    except:
        return {"TRX":0,"USDT":0,"USDC":0}

def get_transactions(wallet):
    try:
        url = f"https://apilist.tronscanapi.com/api/transaction?address={wallet}&limit={MAX_TX_CHECK}"
        return requests.get(url, timeout=5).json()["data"]
    except:
        return []

def analyze_tx(tx, wallet):
    global daily_count_in, daily_count_out, daily_token_in, daily_token_out, daily_swap_fees

    coin = "UNKNOWN"
    amount = 0
    fee = 0
    if "contractData" in tx and "amount" in tx["contractData"]:
        amount = tx["contractData"]["amount"]/1000000
        coin = "TRX"
        fee = tx.get("fee",0)/1000000
    elif "trc20TransferInfo" in tx and len(tx["trc20TransferInfo"])>0:
        transfer = tx["trc20TransferInfo"][0]
        amount = float(transfer["amount_str"])/1000000
        coin = transfer["symbol"]
        fee = tx.get("fee",0)/1000000

    sender = tx["ownerAddress"]
    receiver = tx["toAddress"]

    if receiver == wallet:
        direction = "📥 GİRİŞ"
        daily_count_in[wallet] += 1
        daily_token_in[wallet][coin] = daily_token_in[wallet].get(coin,0) + amount
    else:
        direction = "📤 ÇIKIŞ"
        daily_count_out[wallet] += 1
        daily_token_out[wallet][coin] = daily_token_out[wallet].get(coin,0) + amount

    swap_info = ""
    if coin != "TRX" and fee>0:
        swap_info = f"🔄 SWAP İŞLEMİ\nİşlem Ücreti/Kesinti: {fee:,.2f} {coin}"
        daily_swap_fees[wallet][coin] = daily_swap_fees[wallet].get(coin,0) + fee

    usd_price = get_price(f"{coin}USDT") if coin=="TRX" else 1
    usdt_try = get_price("USDTTRY")
    usd_value = amount*usd_price
    tl_value = usd_value*usdt_try

    balances = get_balance(wallet)

    msg = f"""
🏦 TRON Cüzdan Hareketi

Adres: {wallet}
{direction}

💰 Tür: {coin}
💵 Miktar: {amount:,.2f}
💱 Kur: {usdt_try:.2f} ₺
💵 TL Karşılığı: ₺{tl_value:,.2f}
{swap_info}

📊 Cüzdan Bakiyesi
TRX: {balances['TRX']:,.2f}
USDT: {balances['USDT']:,.2f}
USDC: {balances['USDC']:,.2f}

TX: https://tronscan.org/#/transaction/{tx['hash']}
"""
    return msg

def generate_z_report(wallet):
    msg = f"📊 Z RAPORU - Günlük Özet\nCüzdan: {wallet}\n\n"
    msg += f"Giriş İşlemleri: {daily_count_in[wallet]}\nÇıkış İşlemleri: {daily_count_out[wallet]}\n\n"
    msg += "Token Bazında Giriş:\n"
    for coin, amt in daily_token_in[wallet].items():
        msg += f"  {coin}: {amt:,.2f}\n"
    msg += "Token Bazında Çıkış:\n"
    for coin, amt in daily_token_out[wallet].items():
        msg += f"  {coin}: {amt:,.2f}\n"
    msg += "Swap Ücretleri:\n"for coin, fee in daily_swap_fees[wallet].items():
        msg += f"  {coin}: {fee:,.2f}\n"
    msg += f"\nRapor oluşturma saati: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return msg

# ----------- BOT CALLBACK -------------
async def check_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_tx, current_day
    now = datetime.now()
    if now.date() != current_day:
        # Gün değişti, Z raporu oluştur
        for wallet in WALLETS:
            z_report = generate_z_report(wallet)
            await update.message.reply_text(z_report)
            # Günlük sayaçları sıfırla
            last_tx[wallet] = None
            daily_count_in[wallet] = 0
            daily_count_out[wallet] = 0
            daily_token_in[wallet] = {}
            daily_token_out[wallet] = {}
            daily_swap_fees[wallet] = {}
        current_day = now.date()

    for wallet in WALLETS:
        txs = get_transactions(wallet)
        if len(txs) == 0:
            continue
        tx = txs[0]
        txid = tx["hash"]
        if txid != last_tx[wallet]:
            last_tx[wallet] = txid
            msg = analyze_tx(tx, wallet)
            await update.message.reply_text(msg)

# ------------- UYGULAMA ----------------
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), check_wallet))

print("Profesyonel TRON takip botu grup içinde çalışıyor ve günlük Z raporu oluşturacak...")
app.run_polling()
