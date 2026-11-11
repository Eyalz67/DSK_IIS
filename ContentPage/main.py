from datetime import datetime
from fastapi import FastAPI

from routers import content_page

# /docs and /redoc load JavaScript from the internet - disabled for the air-gap
app = FastAPI(title="Data Swiss Knife API", docs_url=None, redoc_url=None)

app.include_router(content_page.router)


@app.get("/api/hello")
def hello():
    return {
        "message": "Hello from Python",
        "hebrew_test": "שלום",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
