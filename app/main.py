import os
from dotenv import load_dotenv

from account.adapter.input.web.account_router import account_router
from config.database.session import Base, engine
from documents_multi_agents.adapter.input.web.document_multi_agent_router import documents_multi_agents_router
from kftc.adapter.input.web.kftc_router import kftc_router
from sosial_oauth.adapter.input.web.google_oauth2_router import authentication_router

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

origins = [
    "http://localhost:3000",  # Next.js 프론트 엔드 URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 정확한 origin만 허용
    allow_credentials=True,      # 쿠키 허용
    allow_methods=["*"],         # 모든 HTTP 메서드 허용
    allow_headers=["*"],         # 모든 헤더 허용
)

app.include_router(account_router, prefix="/account")
app.include_router(authentication_router, prefix="/authentication")
app.include_router(documents_multi_agents_router, prefix="/documents-multi-agents")
app.include_router(documents_multi_agents_router, prefix="/flow")  # 프론트엔드 호환용
app.include_router(kftc_router, prefix="/kftc")

# 앱 실행
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("APP_HOST")
    port = int(os.getenv("APP_PORT"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    uvicorn.run(app, host=host, port=port)
