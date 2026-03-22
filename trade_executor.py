"""
Trade Executor

Handles precise timing for trade execution at exact :00 seconds.
Coordinates between signal reception and trade placement.

Martingale logic:
- 3 steps per signal
- If all 3 steps lose, wait for next signal
- Continue martingale from where we left off
- Max 3 cycles (9 steps total)
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional
from signal_parser import TradingSignal
from martingale import MartingaleManager
from quotex_api import QuotexAPI
from config import EXECUTE_AT_EXACT_SECOND, TIME_BUFFER_MS, STEPS_PER_SIGNAL


class TradeExecutor:
    def __init__(self, quotex_api: QuotexAPI, martingale: MartingaleManager):
        self.api = quotex_api
        self.martingale = martingale
        self.pending_signals: list[TradingSignal] = []
        self.executed_trades: list[dict] = []
        self._scheduler_running = False

    async def schedule_trade(self, signal: TradingSignal):
        """
        Schedule a trade for execution at the signal's specified time.
        Handles up to 3 martingale steps per signal.
        """
        now = datetime.now()
        target_time = datetime.combine(now.date(), signal.execution_time)

        # If target time is in the past (for today), it might be for tomorrow
        if target_time < now:
            # Check if it's just a few seconds in the past (signal delay)
            if (now - target_time).total_seconds() < 60:
                # Execute immediately if within a minute
                print(f"Signal time passed by {(now - target_time).total_seconds():.1f}s, executing immediately")
                await self._execute_signal_cycle(signal)
                return
            else:
                # Signal is old, skip
                print(f"Signal time {signal.execution_time} has passed, skipping")
                return

        # Calculate wait time
        target_second = target_time.replace(microsecond=0)
        wait_seconds = (target_second - now).total_seconds()

        # Subtract a small buffer to account for execution time
        wait_seconds -= (TIME_BUFFER_MS / 1000)

        if wait_seconds > 0:
            print(f"Scheduled trade for {signal.execution_time} (waiting {wait_seconds:.2f}s)")
            self.pending_signals.append(signal)

            # Wait until execution time
            await asyncio.sleep(wait_seconds)

            # Final precision wait to hit exactly :00
            await self._precise_wait_until(target_second)

        # Execute the signal cycle (up to 3 trades)
        await self._execute_signal_cycle(signal)

    async def _precise_wait_until(self, target: datetime):
        """
        Precision wait until exact target time using busy-wait for final milliseconds.
        """
        while datetime.now() < target:
            remaining = (target - datetime.now()).total_seconds()
            if remaining > 0.1:
                await asyncio.sleep(0.05)
            elif remaining > 0:
                # Busy wait for final 100ms
                pass
            else:
                break

    async def _execute_signal_cycle(self, signal: TradingSignal):
        """
        Execute a signal cycle - up to 3 martingale trades per signal.
        """
        # Start new signal cycle
        self.martingale.start_new_signal()

        # Get duration from timeframe
        duration = self._timeframe_to_seconds(signal.timeframe)

        # Execute up to STEPS_PER_SIGNAL trades (3 per signal)
        for step_in_signal in range(STEPS_PER_SIGNAL):
            trade_amount = self.martingale.get_current_trade_amount()
            current_step = self.martingale.get_current_step()
            current_cycle = self.martingale.get_current_cycle()

            execution_time = datetime.now()

            print(f"\n{'='*60}")
            print(f"EXECUTING TRADE at {execution_time.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"  Pair: {signal.pair}")
            print(f"  Direction: {signal.direction.upper()}")
            print(f"  Amount: ${trade_amount:.2f}")
            print(f"  Step {current_step} of 9 (Cycle {current_cycle}, trade {step_in_signal + 1}/{STEPS_PER_SIGNAL} in signal)")
            print(f"{'='*60}")

            # Place the trade
            trade_id = await self.api.place_trade(
                pair=signal.pair,
                direction=signal.direction,
                amount=trade_amount,
                duration=duration
            )
            
            if trade_id:
                print(f"Trade placed successfully! ID: {trade_id}")

                # Record trade
                trade_record = {
                    "id": trade_id,
                    "signal": signal,
                    "amount": trade_amount,
                    "step": current_step,
                    "cycle": current_cycle,
                    "step_in_signal": step_in_signal + 1,
                    "execution_time": execution_time.isoformat(),
                    "target_time": signal.execution_time.strftime("%H:%M:%S"),
                    "time_diff_ms": (execution_time - datetime.combine(
                        execution_time.date(), signal.execution_time
                    )).total_seconds() * 1000
                }
                self.executed_trades.append(trade_record)

                print(f"Execution time offset: {trade_record['time_diff_ms']:.1f}ms")

                # Wait for trade result
                print(f"Waiting for trade result (duration: {duration}s)...")
                result = await self.api.check_trade_result(trade_id, timeout=duration + 30)

                if result == "win":
                    # Calculate profit
                    payout = signal.payout / 100 if signal.payout else 0.85
                    profit = trade_amount * payout
                    self.martingale.record_win(profit)
                    print(f"\n*** WIN! Profit: ${profit:.2f} ***")
                    print("Martingale reset to Step 1. Waiting for next signal...")
                    self._print_stats()
                    break  # Exit signal cycle on win

                elif result == "loss":
                    can_continue = self.martingale.record_loss()
                    print(f"\n*** LOSS! Lost: ${trade_amount:.2f} ***")

                    if not can_continue:
                        # Signal cycle complete (3 steps done) or max step reached
                        print("\nSignal cycle complete. Waiting for next signal...")
                        self._print_stats()
                        break
                    else:
                        # More steps available in this signal, continue immediately
                        print(f"\nContinuing to next step...")
                        self._print_stats()
                        # Small delay between trades
                        await asyncio.sleep(2)
                else:
                    print(f"\nUnable to determine result, check manually")
                    break

            else:
                print("Failed to place trade!")
                break

        # Remove from pending
        if signal in self.pending_signals:
            self.pending_signals.remove(signal)

    def _print_stats(self):
        """Print current statistics."""
        stats = self.martingale.get_stats()
        print(f"\nCurrent Stats:")
        print(f"  Next amount: {stats['current_amount']} (Step {stats['current_step']}, Cycle {stats['current_cycle']})")
        print(f"  Steps in signal: {stats['steps_in_signal']}")
        print(f"  Total P/L: {stats['total_profit']}")
        print(f"  Win rate: {stats['win_rate']}")

    def _timeframe_to_seconds(self, timeframe: str) -> int:
        """Convert timeframe string to seconds."""
        timeframe = timeframe.upper()
        if timeframe == "M1":
            return 60
        elif timeframe == "M5":
            return 300
        elif timeframe == "M15":
            return 900
        elif timeframe == "M30":
            return 1800
        elif timeframe == "H1":
            return 3600
        else:
            return 60

    def get_pending_count(self) -> int:
        """Get number of pending trades."""
        return len(self.pending_signals)

    def get_executed_count(self) -> int:
        """Get number of executed trades."""
        return len(self.executed_trades)


async def test_executor():
    """Test trade executor with mock data."""
    from signal_parser import TradingSignal
    from datetime import time

    api = QuotexAPI()
    martingale = MartingaleManager(state_file="test_martingale.json")

    executor = TradeExecutor(api, martingale)

    now = datetime.now()
    target = now + timedelta(seconds=10)

    test_signal = TradingSignal(
        pair="EURUSD-OTC",
        timeframe="M1",
        execution_time=time(target.hour, target.minute, target.second),
        direction="call"
    )

    print(f"Current time: {now.strftime('%H:%M:%S')}")
    print(f"Test signal scheduled for: {test_signal.execution_time}")


if __name__ == "__main__":
    asyncio.run(test_executor())
