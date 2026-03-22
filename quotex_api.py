"""
Quotex Trading API Client

Handles login, trade execution, and result tracking.
Uses pyquotex library for WebSocket-based communication.
"""

import asyncio
import sys
from datetime import datetime
from typing import Optional, Tuple
from config import QUOTEX_EMAIL, QUOTEX_PASSWORD, USE_DEMO_ACCOUNT
from pyquotex.stable_api import Quotex
#from quotexapi.stable_api import Quotex

# Try to import pyquotex
#PYQUOTEX_AVAILABLE = False

#    from quotexapi.stable_api import Quotex
#    PYQUOTEX_AVAILABLE = True
#except ImportError:
 #   try:
 #       # Alternative import path
 #       from pyquotex.quotexapi.stable_api import Quotex
 #       PYQUOTEX_AVAILABLE = True
#    except ImportError:
#        pass


class QuotexAPI:
    def __init__(self):
        self.client = True
        self.logged_in = True
        self.is_demo = USE_DEMO_ACCOUNT
        self._pending_trades = {}
        self._trade_results = {}

    async def connect(self) -> bool:
        """Initialize and connect to Quotex."""
        #if not PYQUOTEX_AVAILABLE:
        #    print("pyquotex library not available")
        ##    print("Install with: pip install git+https://github.com/cleitonleonel/pyquotex.git")
        #    return False

        try:
            # Initialize client
            self.client = Quotex(
                email=QUOTEX_EMAIL,
                password=QUOTEX_PASSWORD,
                lang="pt"
            )

            # Set account type before connecting
            if self.is_demo:
                self.client.set_account_mode("PRACTICE")
            else:
                self.client.set_account_mode("REAL")

            # Connect to Quotex
            print("Connecting to Quotex...")
            check, reason = await self.client.connect()

            if check:
                self.logged_in = True
                account_type = "DEMO" if self.is_demo else "REAL"
                print(f"Connected to Quotex ({account_type} account)")

                # Get initial balance
                balance = await self.client.get_balance()
                print(f"Account balance: ${balance:.2f}")
                return True
            else:
                print(f"Quotex connection failed: {reason}")
                return False

        except Exception as e:
            print(f"Quotex connection error: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def get_balance(self) -> Tuple[float, float]:
        """Get current balance."""
        if not self.logged_in or not self.client:
            return 0.0, 0.0

        try:
            balance = await self.client.get_balance()
            if self.is_demo:
                return 0.0, balance
            else:
                return balance, 0.0
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0, 0.0

    async def place_trade(
        self,
        pair: str,
        direction: str,
        amount: float,
        duration: int = 60
    ) -> Optional[str]:
        """
        Place a trade on Quotex.

        Args:
            pair: Trading pair (e.g., "EURGBP-OTC")
            direction: "call" or "put"
            amount: Trade amount in USD
            duration: Trade duration in seconds (default 60 for M1)

        Returns:
            Trade ID if successful, None otherwise
        """
        if not self.logged_in or not self.client:
            print("Not connected to Quotex")
            return None

        try:
            # Format asset name for pyquotex
            # Convert "EURGBP-OTC" to "EURGBP_otc" format
            asset = pair.replace("-OTC", "_otc")
            if not asset.endswith("_otc") and "-OTC" not in pair:
                asset = pair  # Use as-is if no OTC suffix

            print(f"Checking asset availability: {asset}")

            # Check if asset is available
            asset_name, asset_data = await self.client.get_available_asset(
                asset,
                force_open=True
            )

            

            print(f"Placing trade: {asset_name} {direction.upper()} ${amount} for {duration}s")

            # Place the trade
            # direction should be "call" or "put"
            status, trade_info = await self.client.buy(
                amount=amount,
                asset=asset_name,
                direction=direction.lower(),
                duration=duration
            )

            if status:
                trade_id = str(trade_info.get("id", datetime.now().timestamp()))
                print(f"Trade placed successfully! ID: {trade_id}")

                self._pending_trades[trade_id] = {
                    "pair": pair,
                    "asset_name": asset_name,
                    "direction": direction,
                    "amount": amount,
                    "duration": duration,
                    "time": datetime.now().isoformat(),
                    "info": trade_info
                }
                return trade_id
            else:
                print(f"Trade failed: {trade_info}")
                return None

        except Exception as e:
            print(f"Error placing trade: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def check_trade_result(self, trade_id: str, timeout: int = 120) -> Optional[str]:
        """
        Check the result of a trade by waiting for it to complete.

        Returns:
            "win", "loss", or None if unable to determine
        """
        if not self.logged_in or not self.client:
            return None

        try:
            trade_info = self._pending_trades.get(trade_id, {})
            duration = trade_info.get("duration", 60)

            # Wait for the trade to complete
            print(f"Waiting {duration}s for trade to complete...")
            await asyncio.sleep(duration + 5)

            # Try to check result via sell_option or balance change
            try:
                # Get current balance and compare
                new_balance = await self.client.get_balance()

                # Check if we can get the trade result directly
                if hasattr(self.client, 'check_win') and callable(self.client.check_win):
                    result = await self.client.check_win(trade_id)
                    if result is not None:
                        if result > 0:
                            self._trade_results[trade_id] = "win"
                            return "win"
                        else:
                            self._trade_results[trade_id] = "loss"
                            return "loss"

                # Fallback: unable to determine automatically
                print("Trade completed. Check result manually or based on balance.")
                return None

            except Exception as e:
                print(f"Error checking result: {e}")
                return None

        except Exception as e:
            print(f"Error checking trade result: {e}")
            return None

    async def close(self):
        """Close connection and cleanup."""
        if self.client:
            try:
                self.client.close()
            except:
                pass
        self.logged_in = False
        print("Quotex connection closed")

    def is_connected(self) -> bool:
        """Check if connected and logged in."""
        return self.logged_in and self.client is not None


async def test_connection():
    """Test Quotex connection."""
    api = QuotexAPI()

    print("Testing Quotex connection...")
    print(f"Email: {QUOTEX_EMAIL}")
    print(f"Demo mode: {USE_DEMO_ACCOUNT}")
    print(f"PyQuotex available: {PYQUOTEX_AVAILABLE}")

    if await api.connect():
        print("\nConnection successful!")
        real, demo = await api.get_balance()
        print(f"Balance - Real: ${real:.2f}, Demo: ${demo:.2f}")

        # Test trade placement (demo only)
        if USE_DEMO_ACCOUNT:
            print("\nTesting trade placement...")
            trade_id = await api.place_trade("EURUSD_otc", "call", 1.00, 60)
            if trade_id:
                print(f"Test trade placed: {trade_id}")
    else:
        print("\nConnection failed!")
        print("\nTroubleshooting:")
        print("1. Check your email/password in config.py")
        print("2. Make sure you can login at quotex.io manually")
        print("3. Try: pip install git+https://github.com/cleitonleonel/pyquotex.git")

    await api.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
