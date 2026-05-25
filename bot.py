"""
MantisTrackerBot — Crypto Airdrop Tracker
Telegram: @Mantis_Tracker_Bot
Priority chains: SOL · BTC · ETH · BNB
Daily auto-digest + scam safety scoring
"""

import logging
import asyncio
import json
import os
import hashlib
from datetime import datetime, time as dtime
from typing import Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from telegram.constants import ParseMode
from airdrop_sources import fetch_all_airdrops, PRIORITY_CHAINS

# ─── CONFIG ──────────────────────────────────────────────────────────────────

 import os
   BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # ⚠️ REGENERATE THIS TOKEN

DAILY_DIGEST_HOUR   = 8   # UTC
DAILY_DIGEST_MINUTE = 0

DATA_FILE  = "airdrop_data.json"
USERS_FILE = "users.json"

CHAIN_EMOJIS = {
    "SOL": "◎", "BTC": "₿", "ETH": "Ξ",
    "BNB": "🔶", "BASE": "🔵", "ARB": "🔷",
    "MATIC": "🟣", "AVAX": "🔺", "APT": "🅰️",
    "SUI": "💧", "TON": "💎", "NEAR": "🌈",
    "ATOM": "⚛️", "OTHER": "🪙",
}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── SAFETY TIPS ─────────────────────────────────────────────────────────────

DAILY_SAFETY_TIPS = [
    ("🔑", "Never share your password or PIN with anyone — not support, not admins, not bots."),
    ("🌱", "Your seed phrase is your wallet. If anyone asks for it, they're stealing from you. Full stop."),
    ("🔒", "Enable 2FA (two-factor authentication) on every exchange and email account you own."),
    ("🔗", "Always check the URL before connecting your wallet. One wrong character = drained wallet."),
    ("🪣", "Use a separate 'burner' wallet for airdrops — never your main wallet with real funds."),
    ("📧", "Never click crypto links from emails or DMs. Go directly to the official site yourself."),
    ("💰", "Real airdrops are 100% free. If it costs anything to claim — gas, fee, 'activation' — it's a scam."),
    ("👤", "No legitimate project will ever DM you first asking you to claim a reward."),
    ("📱", "Store your seed phrase offline — written on paper, never in a photo, note app, or cloud storage."),
    ("🚨", "If a deal sounds too good to be true (100x guaranteed!), it is. Always. No exceptions."),
    ("🔍", "Before interacting with any contract, verify it on Etherscan/Solscan and check the audit report."),
    ("🤫", "Don't publicly announce your wallet address or holdings — it makes you a target."),
    ("⚙️", "Use a hardware wallet (Ledger/Trezor) for any significant crypto holdings."),
    ("🛑", "Revoke token approvals regularly at revoke.cash — old approvals can be exploited anytime."),
    ("🎭", "Fake support accounts on Telegram/Discord are everywhere. Admins will NEVER DM you first."),
    ("🧪", "Test any new contract interaction with a small amount first before going all in."),
    ("📵", "Never enter your seed phrase into any website, app, or bot — ever. Not even 'official' ones."),
    ("🔐", "Use a unique, strong password for every crypto account. Use a password manager."),
    ("🕵️", "Check a project's GitHub, audit status, and team before trusting it with your wallet."),
    ("🌐", "Bookmark your most-used DeFi sites. Scammers buy misspelled domain ads to fool you."),
]

