from fastapi import FastAPI

from app.apis.v1 import recognition_routers

app = FastAPI(title="ReMedi API (Recognition Demo)")
app.include_router(recognition_routers.router)
