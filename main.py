import sys
import time

from loguru import logger
from notifiers.logging import NotificationHandler  # type: ignore

from src.oracle import Oracle
from src.settings import (
    WEB3_WS_ENDPOINT,
    WEB3_WS_ENDPOINT_TIMEOUT,
    WEB3_HTTP_ENDPOINT,
    INJECT_POA_MIDDLEWARE,
    INJECT_STALE_CHECK_MIDDLEWARE,
    INJECT_RETRY_REQUEST_MIDDLEWARE,
    INJECT_LOCAL_FILTER_MIDDLEWARE,
    STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY,
    ORACLE_PRIVATE_KEY,
    BALANCE_WARNING_THRESHOLD,
    BALANCE_ERROR_THRESHOLD,
    APPLY_GAS_PRICE_STRATEGY,
    MAX_TX_WAIT_SECONDS,
    LOG_LEVEL,
    PROCESS_INTERVAL,
    BEACON_CHAIN_RPC_ENDPOINT,
    SEND_TELEGRAM_NOTIFICATIONS,
)
from src.utils import (
    get_web3_client,
    configure_default_account,
    InterruptHandler,
    check_default_account_balance,
    wait_prysm_ready,
    telegram,
)

# Send notification to admins on error
handler = NotificationHandler("telegram")
logger.remove(0)
logger.add(
    sink=sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>"
    " <level>{level}</level> <level>{message}</level>",
    level=LOG_LEVEL,
)
logger.add(handler, level="ERROR", backtrace=False, diagnose=False)


@logger.catch
def main() -> None:
    # setup Web3 client
    web3_client = get_web3_client(
        http_endpoint=WEB3_HTTP_ENDPOINT,
        ws_endpoint=WEB3_WS_ENDPOINT,
        ws_endpoint_timeout=WEB3_WS_ENDPOINT_TIMEOUT,
        apply_gas_price_strategy=APPLY_GAS_PRICE_STRATEGY,
        max_tx_wait_seconds=MAX_TX_WAIT_SECONDS,
        inject_retry_request=INJECT_RETRY_REQUEST_MIDDLEWARE,
        inject_poa=INJECT_POA_MIDDLEWARE,
        inject_local_filter=INJECT_LOCAL_FILTER_MIDDLEWARE,
        inject_stale_check=INJECT_STALE_CHECK_MIDDLEWARE,
        stale_check_allowable_delay=STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY,
    )

    # setup default account
    configure_default_account(web3_client, ORACLE_PRIVATE_KEY)

    # wait for interrupt
    interrupt_handler = InterruptHandler()

    if SEND_TELEGRAM_NOTIFICATIONS:
        # Notify Telegram the oracle is warming up, so that
        # oracle maintainers know the service has restarted
        telegram.notify(
            message=f"Oracle starting with account [{web3_client.eth.default_account}]"
                    f"(https://etherscan.io/address/{web3_client.eth.default_account})",
            parse_mode="markdown",
            raise_on_errors=True,
            disable_web_page_preview=True,
        )

    # wait that node is synced before trying to do anything
    wait_prysm_ready(interrupt_handler, BEACON_CHAIN_RPC_ENDPOINT, PROCESS_INTERVAL)

    oracle = Oracle(w3=web3_client, interrupt_handler=interrupt_handler)

    # check oracle balance
    if SEND_TELEGRAM_NOTIFICATIONS:
        check_default_account_balance(
            w3=web3_client,
            warning_amount=BALANCE_WARNING_THRESHOLD,
            error_amount=BALANCE_ERROR_THRESHOLD,
        )

    while not interrupt_handler.exit:
        # check and perform oracle duties
        oracle.process()

        # wait until next processing time
        time.sleep(PROCESS_INTERVAL)


if __name__ == "__main__":
    main()
