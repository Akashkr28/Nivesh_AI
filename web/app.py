"""
Application entry point.
Creates the FastAPI app, registers all routers, serves static files.
No business logic lives here.
"""

import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.routes.analyze import router as analyze_router
from web.routes.portfolio import router as portfolio_router
from web.routes.alerts import router as alerts_router
from web.routes.narrative import router as narrative_router
from web.routes.search import router as search_router
from web.routes.auth import router as auth_router
from web.auth.database import init_db

app = FastAPI(
    title="NiveshAI",
    description="AI-powered market intelligence for Indian and global stocks",
    version="2.0",
)

# Initialise database on startup
init_db()

# Register all route modules
app.include_router(auth_router)
app.include_router(analyze_router)
app.include_router(portfolio_router)
app.include_router(alerts_router)
app.include_router(narrative_router)
app.include_router(search_router)

# Serve static files (CSS, JS)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing():
    with open(os.path.join(STATIC_DIR, "landing.html")) as f:
        return HTMLResponse(content=f.read())

@app.get("/auth", response_class=HTMLResponse, include_in_schema=False)
async def auth_page():
    with open(os.path.join(STATIC_DIR, "auth.html")) as f:
        return HTMLResponse(content=f.read())

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    with open(os.path.join(STATIC_DIR, "index.html")) as f:
        return HTMLResponse(content=f.read())


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Market Analysis Dashboard")
    print("  http://localhost:8000")
    print("  API docs: http://localhost:8000/docs")
    print("=" * 50 + "\n")
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=False)
