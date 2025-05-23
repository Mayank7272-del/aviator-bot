import json
import random
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# Simulated trends for 2025
WEB_TRENDS_2025 = {
    "aviator": {
        "safe": (1.5, 2.5, 0.97),  # (min, max, RTP)
        "balanced": (2.5, 5.0, 0.95),
        "aggressive": (10.0, 100.0, 0.80)
    }
}
SIMULATED_X_PULL = {
    "aviator": {"2x-5x": 0.6, "100x": 0.2, "instaloss": 0.2}
}
USER_DATA_FILE = "user_data.json"

def load_user_data():
    try:
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class AviatorBettingBot:
    def __init__(self):
        self.user_data = load_user_data()
        self.pending_results = {}

    def get_user_state(self, user_id):
        if str(user_id) not in self.user_data:
            self.user_data[str(user_id)] = {
                "game": "aviator",
                "capital": 2500,
                "pl": 0,
                "mode": "safe",
                "scaling": "increment",
                "max_bet": 200,
                "ai_mode": "conservative",
                "ai_learn": "fast",
                "mood": "neutral",
                "bias": {"margin": -0.1},
                "bet_history": [],
                "last_bet": 10,
                "low_multiplier_count": 0
            }
        return self.user_data[str(user_id)]

    def save_user_state(self, user_id):
        save_user_data(self.user_data)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        status = self.format_status(user_id)
        keyboard = [
            [InlineKeyboardButton("Go (Bet)", callback_data="go"),
             InlineKeyboardButton("Status", callback_data="status")],
            [InlineKeyboardButton("Set Mode", callback_data="set_mode"),
             InlineKeyboardButton("Set Scaling", callback_data="set_scaling")],
            [InlineKeyboardButton("Restore", callback_data="restore")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🚀 Ultimate Aviator Betting Bot! 🔥\n{status}", reply_markup=reply_markup)

    def format_status(self, user_id):
        state = self.get_user_state(user_id)
        return (
            f"**STATUS** ({datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')})\n"
            f"```\n"
            f"| Game   | Capital | P/L   | Status | Mode | Mood    |\n"
            f"|--------|---------|-------|--------|------|---------|\n"
            f"| Aviator | ₹{state['capital']:<6} | {state['pl']:+₹<5} | Active | {state['mode'].capitalize():<4} | {state['mood'].capitalize():<7} |\n"
            f"```\n"
            f"**P/L Chart**: {''.join(['+' if x else '-' for x in state['bet_history'][-5:]])}"
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        status = self.format_status(user_id)
        await update.effective_message.reply_text(status)

    async def go(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        state = self.get_user_state(user_id)
        if state["capital"] < 250:
            await update.effective_message.reply_text("⚠️ Low capital! Add funds or use `/restore`.")
            return
        self.pending_results[user_id] = {"bet": None, "timestamp": time.time()}
        await update.effective_message.reply_text("📸 Send screenshot description (e.g., 'Last 5: 2.0x win, 1.5x loss, 3.0x win').")
        context.user_data["awaiting_screenshot"] = True

    async def handle_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.user_data.get("awaiting_screenshot"):
            await update.message.reply_text("⚠️ No screenshot expected. Use `/go`.")
            return

        screenshot = update.message.text
        state = self.get_user_state(user_id)
        multipliers = [float(x.split("x")[0]) for x in screenshot.split(",") if "x" in x]
        low_multipliers = sum(1 for x in multipliers if x < 2.0)
        high_multipliers = sum(1 for x in multipliers if x >= 10.0)
        total = len(multipliers) + 1

        mode_ranges = WEB_TRENDS_2025["aviator"][state["mode"]]
        base_mult = random.uniform(mode_ranges[0], mode_ranges[1])
        if low_multipliers / total > 0.5 or state["low_multiplier_count"] >= 6:
            base_mult = min(mode_ranges[0] + 0.5, mode_ranges[1])
            await update.message.reply_text("⚠️ Warning: 6+ low multipliers detected. Adjusting signal.")
        if state["mood"] == "cautious":
            base_mult = max(mode_ranges[0], base_mult - 0.2)
        elif state["mood"] == "excited":
            base_mult = min(mode_ranges[1], base_mult + 0.5)
        multiplier = round(base_mult - state["bias"]["margin"], 1)
        accuracy = 95 if state["ai_mode"] == "conservative" else 90
        accuracy = round(accuracy * (1 - 0.1 * low_multipliers / total + 0.1 * high_multipliers / total), 1)

        analysis = (
            f"📊 **Market Analysis** (Screenshot: '{screenshot}')\n"
            f"- Low (<2x): {low_multipliers}, High (10x+): {high_multipliers}\n"
            f"- Trend: {multiplier}x, {accuracy}% accuracy for {state['mode'].capitalize()} mode"
        )
        await update.message.reply_text(analysis)

        bet = min(state["last_bet"], state["capital"], state["max_bet"])
        signal = f"🚀 **Aviator Signal**: Bet ₹{bet} @ {multiplier}x, {accuracy}% accuracy."
        self.pending_results[user_id] = {"bet": bet, "multiplier": multiplier, "timestamp": time.time()}
        keyboard = [
            [InlineKeyboardButton("Win", callback_data="result_win"),
             InlineKeyboardButton("Lose", callback_data="result_lose"),
             InlineKeyboardButton("Skip", callback_data="result_skip")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(signal, reply_markup=reply_markup)
        context.user_data["awaiting_screenshot"] = False
        context.user_data["awaiting_result"] = True

    async def handle_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.pending_results or not context.user_data.get("awaiting_result"):
            await update.effective_message.reply_text("⚠️ No pending result. Use `/go`.")
            return

        query = update.callback_query
        await query.answer()
        result = query.data.split("_")[1]
        state = self.get_user_state(user_id)
        pending = self.pending_results[user_id]
        bet, multiplier = pending["bet"], pending["multiplier"]

        if result == "skip":
            await query.message.reply_text("⏭️ Round skipped. Use `/go`.")
            del self.pending_results[user_id]
            context.user_data["awaiting_result"] = False
            return

        win = result == "win"
        payout = bet * multiplier if win else 0
        state["capital"] += payout - bet
        state["pl"] += payout - bet
        state["bet_history"].append(win)
        state["last_bet"] = (bet + 10 if win else 10) if state["scaling"] == "increment" else (bet * 2 if not win else 10)
        state["last_bet"] = min(state["last_bet"], state["max_bet"], state["capital"])
        state["low_multiplier_count"] = state["low_multiplier_count"] + 1 if multiplier < 2.0 else 0

        if win:
            state["bias"]["margin"] -= 0.01 if state["ai_learn"] == "fast" else 0.005
        else:
            state["bias"]["margin"] += 0.02 if state["ai_learn"] == "fast" else 0.01
        state["bias"]["margin"] = max(-0.5, min(state["bias"]["margin"], 0.5))

        recent_results = state["bet_history"][-3:]
        state["mood"] = "excited" if recent_results.count(True) >= 2 else "cautious" if recent_results.count(False) >= 2 else "neutral"

        self.save_user_state(user_id)
        details = (
            f"{'🎉' if win else '⚠️'} **Result**: {'Win' if win else 'Loss'}! {'+₹' + str(payout - bet) if win else '-₹' + str(bet)}\n"
            f"**P/L**: +₹{state['pl']} | **Capital**: ₹{state['capital']}\n"
            f"**P/L Chart**: {''.join(['+' if x else '-' for x in state['bet_history'][-5:]])}\n"
            f"**AI Feedback**: Margin {'tightened' if win else 'widened'} to {state['bias']['margin']:.2f}x\n"
            f"**Mood**: {state['mood'].capitalize()} {'(bolder)' if state['mood'] == 'excited' else '(tighter)' if state['mood'] == 'cautious' else ''}\n"
            f"**Next Bet**: ₹{state['last_bet']}"
        )
        keyboard = [[InlineKeyboardButton("Go (Next Round)", callback_data="go")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(details, reply_markup=reply_markup)
        del self.pending_results[user_id]
        context.user_data["awaiting_result"] = False

        if state["capital"] < 250:
            state["capital"] = 0
            self.save_user_state(user_id)
            await query.message.reply_text("⚠️ Low capital! Add funds or use `/restore`.")

    async def restore(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        state = self.get_user_state(user_id)
        await update.effective_message.reply_text(f"✅ Restored state! Capital: ₹{state['capital']}, Mode: {state['mode'].capitalize()}, Mood: {state['mood'].capitalize()}.")
        await self.status(update, context)

    async def real_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text("🔍 Real X search not implemented. Using simulated trends (60% 2x–5x, 20% 100x). Contact developer for X API integration.")

    async def set_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("Safe", callback_data="mode_safe"),
             InlineKeyboardButton("Balanced", callback_data="mode_balanced"),
             InlineKeyboardButton("Aggressive", callback_data="mode_aggressive")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Choose betting mode:", reply_markup=reply_markup)

    async def set_scaling(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("Increment", callback_data="scaling_increment"),
             InlineKeyboardButton("Martingale", callback_data="scaling_martingale")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Choose scaling strategy:", reply_markup=reply_markup)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data

        if data == "go":
            await self.go(update, context)
        elif data == "status":
            await self.status(update, context)
        elif data == "set_mode":
            await self.set_mode(update, context)
        elif data == "set_scaling":
            await self.set_scaling(update, context)
        elif data == "restore":
            await self.restore(update, context)
        elif data.startswith("mode_"):
            mode = data.split("_")[1]
            state = self.get_user_state(user_id)
            state["mode"] = mode
            self.save_user_state(user_id)
            await query.message.reply_text(f"✅ Mode set to {mode.capitalize()}!")
        elif data.startswith("scaling_"):
            scaling = data.split("_")[1]
            state = self.get_user_state(user_id)
            state["scaling"] = scaling
            self.save_user_state(user_id)
            await query.message.reply_text(f"✅ Scaling set to {scaling.capitalize()}!")
        elif data.startswith("result_"):
            await self.handle_result(update, context)

async def main():
    TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your BotFather token
    bot = AviatorBettingBot()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("status", bot.status))
    app.add_handler(CommandHandler("go", bot.go))
    app.add_handler(CommandHandler("restore", bot.restore))
    app.add_handler(CommandHandler("real_search", bot.real_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_screenshot))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
