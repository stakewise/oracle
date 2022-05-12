import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def save(func):
    if asyncio.iscoroutinefunction(func):

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except BaseException as e:
                logger.exception(e)

    else:

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseException as e:
                logger.exception(e)

    return wrapper