TIPS_GUIDE = """🛡️ *Crypto Security Guide — MantisTracker*

━━━━━━━━━━━━━━━━━━━━
🔑 *PASSWORDS & ACCOUNTS*

• Use a unique password for every exchange/site
• Use a password manager (Bitwarden is free & open source)
• Enable 2FA on everything — use an authenticator app, not SMS
• Never share your password, PIN, or 2FA code with anyone
• No legitimate support team will ever ask for your password

━━━━━━━━━━━━━━━━━━━━
🌱 *SEED PHRASES & PRIVATE KEYS*

• Your seed phrase = full access to your entire wallet
• Write it on paper and store it somewhere physically safe
• Never type it into any website, app, Telegram bot, or form
• Never photograph it or save it in notes/cloud/email
• If anyone asks for it, they are stealing from you — guaranteed

━━━━━━━━━━━━━━━━━━━━
🪣 *WALLET SAFETY*

• Use a dedicated "burner" wallet for airdrops & new projects
• Keep main savings in a hardware wallet (Ledger/Trezor)
• Regularly revoke old token approvals at revoke.cash
• Never keep more on an exchange than you're actively trading
• Verify every contract address before approving

━━━━━━━━━━━━━━━━━━━━
🔗 *LINKS & PHISHING*

• Always type URLs yourself or use bookmarks
• Check every character in a URL before connecting
• Scammers run paid ads with near-identical fake domains
• Never click crypto links in emails, DMs, or random tweets
• Fake support bots/accounts on Telegram are extremely common

━━━━━━━━━━━━━━━━━━━━
💰 *AIRDROP-SPECIFIC RULES*

• Legitimate airdrops are ALWAYS free to claim
• No airdrop requires a "gas fee" sent to an address
• No airdrop requires your seed phrase or private key
• No project will DM you first about a reward
• If urgency is being created ("expires in 10 min!") — it's a scam

━━━━━━━━━━━━━━━━━━━━
🚨 *IF YOU THINK YOU'VE BEEN SCAMMED*

1. Immediately move remaining funds to a new wallet
2. Revoke all token approvals on the compromised wallet
3. Change passwords on any connected accounts
4. Report to the project's official Discord/support
5. File a report at ic3.gov (US) or your local cybercrime unit

_Stay paranoid. Stay safe. 🦗_"""

# ─── SCAM SCORING ─────────────────────────────────────────────────────────────

SCAM_RED_FLAGS = [
    "send crypto", "send eth", "send bnb", "send sol", "send btc",
    "private key", "seed phrase", "mnemonic", "secret phrase",
    "import wallet", "unlock airdrop", "activate wallet",
    "processing fee", "gas fee required", "pay to claim",
    "guaranteed returns", "100x guaranteed", "1000x",
    "connect wallet to receive", "dm for claim", "dm to claim",
]

SCAM_YELLOW_FLAGS = [
    "connect wallet", "sign transaction", "approve contract",
    "limited time only", "act now", "exclusive invite",
    "expires in", "whitelist only",
]

TRUST_SIGNALS = [
    "coinmarketcap", "coingecko", "official", "verified",
    "github", "audited", "mainnet", "testnet",
]


def calculate_scam_score(airdrop: dict) -> tuple[int, str, list]:
    text = " ".join([
        airdrop.get("name", ""),
        airdrop.get("description", ""),
        airdrop.get("requirements", ""),
        airdrop.get("url", ""),
    ]).lower()

    score = 0
    warnings = []

    for flag in SCAM_RED_FLAGS:
        if flag in text:
            score += 3
            warnings.append(f"🚨 '{flag}'")

    for flag in SCAM_YELLOW_FLAGS:
        if flag in text:
            score += 1
            warnings.append(f"⚠️ '{flag}'")

    # Curated entries always get a trust bonus
    if airdrop.get("source") == "curated":
        score = max(0, score - 2)

    for signal in TRUST_SIGNALS:
        if signal in text:
            score = max(0, score - 1)

    score = min(10, score)

    if score == 0:     label = "✅ SAFE"
    elif score <= 2:   label = "🟡 LOW RISK"
    elif score <= 5:   label = "🟠 MODERATE RISK"
    elif score <= 7:   label = "🔴 HIGH RISK"
    else:              label = "☠️ LIKELY SCAM"

    return score, label, warnings


# ─── PERSISTENCE ──────────────────────────────────────────────────────────────

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}


def save_users(data: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_cache() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"airdrops": [], "last_updated": None, "new_ids": []}


