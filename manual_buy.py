import asyncio
import base64
import struct
import base58

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts

from solders.message import MessageV0
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.transaction import VersionedTransaction
from solders.compute_budget import set_compute_unit_price
from solders.hash import Hash

import spl.token.instructions as spl_token
from spl.token.instructions import get_associated_token_address
from construct import Struct, Int64ul, Flag, Byte, Bytes, Padding
from grpc_connection import GRPCConnection

from constants import (
    PUMP_EVENT_AUTHORITY,
    PUMP_FEE,
    PUMP_GLOBAL,
    PUMP_PROGRAM,
    SYSTEM_PROGRAM,
    SYSTEM_RENT,
    SYSTEM_TOKEN_PROGRAM,
    RPC_ENDPOINT,
    TOKEN_DECIMALS,
    LAMPORTS_PER_SOL,
    PAYER_PRIVATE_KEY,
)


grpc_connection = GRPCConnection()


class BondingCurveState:
    _STRUCT = Struct(
        "virtual_token_reserves" / Int64ul,
        "virtual_sol_reserves" / Int64ul,
        "real_token_reserves" / Int64ul,
        "real_sol_reserves" / Int64ul,
        "token_total_supply" / Int64ul,
        "complete" / Flag,
    )

    def __init__(self, data: bytes) -> None:
        parsed = self._STRUCT.parse(data[8:])
        self.__dict__.update(parsed)


PumpfunProgramDataStruct = Struct(
    Padding(8),
    "mint" / Bytes(32),
    "solAmount" / Int64ul,
    "tokenAmount" / Int64ul,
    "isBuy" / Byte,
    "user" / Bytes(32),
    "timestamp" / Int64ul,
    "virtualSolReserves" / Int64ul,
    "virtualTokenReserves" / Int64ul,
    "realSolReserves" / Int64ul,
    "realTokenReserves" / Int64ul,
)


def get_pumpfun_decoded_data(log: str):
    pump_log = log.split(" ").pop()
    decoded_bytes = base64.b64decode(pump_log)

    if len(decoded_bytes) == 129:
        return PumpfunProgramDataStruct.parse(decoded_bytes)
    return None


async def buy_token(
    mint: Pubkey,
    bonding_curve: Pubkey,
    associated_bonding_curve: Pubkey,
    amount: float,
    slippage: float = 0.20,
    max_retries=1,
    virtual_sol_reserves: int = 0,
    virtual_token_reserves: int = 0,
    priority_fee: int = 0,
):
    payer = Keypair.from_base58_string(PAYER_PRIVATE_KEY)

    async with AsyncClient(RPC_ENDPOINT) as client:
        associated_token_account = get_associated_token_address(payer.pubkey(), mint)
        amount_lamports = int(amount * LAMPORTS_PER_SOL)

        # Fetch the token price
        token_price_sol = (virtual_sol_reserves / LAMPORTS_PER_SOL) / (
            virtual_token_reserves / 10**TOKEN_DECIMALS
        )
        token_amount = amount / token_price_sol

        # Calculate maximum SOL to spend with slippage
        max_amount_lamports = int(amount_lamports * (1 + slippage))
        latest_block = grpc_connection.get_latest_block()
        _blockhash = latest_block.blockhash

        # Continue with the buy transaction
        for attempt in range(max_retries):
            try:
                accounts = [
                    AccountMeta(pubkey=PUMP_GLOBAL, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=PUMP_FEE, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
                    AccountMeta(
                        pubkey=bonding_curve, is_signer=False, is_writable=True
                    ),
                    AccountMeta(
                        pubkey=associated_bonding_curve,
                        is_signer=False,
                        is_writable=True,
                    ),
                    AccountMeta(
                        pubkey=associated_token_account,
                        is_signer=False,
                        is_writable=True,
                    ),
                    AccountMeta(
                        pubkey=payer.pubkey(), is_signer=True, is_writable=True
                    ),
                    AccountMeta(
                        pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False
                    ),
                    AccountMeta(
                        pubkey=SYSTEM_TOKEN_PROGRAM, is_signer=False, is_writable=False
                    ),
                    AccountMeta(pubkey=SYSTEM_RENT, is_signer=False, is_writable=False),
                    AccountMeta(
                        pubkey=PUMP_EVENT_AUTHORITY, is_signer=False, is_writable=False
                    ),
                    AccountMeta(
                        pubkey=PUMP_PROGRAM, is_signer=False, is_writable=False
                    ),
                ]

                discriminator = struct.pack("<Q", 16927863322537952870)
                data = (
                    discriminator
                    + struct.pack("<Q", int(token_amount * 10**6))
                    + struct.pack("<Q", max_amount_lamports)
                )
                buy_ix = Instruction(PUMP_PROGRAM, data, accounts)
                create_ata_ix = spl_token.create_idempotent_associated_token_account(
                    payer=payer.pubkey(), owner=payer.pubkey(), mint=mint
                )

                msg = MessageV0.try_compile(
                    payer.pubkey(),
                    [create_ata_ix, set_compute_unit_price(priority_fee), buy_ix],
                    address_lookup_table_accounts=[],
                    recent_blockhash=Hash.from_string(_blockhash),
                )
                tx_buy = await client.send_transaction(
                    VersionedTransaction(
                        msg,
                        [payer],
                    ),
                    opts=TxOpts(skip_preflight=True, preflight_commitment=Confirmed),
                )

                print(
                    f"Transaction sent: https://explorer.solana.com/tx/{tx_buy.value}"
                )

                return

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)[:50]}")
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    print(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    print("Max retries reached. Unable to complete the transaction.")


def get_bonding_curve(mint_pubkey: Pubkey, program_pubkey: Pubkey) -> Pubkey:
    seeds_to_try = [
        b"bonding-curve",
    ]

    for seed in seeds_to_try:
        bonding_curve, bump = Pubkey.find_program_address(
            [seed, bytes(mint_pubkey)], program_pubkey
        )
        print(f"Seed: {seed}, Bonding Curve: {bonding_curve}, Bump: {bump}")
        return bonding_curve


async def listen_for_create_transaction(response_stream):

    for response in response_stream:
        try:
            txn = grpc_connection.parse_response(response)
            if not txn:
                continue

            for log in txn.meta.log_messages:
                if "Program data:" in log:
                    signature = base58.b58encode(txn.signature).decode("utf-8")
                    print("transaction", signature)
                    decoded_data = get_pumpfun_decoded_data(log)
                    if decoded_data and decoded_data["isBuy"] == 1:
                        mint = Pubkey.from_bytes(decoded_data["mint"])
                        bonding_curve = get_bonding_curve(mint, PUMP_PROGRAM)

                        associated_bonding_curve = (
                            spl_token.get_associated_token_address(
                                owner=bonding_curve,
                                mint=mint,
                                token_program_id=SYSTEM_TOKEN_PROGRAM,
                            )
                        )

                        # Amount of SOL to spend (adjust as needed)
                        amount = 0.001

                        await buy_token(
                            mint,
                            bonding_curve,
                            associated_bonding_curve,
                            amount,
                            virtual_token_reserves=decoded_data["virtualTokenReserves"],
                            virtual_sol_reserves=decoded_data["virtualSolReserves"],
                            priority_fee=500_000,
                            slippage=0.3,
                        )
        except Exception as e:
            await asyncio.sleep(1)


async def main():
    grpc_connection.init()
    stream = grpc_connection.connect()
    await listen_for_create_transaction(stream)


if __name__ == "__main__":
    asyncio.run(main())
