import asyncio

from aiohttp import web

from common.settings import HEALTH_SERVER_HOST, HEALTH_SERVER_PORT


def start_health_server(runner):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, HEALTH_SERVER_HOST, HEALTH_SERVER_PORT)
    loop.run_until_complete(site.start())
    loop.run_forever()


def create_health_server_runner(routes):
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    return runner
