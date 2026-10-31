from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analyse, gares, lignes, regions

app = FastAPI(
    title="RailGIS Maroc API",
    description="API geospatiale du reseau ferroviaire marocain (ONCF)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lignes.router)
app.include_router(gares.router)
app.include_router(analyse.router)
app.include_router(regions.router)


@app.get("/")
def root():
    return {"service": "RailGIS Maroc API", "status": "ok", "docs": "/docs"}
