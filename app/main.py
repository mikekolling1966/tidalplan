from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
import os

from app.routers import tides, routing, vessel

app = FastAPI(title="Tidal Router", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Force no-cache on all /static/ responses so browsers always get fresh JS/CSS."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

app.add_middleware(NoCacheStaticMiddleware)

app.include_router(tides.router,   prefix="/api/tides",   tags=["tides"])
app.include_router(routing.router, prefix="/api/route",   tags=["routing"])
app.include_router(vessel.router,  prefix="/api/vessel",  tags=["vessel"])

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(
        os.path.join(frontend_dir, "index.html"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
