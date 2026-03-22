"""
Telegram Channel Monitor

Monitors specified Telegram channel for trading signals
using Telethon library.
"""

import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import Message
from typing import Callable, Optional
from configu2 import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL
from signal_parser import parse_signal, TradingSignal


class TelegramMonitor:
    def __init__(self, session_name: str = "prueb_bot_session2"):
        self.client = TelegramClient(
            session_name,
            TELEGRAM_API_ID,
            TELEGRAM_API_HASH
        )
        self.channel_entity = None
        self.signal_callback: Optional[Callable[[TradingSignal], None]] = None
        self.running = False

    async def connect(self) -> bool:
        """Connect to Telegram and get channel entity."""
        try:
            await self.client.start()
            print("Connected to Telegram")

            # Get channel entity
            try:
                self.channel_entity = await self.client.get_entity(TELEGRAM_CHANNEL)
                print(f"Monitoring channel: {self.channel_entity.title if hasattr(self.channel_entity, 'title') else TELEGRAM_CHANNEL}")
            except Exception as e:
                # Try with t.me link format
                try:
                    self.channel_entity = await self.client.get_entity(f"https://t.me/{TELEGRAM_CHANNEL}")
                    print(f"Monitoring channel: {TELEGRAM_CHANNEL}")
                except:
                    print(f"Could not find channel: {TELEGRAM_CHANNEL}")
                    print("Make sure you're subscribed to the channel.")
                    return False

            return True

        except Exception as e:
            print(f"Telegram connection error: {e}")
            return False

    def set_signal_callback(self, callback: Callable[[TradingSignal], None]):
        """Set callback function to be called when a valid signal is received."""
        self.signal_callback = callback

    async def start_monitoring(self):
        """Start monitoring the channel for new messages."""
        if not self.channel_entity:
            print("Not connected to channel")
            return

        self.running = True
        print(f"\nStarted monitoring {TELEGRAM_CHANNEL} for signals...")
        print("Waiting for trading signals...\n")

        @self.client.on(events.NewMessage(chats=self.channel_entity))
        async def handle_new_message(event: events.NewMessage.Event):
            message: Message = event.message
    
            # Skip empty messages
            if not message.text:
                return

            # Log received message
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New message received:")
            #print(f"{message.text[:100]}..." if len(message.text) > 100 else message.text)

            # Try to parse as trading signal
            signal = parse_signal(message.text)
            txt =  message.text           
            #busq = txt.find("/")
            #print(busq)
            par = (txt[5:11])
            pares= (par.replace("/", ""))
            selec = str(txt[42:46])
            hora =(txt[27:36])
            print(par)
            print(selec)
            print(hora)
            import requests

            TELEGRAM_BOT_TOKEN = "8535869356:AAEt29KFV87aDSatjYWAoLg0yZts4rYvQWs"
            TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            chat_id = "@senalesgilbert610"

            if selec == str("call"):

                message = [
                "QUOTEX Live SIGNALS \n "
                f"🪁 {par}-OTC \n🔥 M5 \n ⏰{hora} \n"
                "📊 call"
                ]
            else:
                message = {
                'QUOTEX Live SIGNALS \n '
                f"🪁 {par}-OTC \n🔥 M5 \n ⏰ {hora} \n"
                '📊 put'
                }

            params = {"chat_id": chat_id, "parse_mode": "HTML", "text": message}
            requests.get(TELEGRAM_API_URL, params=params)
            
            if signal:
                print("\n*** SIGNAL DETECTED ***")
                print("Pair: {signal.pair}")
                print("Direction: {signal.direction.upper()}")
                print("Time: {signal.execution_time}")
                print("Timeframe: {signal.timeframe}")
                print("*" * 25)

                # Call the callback if set
                if self.signal_callback:
                    try:
                        await self.signal_callback(signal)
                    except Exception as e:
                        print(f"Error in signal callback: {e}")
            else:
                print("(Not a trading signal, ignoring)")

        # Keep running until stopped
        while self.running:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop monitoring."""
        self.running = False
        await self.client.disconnect()
        print("Telegram monitor stopped")

    async def get_recent_messages(self, limit: int = 10) -> list:
        """Get recent messages from channel (for testing)."""
        if not self.channel_entity:
            return []

        messages = []
        async for message in self.client.iter_messages(self.channel_entity, limit=limit):
            if message.text:
                messages.append({
                    "id": message.id,
                    "date": message.date.isoformat(),
                    "text": message.text
                })
        return messages


async def test_monitor():
    """Test telegram monitoring."""
    monitor = TelegramMonitor()

    if await monitor.connect():
        # Get recent messages to test signal parsing
        print("\nFetching recent messages...")
        messages = await monitor.get_recent_messages(20)

        print(f"\nFound {len(messages)} recent messages")
        print("\nTesting signal parsing on recent messages:")
        print("-" * 50)

        for msg in messages:
            signal = parse_signal(msg["text"])
            if signal:
                print(f"\nSIGNAL FOUND:")
                print(f"  Date: {msg['date']}")
                print(f"  Pair: {signal.pair}")
                print(f"  Direction: {signal.direction}")
                print(f"  Time: {signal.execution_time}")

        # Define a test callback
        async def on_signal(signal: TradingSignal):
            print(f"\n!!! NEW SIGNAL CALLBACK !!!")
            print(f"Would trade: {signal.pair} {signal.direction} at {signal.execution_time}")

        monitor.set_signal_callback(on_signal)

        print("\n" + "=" * 50)
        print("Starting live monitoring (press Ctrl+C to stop)...")
        print("=" * 50)

        try:
            await monitor.start_monitoring()
        except KeyboardInterrupt:
            print("\nStopping...")

    await monitor.stop()


if __name__ == "__main__":
    asyncio.run(test_monitor())
