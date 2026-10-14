import os
import time
from aiohttp import web

async def ping_handler(request: web.Request) -> web.Response:
    """Serverni uxlab qolmasligi uchun (keep-alive / healthcheck) javob beruvchi endpoint"""
    return web.json_response({
        "status": "ok",
        "service": "valyutabot",
        "timestamp": time.time(),
        "message": "Bot is alive and running 24/7!"
    })

def create_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", ping_handler)
    app.router.add_get("/ping", ping_handler)
    app.router.add_get("/health", ping_handler)
    return app
