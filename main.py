# main.py
import os
import asyncio
import logging
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.requests import Request
from starlette.routing import Route
from telegram import Update
from telegram.ext import Application

# ... (import your other modules: config, logger, etc.)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
# Render provides this environment variable automatically
APP_URL = os.environ["RENDER_EXTERNAL_URL"] 
PORT = int(os.environ.get("PORT", 8000))

async def telegram_webhook(request: Request):
    """Handle incoming updates from Telegram."""
    app = request.app.state.tg_app
    update = Update.de_json(await request.json(), app.bot)
    await app.process_update(update)
    return Response()

async def health_check(request: Request):
    """Respond to Render's health checks to keep the service alive."""
    return Response("OK")

async def main():
    # --- Your existing bot setup ---
    # ... (Initialize paper_engine, scheduler, telegram_bot)
    # Instead of scheduler.start() and telegram_bot.run_polling(), do:
    
    tg_app = Application.builder().token(TOKEN).build()
    # ... (add your handlers to tg_app)

    # --- Starlette Web Server ---
    app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthz", health_check, methods=["GET"]),
    ])
    app.state.tg_app = tg_app

    # Set webhook
    await tg_app.bot.set_webhook(f"{APP_URL}/telegram")
    logging.info(f"Webhook set to {APP_URL}/telegram")

    # Start server
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
