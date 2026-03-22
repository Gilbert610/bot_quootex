#!/usr/bin/env python3
"""
Quotex Trading Bot

Main entry point that coordinates:
- Telegram signal monitoring
- Signal parsing
- Trade execution with precise timing
- Martingale strategy management

Usage:
    python bot.py           # Run the bot
    python bot.py --test    # Run in test mode (no actual trades)
    python bot.py --stats   # Show current statistics
    python bot.py --reset   # Reset martingale to step 1
"""
import app
import asyncio
import argparse
import signal
import sys
from datetime import datetime

from config import (
    TELEGRAM_CHANNEL, QUOTEX_EMAIL, USE_DEMO_ACCOUNT,
    STARTING_AMOUNT, MAX_MARTINGALE_STEPS, MARTINGALE_MULTIPLIER
)
from telegram_monitor import TelegramMonitor
from signal_parser import TradingSignal, signal_to_dict
from quotex_api import QuotexAPI
from martingale import MartingaleManager
from trade_executor import TradeExecutor


class QuotexTradingBot:
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.telegram = TelegramMonitor()
        self.quotex = QuotexAPI()
        self.martingale = MartingaleManager()
        self.executor = TradeExecutor(self.quotex, self.martingale)
        self.running = False
        self._trade_tasks = []

    async def start(self):
        """Start the trading bot."""
        print("=" * 60)
        print("  QUOTEX TELEGRAM TRADING BOT")
        print("=" * 60)
        print(f"\nMode: {'TEST (no real trades)' if self.test_mode else 'LIVE'}")
        print(f"Account: {'DEMO' if USE_DEMO_ACCOUNT else 'REAL'}")
        print(f"Channel: {TELEGRAM_CHANNEL}")
        print(f"Starting amount: ${STARTING_AMOUNT}")
        print(f"Martingale steps: {MAX_MARTINGALE_STEPS} (x{MARTINGALE_MULTIPLIER})")
        print("-" * 60)
        print("-" * 60)

        # Show current martingale state
        self.martingale.print_step_table()
        print(f"\nCurrent stats: {self.martingale.get_stats()}")
        print("-" * 60)

        # Connect to Telegram
        print("\nConnecting to Telegram...")
        if not await self.telegram.connect():
            print("Failed to connect to Telegram. Exiting.")
            return False

        # Connect to Quotex (unless in test mode)
        if not self.test_mode:
            print("\nConnecting to Quotex...")
            if not await self.quotex.connect():
                print("Failed to connect to Quotex.")
                print("The bot will continue monitoring signals but won't execute trades.")
                print("Check your Quotex credentials in config.py")
            else:
                real, demo = await self.quotex.get_balance()
                print(f"Quotex connected! Balances - Real: ${real:.2f}, Demo: ${demo:.2f}")

        # Set up signal handler
        self.telegram.set_signal_callback(self._on_signal)

        # Start monitoring
        self.running = True
        print("\n" + "=" * 60)
        print("  BOT STARTED - Monitoring for signals...")
        print("=" * 60 + "\n")

        try:
            await self.telegram.start_monitoring()
        except KeyboardInterrupt:
            pass

        return True

    async def _on_signal(self, signal: TradingSignal):
        """Callback when a trading signal is received."""
        print(f"\n{'*' * 50}")
        print(f"SIGNAL RECEIVED at {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'*' * 50}")
        print(f"  Pair: {signal.pair}")
        print(f"  Direction: {signal.direction.upper()}")
        print(f"  Execute at: {signal.execution_time}")
        print(f"  Timeframe: {signal.timeframe}")
        if signal.forecast:
            print(f"  Forecast: {signal.forecast}%")
        if signal.payout:
            print(f"  Payout: {signal.payout}%")
        print(f"{'*' * 50}")
        print(f"  Pair: {signal.pair}")
        print(signal.pair)
        if self.test_mode:
            print("\n[TEST MODE] Would schedule trade but not executing")
            print(f"  Amount would be: ${self.martingale.get_current_trade_amount():.2f}")
            print(f"  Martingale step: {self.martingale.get_current_step()}")
            return

        # Schedule the trade
        trade_task = asyncio.create_task(self.executor.schedule_trade(signal))
        self._trade_tasks.append(trade_task)

    async def stop(self):
        """Stop the bot gracefully."""
        print("\nStopping bot...")
        self.running = False

        # Cancel pending trade tasks
        for task in self._trade_tasks:
            if not task.done():
                task.cancel()

        # Disconnect from services
        await self.telegram.stop()
        await self.quotex.close()

        print("Bot stopped.")


def show_stats():
    """Show current martingale statistics."""
    martingale = MartingaleManager()
    print("\n" + "=" * 40)
    print("  CURRENT STATISTICS")
    print("=" * 40)
    martingale.print_step_table()
    stats = martingale.get_stats()
    print("\nTrading Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("=" * 40)


def reset_martingale():
    """Reset martingale to step 1."""
    martingale = MartingaleManager()
    martingale.reset()
    print("\nMartingale reset to Step 1")
    print(f"Next trade amount: ${martingale.get_current_trade_amount():.2f}")


async def main():
    parser = argparse.ArgumentParser(description="Quotex Telegram Trading Bot")
    parser.add_argument("--test", action="store_true", help="Run in test mode (no actual trades)")
    parser.add_argument("--stats", action="store_true", help="Show current statistics")
    parser.add_argument("--reset", action="store_true", help="Reset martingale to step 1")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.reset:
        reset_martingale()
        return

    # Create and start bot
    bot = QuotexTradingBot(test_mode=args.test)

    # Handle Ctrl+C gracefully
    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(bot.stop())

    try:
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot terminated by user")
