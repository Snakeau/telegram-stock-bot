"""Simple landing page for the Telegram stock bot."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from chatbot.landing_pages import (
    render_features_page,
    render_home_page,
    render_infographics_page,
)

web_app = FastAPI()


@web_app.get("/", response_class=HTMLResponse)
async def root():
    return render_home_page("standalone-web-ui")


@web_app.get("/features", response_class=HTMLResponse)
async def features():
    return render_features_page("standalone-web-ui")


@web_app.get("/infographics", response_class=HTMLResponse)
async def infographics():
    return render_infographics_page("standalone-web-ui")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8001)
