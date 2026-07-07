from fastapi import FastAPI

from app.apis.v1 import auth_routers, chat_routers

app = FastAPI(title="ReMedi API (Chat Demo)")
app.include_router(auth_routers.router)
app.include_router(chat_routers.router)