def save_cache(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_user(uid: int) -> dict:
    users = load_users()
    key = str(uid)
    if key not in users:
        users[key] = {
            "id": uid,
            "filters": PRIORITY_CHAINS.copy(),
            "notifications": True,
            "joined": datetime.now().isoformat(),
        }
        save_users(users)
    return users[key]


def update_user(uid: int, patch: dict):
    users = load_users()
    key = str(uid)
    if key not in users:
        get_user(uid)
        users = load_users()
    users[key].update(patch)
    save_users(users)


# ─── FORMATTERS ───────────────────────────────────────────────────────────────

def fmt_card(airdrop: dict, index: int = None, full: bool = False) -> str:
    chain = airdrop.get("chain", "OTHER")
    emoji = CHAIN_EMOJIS.get(chain, "🪙")
    score, label, warnings = calculate_scam_score(airdrop)
    name   = airdrop.get("name", "Unknown")
    desc   = airdrop.get("description", "")
    url    = airdrop.get("url", "")
    status = airdrop.get("status", "unknown").upper()
    est    = airdrop.get("est_value", "")
    dl     = airdrop.get("deadline", "")

    prefix = f"{index}. " if index else ""
    lines = [f"{prefix}{emoji} *{name}*"]
    lines.append(f"Chain: `{chain}` | Status: `{status}`")
    if est:
        lines.append(f"Est. Value: `{est}`")
    lines.append(f"Safety: {label} `({score}/10)`")

    if full:
        if desc:
            lines.append(f"\n📝 {desc[:300]}")
        req = airdrop.get("requirements", "")
        if req:
            lines.append(f"\n📋 *How to qualify:*\n{req[:250]}")
        if dl:
            lines.append(f"⏰ Deadline: {dl}")
        if score > 0 and warnings:
            lines.append(f"⚠️ Flags: {', '.join(warnings[:2])}")
        if url:
            lines.append(f"🔗 [Open Airdrop]({url})")
    else:
        if url:
            lines.append(f"🔗 [Details]({url})")

    return "\n".join(lines)


def fmt_digest(airdrops: list, new_ids: list) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    priority = [a for a in airdrops if a.get("chain") in PRIORITY_CHAINS and calculate_scam_score(a)[0] <= 5]
    others   = [a for a in airdrops if a.get("chain") not in PRIORITY_CHAINS and calculate_scam_score(a)[0] <= 2]

    header = (
        f"🦗 *MANTIS TRACKER — Daily Digest*\n"
        f"📅 {date_str}\n"
        f"{'─'*28}\n"
        f"*{len(airdrops)}* total airdrops tracked | *{len(new_ids)}* new today\n\n"
    )

    body = "⭐ *SOL · BTC · ETH · BNB*\n\n"
    for i, a in enumerate(priority[:8], 1):
        body += fmt_card(a, index=i) + "\n\n"

    if others:
        body += f"🌐 *Other Chains* ({len(others)} safe found)\n\n"
        for i, a in enumerate(others[:3], 1):
            body += fmt_card(a, index=i) + "\n\n"

    # Rotating daily safety tip — cycles by day of year
    tip_index = datetime.now().timetuple().tm_yday % len(DAILY_SAFETY_TIPS)
    tip_emoji, tip_text = DAILY_SAFETY_TIPS[tip_index]

    footer = (
        f"{'─'*28}\n"
        f"💡 *Daily Safety Tip:*\n"
        f"{tip_emoji} {tip_text}\n\n"
        f"🛡️ Legit airdrops are always FREE. Never share your seed phrase or password.\n\n"
        f"/airdrops  /new  /filter  /tips  /safety"
    )
    return header + body + footer


# ─── COMMANDS ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id)
    kb = [
        [InlineKeyboardButton("📋 Today's Airdrops", callback_data="c_airdrops"),
         InlineKeyboardButton("🆕 New Today",         callback_data="c_new")],
        [InlineKeyboardButton("⚙️ Chain Filters",     callback_data="c_filter"),
         InlineKeyboardButton("🛡️ Safety Guide",      callback_data="c_safety")],
        [InlineKeyboardButton("💡 Security Tips",     callback_data="c_tips"),
         InlineKeyboardButton("📊 Bot Status",        callback_data="c_status")],
        [InlineKeyboardButton("❓ Help",               callback_data="c_help")],
    ]
    await update.message.reply_text(
        "🦗 *Welcome to MantisTrackerBot!*\n\n"
        "Your personal crypto airdrop radar — powered by real data, "
        "scam-scored for your safety.\n\n"
        "Tracking: SOL ◎ | BTC ₿ | ETH Ξ | BNB 🔶\n\n"
        "📅 Daily digest every morning at *8AM UTC*\n"
        "🛡️ Every listing safety-scored 0–10\n"
        "🔍 Filter by chain, see only what you want\n\n"
        "_Golden Rule: If it asks for your seed phrase or to send "
        "crypto — it's a SCAM. Walk away._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def _send_airdrops(target, user_id: int, new_only: bool = False):
    user_data = get_user(user_id)
    filters   = user_data.get("filters", PRIORITY_CHAINS)
    cache     = load_cache()
    airdrops  = cache.get("airdrops", [])

    if not airdrops:
        await target.reply_text("⏳ Fetching data... try /refresh first.")
        return

    if new_only:
        new_ids  = cache.get("new_ids", [])
        airdrops = [a for a in airdrops if a.get("id") in new_ids]
        header_label = "🆕 *New Airdrops Today*"
    else:
        header_label = "📋 *Current Airdrops*"

    if "ALL" not in filters:
        airdrops = [a for a in airdrops if a.get("chain") in filters]

    safe = [a for a in airdrops if calculate_scam_score(a)[0] <= 5]

    if not safe:
        await target.reply_text(
            "😕 No safe airdrops for your current filters.\n"
            "Use /filter to adjust or /refresh to update.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    lu = cache.get("last_updated", "")
    try:
        lu_fmt = datetime.fromisoformat(lu).strftime("%b %d %H:%M UTC")
    except Exception:
        lu_fmt = "recently"

    msg = (
        f"{header_label} — Updated {lu_fmt}\n"
        f"Showing {min(len(safe), 10)} of {len(safe)} | "
        f"Chains: {', '.join(filters)}\n\n"
    )

    chunks, current = [], msg
    for i, a in enumerate(safe[:10], 1):
        card = fmt_card(a, index=i) + "\n\n"
        if len(current) + len(card) > 3800:
            chunks.append(current)
            current = card
        else:
            current += card
    current += "─────────────────\n/new  /filter  /refresh  /help"
    chunks.append(current)

    for chunk in chunks:
        await target.reply_text(chunk, parse_mode=ParseMode.MARKDOWN,
                                 disable_web_page_preview=True)


async def cmd_airdrops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_airdrops(update.message, update.effective_user.id)


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or (update.callback_query and update.callback_query.message)
    await _send_airdrops(msg, update.effective_user.id, new_only=True)


async def cmd_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    ud       = get_user(user_id)
    current  = ud.get("filters", PRIORITY_CHAINS)
    all_chains = PRIORITY_CHAINS + ["BASE", "ARB", "MATIC", "AVAX", "APT", "SUI", "ALL"]

    kb, row = [], []
    for chain in all_chains:
        em  = CHAIN_EMOJIS.get(chain, "🪙")
        chk = "✅" if chain in current else "⬜"
        row.append(InlineKeyboardButton(f"{chk}{em}{chain}", callback_data=f"f_{chain}"))
        if len(row) == 3:
            kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("💾 Done", callback_data="f_save")])

    text = (
        f"⚙️ *Chain Filters*\n\n"
        f"Active: `{', '.join(current)}`\n\n"
        f"Tap to toggle — ✅ = included in your feed:"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                         reply_markup=InlineKeyboardMarkup(kb))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                                       reply_markup=InlineKeyboardMarkup(kb))


