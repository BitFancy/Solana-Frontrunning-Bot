from solders.pubkey import Pubkey
import os
from dotenv import load_dotenv

load_dotenv()

PUMP_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
PUMP_GLOBAL = Pubkey.from_string("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
PUMP_EVENT_AUTHORITY = Pubkey.from_string(
    "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"
)
PUMP_FEE = Pubkey.from_string("CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
SYSTEM_TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)
SYSTEM_RENT = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
SOL = Pubkey.from_string("So11111111111111111111111111111111111111112")

TOKEN_DECIMALS = 6

# Global constants

LAMPORTS_PER_SOL = 1_000_000_000

# RPC
RPC_TOKEN = os.getenv('RPC_TOKEN')
# RPC ENDPOINTS
RPC_ENDPOINT = os.getenv('RPC_ENDPOINT')
RPC_WEBSOCKET = os.getenv('RPC_WEBSOCKET')
# GRPC GEYSER
GEYSER_ADDRESS = os.getenv('GEYSER_ADDRESS')

PAYER_PRIVATE_KEY = os.getenv('PAYER_PRIVATE_KEY')

