# Telegram API credentials
TELEGRAM_API_ID = 34506083
TELEGRAM_API_HASH = "5676893fa1c0fe15eca5dbbceb3ab6a2"

# Telegram channel to monitor
TELEGRAM_CHANNEL = "senalesgilbert610"

# Quotex credentials
QUOTEX_EMAIL = "vizcayagilberto@gmail.com"
QUOTEX_PASSWORD = "M@tador610"

# Trading settings
USE_DEMO_ACCOUNT = True  # Set to False for real trading
STARTING_AMOUNT = 1.00  # Step 1 tradGe amount in USD
MARTINGALE_MULTIPLIER = 2.5  # Multiplier for each losing step
MAX_MARTINGALE_STEPS = 9  # Maximum steps before reset
STEPS_PER_SIGNAL = 3  # Number of martingale steps per signal (3 steps per signal, 3 cycles max)

# Martingale structure:
# - 3 steps per signal (cycle)
# - 3 cycles maximum (9 steps total)
# - WIN at any step = reset to Step 1
# - After Step 9 = reset to Step 1
#
# Cycle 1 (Signal 1): Steps 1-3
#   Step 1: $1.00
#   Step 2: $2.50
#   Step 3: $6.25
#
# Cycle 2 (Signal 2): Steps 4-6
#   Step 4: $15.63
#   Step 5: $39.06
#   Step 6: $97.66
#
# Cycle 3 (Signal 3): Steps 7-9
#   Step 7: $244.15
#   Step 8: $610.38
#   Step 9: $1,525.95

# Timing settings
EXECUTE_AT_EXACT_SECOND = 0  # Execute at :00 seconds
TIME_BUFFER_MS = 100  # Buffer before execution time (milliseconds)