async def cmd_safety(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛡️ *Airdrop Safety Guide*\n\n"
        "*Score Scale:*\n"
        "✅ 0 — Safe\n"
        "🟡 1–2 — Low Risk\n"
        "🟠 3–5 — Moderate Risk (research first)\n"
        "🔴 6–7 — High Risk (likely avoid)\n"
        "☠️ 8–10 — Likely Scam (do not interact)\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🚨 *INSTANT WALK-AWAY signs:*\n"
        "• Asks for seed phrase / private key\n"
        "• Asks you to SEND crypto to claim\n"
        "• Charges any fee to 'activate' claim\n"
        "• Guarantees massive returns\n"
        "• Only contact is a random DM\n\n"
        "⚠️ *Proceed with caution:*\n"
        "• 'Connect wallet' prompts\n"
        "• Extreme urgency / countdown timers\n"
        "• No official website or GitHub\n"
        "• Not on CoinGecko or CoinMarketCap\n\n"
        "✅ *Good signs:*\n"
        "• Listed on CMC / CoinGecko\n"
        "• Verified X account with history\n"
        "• Public GitHub with commits\n"
        "• Security audit completed\n"
        "• 100% free to claim\n\n"
        "_MantisTracker auto-hides drops scored 6+ by default._"
    )
    target = update.message or update.callback_query.message
    await target.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message or update.callback_query.message
    await target.reply_text(TIPS_GUIDE, parse_mode=ParseMode.MARKDOWN)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cache   = load_cache()
    users   = load_users()
    drops   = cache.get("airdrops", [])
    safe_n  = sum(1 for a in drops if calculate_scam_score(a)[0] <= 5)
    flag_n  = len(drops) - safe_n
    lu      = cache.get("last_updated", "Never")
    try:
        lu_fmt = datetime.fromisoformat(lu).strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        lu_fmt = "Never"

    # Count by chain
    chain_counts = {}
    for a in drops:
        c = a.get("chain", "OTHER")
        chain_counts[c] = chain_counts.get(c, 0) + 1
    top_chains = sorted(chain_counts.items(), key=lambda x: -x[1])[:5]
    chain_str = " | ".join(f"{CHAIN_EMOJIS.get(c,'🪙')}{c}:{n}" for c, n in top_chains)

    msg = (
        f"📊 *MantisTrackerBot Status*\n\n"
        f"🕐 Last updated: {lu_fmt}\n"
        f"🪂 Total cached: {len(drops)}\n"
        f"✅ Safe drops: {safe_n}\n"
        f"🚨 Flagged/hidden: {flag_n}\n"
        f"👥 Total users: {len(users)}\n\n"
        f"*By chain:*\n{chain_str}\n\n"
        f"⏰ Next auto-update: 8:00 AM UTC\n"
        f"Priority: SOL ◎ BTC ₿ ETH Ξ BNB 🔶"
    )
    target = update.message or update.callback_query.message
    await target.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Refreshing airdrop data...")
    await _do_update(context)
    await update.message.reply_text("✅ Done! Use /airdrops to see the latest.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🦗 *MantisTrackerBot — Commands*\n\n"
        "/start — Main menu\n"
        "/airdrops — Today's safe list\n"
        "/new — Only new drops since last update\n"
        "/filter — Set chain filters\n"
        "/safety — Scam safety guide\n"
        "/tips — Full crypto security guide\n"
        "/status — Stats & last update\n"
        "/refresh — Force-fetch fresh data\n"
        "/help — This list\n\n"
        "📅 Auto-digest: *8AM UTC daily*\n"
        "🛡️ All listings scam-scored 0–10\n"
        "Chains: SOL ◎ BTC ₿ ETH Ξ BNB 🔶"
    )
    target = update.message or update.callback_query.message
    await target.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    if data == "c_airdrops":
        await _send_airdrops(q.message, q.from_user.id)
    elif data == "c_new":
        await _send_airdrops(q.message, q.from_user.id, new_only=True)
    elif data == "c_filter":
        update._effective_user = q.from_user
        update._message = None
        await cmd_filter(update, context)
    elif data == "c_tips":
        await cmd_tips(update, context)
    elif data == "c_safety":
        await cmd_safety(update, context)
    elif data == "c_status":
        await cmd_status(update, context)
    elif data == "c_help":
        await cmd_help(update, context)
    elif data.startswith("f_"):
        chain = data[2:]
        uid   = q.from_user.id
        ud    = get_user(uid)
        filters = list(ud.get("filters", PRIORITY_CHAINS))

        if chain == "save":
            await q.edit_message_text(
                f"✅ Filters saved: `{', '.join(filters)}`\n\nUse /airdrops to see your list.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if chain == "ALL":
            filters = ["ALL"]
        else:
            if "ALL" in filters: filters = []
            if chain in filters: filters.remove(chain)
            else:                filters.append(chain)
            if not filters:      filters = PRIORITY_CHAINS.copy()

        update_user(uid, {"filters": filters})
        update._effective_user = q.from_user
        update._message = None
        await cmd_filter(update, context)


# ─── SCHEDULED JOB ────────────────────────────────────────────────────────────

async def _do_update(context: ContextTypes.DEFAULT_TYPE):
    cache    = load_cache()
    old_ids  = set(a["id"] for a in cache.get("airdrops", []))
    fresh    = fetch_all_airdrops()
    new_ids  = [a["id"] for a in fresh if a["id"] not in old_ids]

    cache["airdrops"]     = fresh
    cache["last_updated"] = datetime.now().isoformat()
    cache["new_ids"]      = new_ids
    save_cache(cache)
    logger.info(f"✅ Update done: {len(fresh)} total, {len(new_ids)} new")

    # Broadcast digest
    users = load_users()
    digest = fmt_digest(fresh, new_ids)
    sent = 0
    for uid, ud in users.items():
        if not ud.get("notifications", True):
            continue
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=digest,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Could not message {uid}: {e}")
    logger.info(f"📨 Digest sent to {sent}/{len(users)} users")


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    await _do_update(context)


# ─── STARTUP ──────────────────────────────────────────────────────────────────

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start",    "Main menu"),
        BotCommand("airdrops", "Today's safe airdrop list"),
        BotCommand("new",      "New drops since last update"),
        BotCommand("filter",   "Set chain filters"),
        BotCommand("safety",   "Scam safety guide"),
        BotCommand("tips",     "Full crypto security guide"),
        BotCommand("status",   "Bot stats & last update"),
        BotCommand("refresh",  "Force-refresh data now"),
        BotCommand("help",     "All commands"),
    ])
    logger.info("✅ Commands registered")

    # Seed cache on first run
    cache = load_cache()
    if not cache.get("airdrops"):
        logger.info("🌱 Seeding initial airdrop data...")
        drops = fetch_all_airdrops()
        cache["airdrops"]     = drops
        cache["last_updated"] = datetime.now().isoformat()
        cache["new_ids"]      = [a["id"] for a in drops]
        save_cache(cache)
        logger.info(f"✅ Seeded {len(drops)} airdrops")


def main():
    logger.info("🦗 Starting MantisTrackerBot...")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    for cmd, fn in [
        ("start",    cmd_start),
        ("airdrops", cmd_airdrops),
        ("new",      cmd_new),
        ("filter",   cmd_filter),
        ("safety",   cmd_safety),
        ("tips",     cmd_tips),
        ("status",   cmd_status),
        ("refresh",  cmd_refresh),
        ("help",     cmd_help),
    ]:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(on_button))

    app.job_queue.run_daily(
        daily_job,
        time=dtime(hour=DAILY_DIGEST_HOUR, minute=DAILY_DIGEST_MINUTE),
        name="daily_digest",
    )
    logger.info(f"⏰ Daily digest scheduled {DAILY_DIGEST_HOUR:02d}:{DAILY_DIGEST_MINUTE:02d} UTC")
    logger.info("🚀 Bot running — Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
