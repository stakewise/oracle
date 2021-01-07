from datetime import datetime, timezone

import sys
import time
from loguru import logger
from notifiers.logging import NotificationHandler  # type: ignore

from src.reward_token import RewardToken
from src.settings import (
    WEB3_WS_ENDPOINT,
    WEB3_HTTP_ENDPOINT,
    INJECT_POA_MIDDLEWARE,
    INJECT_STALE_CHECK_MIDDLEWARE,
    INJECT_RETRY_REQUEST_MIDDLEWARE,
    INJECT_LOCAL_FILTER_MIDDLEWARE,
    STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY,
    REPORTER_PRIVATE_KEY,
    BALANCE_WARNING_THRESHOLD,
    BALANCE_ERROR_THRESHOLD,
    APPLY_GAS_PRICE_STRATEGY,
    MAX_TX_WAIT_SECONDS,
    LOG_LEVEL,
)
from src.utils import (
    get_web3_client,
    configure_default_account,
    InterruptHandler,
    check_default_account_balance,
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
        apply_gas_price_strategy=APPLY_GAS_PRICE_STRATEGY,
        max_tx_wait_seconds=MAX_TX_WAIT_SECONDS,
        inject_retry_request=INJECT_RETRY_REQUEST_MIDDLEWARE,
        inject_poa=INJECT_POA_MIDDLEWARE,
        inject_local_filter=INJECT_LOCAL_FILTER_MIDDLEWARE,
        inject_stale_check=INJECT_STALE_CHECK_MIDDLEWARE,
        stale_check_allowable_delay=STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY,
    )

    # setup default account
    configure_default_account(web3_client, REPORTER_PRIVATE_KEY)

    # wait for interrupt
    interrupt_handler = InterruptHandler()

    reward_token_total_rewards = RewardToken(
        w3=web3_client, interrupt_handler=interrupt_handler
    )

    while not interrupt_handler.exit:
        # сheck reporter balance
        check_default_account_balance(
            web3_client, BALANCE_WARNING_THRESHOLD, BALANCE_ERROR_THRESHOLD
        )

        current_datetime = datetime.now(tz=timezone.utc)
        if reward_token_total_rewards.next_update_at > current_datetime:
            logger.info(
                f"Scheduling next rewards update at"
                f" {reward_token_total_rewards.next_update_at}"
            )
            time.sleep(
                (
                    reward_token_total_rewards.next_update_at - current_datetime
                ).total_seconds()
            )

        # update Reward Token total rewards
        reward_token_total_rewards.process()


if __name__ == "__main__":
    main()
