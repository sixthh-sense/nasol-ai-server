from fastapi import APIRouter, Depends, UploadFile, HTTPException, Form, Response
from openai import OpenAI
from pypdf import PdfReader
import asyncio
import io
import re
import uuid
from typing import List, Dict

from starlette import status

from config.crypto import Crypto
from config.redis_config import get_redis
from account.adapter.input.web.session_helper import get_current_user
from account.adapter.input.web.request.insert_income_request import InsertIncomeRequest

documents_multi_agents_router = APIRouter(tags=["documents_multi_agents_router"])
redis_client = get_redis()
client = OpenAI()
crypto = Crypto.get_instance()

# -----------------------
# PDF 텍스트 추출
# -----------------------
def extract_text_from_pdf_clean(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        texts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            t = re.sub(r'\s+', ' ', t)  # 공백 정리
            t = re.sub(r'\d+\s*$', '', t)  # 페이지 번호 제거 (행 끝 숫자)
            if t.strip():
                texts.append(t.strip())
        return "\n".join(texts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF parsing error: {str(e)}")


# -----------------------
# 텍스트 청킹
# -----------------------
def chunk_text(text: str, chunk_size=3500, overlap=300) -> List[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, cur = [], ""
    for p in paragraphs:
        if len(cur) + len(p) <= chunk_size:
            cur += " " + p
        else:
            chunks.append(cur.strip())
            cur = p
    if cur:
        chunks.append(cur.strip())
    return chunks


# -----------------------
# GPT 호출 래퍼 (기존)
# -----------------------
async def ask_gpt(prompt: str, max_tokens=500):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda:
    client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0
    ).choices[0].message.content
                                      )


# -----------------------
# QA 에이전트 (문서 기반)
# -----------------------
async def qa_on_document(document: str, question: str) -> str:
    prompt = f"""
다음은 문서 자료이다. 이 문서 내의 정보만 사용하여 질문에 답해라.

요약:
{document}

질문:
{question}

규칙:
- 추론하지 말고 문서 내에서만 답을 찾아라.
- 없으면 "문서에 해당 정보 없음"이라고 답해라.
- 문서 내에 있는 모든 정보를 찾아라.
"""
    return (await ask_gpt(prompt, max_tokens=2500)).strip()


# -----------------------
# QA 에이전트 (문서 기반)
# -----------------------
async def assets_on_document(document: str, question: str) -> str:
    prompt = f"""
다음은 문서 본문이다. 이 문서 내의 정보만 사용하여 질문에 답해라.

본문:
{document}

질문:
{question}

규칙:
- 주어진 문서 본문의 자료를 토대로 한국의 비슷한 소득수준의 재무정보를 분석하여 가이드가 될 수 있는 포토폴리오 자료를 제출하라. 
- 웹 검색을 사용하여 현재 소득 수준에 대한 포토폴리오 자료, 소득 수준이 10% 상승되었을 때, 20% 상승되었을 때에 대한 미래 예측 자료를 함께 제출하라.
- 추가적인 질문을 요구하는 문장은 제외하라.
- -- 등으로 불필요한 줄나눔은 없게 하라.
"""
    return (await ask_gpt(prompt, max_tokens=2500)).strip()

# -----------------------
# QA 에이전트 (요약 기반)
# -----------------------
async def tax_on_document(document: str, question: str) -> str:
    prompt = f"""
다음은 문서 본문이다. 이 문서 내의 정보만 사용하여 질문에 답해라.

본문:
{document}

질문:
{question}

규칙:
- 주어진 문서 본문의 자료를 토대로 질문에 답변하라.
- 추가적인 질문을 요구하는 문장은 제외하라.
- -- 등으로 불필요한 줄나눔은 없게 하라.
"""
    return (await ask_gpt(prompt, max_tokens=2500)).strip()
# -----------------------
# API 엔드포인트
# -----------------------
@documents_multi_agents_router.post("/analyze")
async def analyze_document(file: UploadFile, type_of_doc: str = Form(...), session_id: str = Depends(get_current_user)):
    try:
        content = await file.read()
        if not content:
            raise HTTPException(400, "Empty file upload")

        text = extract_text_from_pdf_clean(content)
        if not text:
            raise HTTPException(400, "No text extracted")

        # 2. QA (요약 기반)
        answer = await qa_on_document(text,
                                      "PDF의 항목과 금액을 급여 : 얼마 비과세소득계 : 얼마 비과세식대 : 얼마 형태로 모든 항목들을 key:value 형태로 요약해줘 "
                                      "예시로 든 항목만 하는게 아니라 모든 금액 항목들을 모두 다 찾아야 해."
                                      "이 때 문서 내 모든 금액을 찾아야 하고, 월별 구분이 합계금액과 함께 있을 경우 월별 금액은 무시해. "
                                      "예시 : "
                                      "건강보험료: 12123123"
                                      "직불카드 등: 123123123"
                                      "급여: 123123"
                                      "상여: 123123")

        pattern = re.compile(r'([가-힣\w\s]+)\s*:\s*([\d,]+)')

        try:

            for match in pattern.finditer(answer):
                field, value = match.groups()
                # 쉼표 제거하고 Redis에 저장
                redis_client.hset(
                    session_id,
                    crypto.enc_data(f"{type_of_doc}:{field.strip()}"),
                    crypto.enc_data(value.replace(",", "").strip())
                )
        except Exception as e:
            print("[ERROR] Failed to save to Redis:", str(e))
        redis_client.expire(session_id, 24 * 60 * 60)

    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")

    return Response(status_code=status.HTTP_200_OK)


# -----------------------
# API 엔드포인트
# -----------------------
@documents_multi_agents_router.get("/future-assets")
async def analyze_document(session_id: str = Depends(get_current_user)):
    try:

        content = redis_client.hgetall(session_id)
        pairs = []
        for k_bytes, v_bytes in content.items():
            try:
                if k_bytes == "USER_TOKEN":
                    continue

                key_plain = crypto.dec_data(k_bytes)
                val_plain = crypto.dec_data(v_bytes)

                # key_plain은 "type:field" 형태 — 원하는 대로 처리
                _, field_name = key_plain.split(':', 1)
                pairs.append(f"{field_name}: {val_plain}")

            except ValueError as e:
                # 복호화 실패 시 로깅/무시
                continue

        data_str = ", ".join(pairs)

        answer = await assets_on_document(data_str,
                                      "현재 내 소득/지출 자료야. 이 자료를 토대로 앞으로의 내 미래 자산에 대한 재무 컨설팅을 듣고 싶어. "
                                      "어떤 방식으로 자산을 분배하면 좋을지, 세액을 줄이는 방법은 있을지. 현재의 소득수준이 10%증가했을 때, 20% 증가했을 때를 대비한 미래 예측 시뮬레이션도 있으면 좋겠어. "
                                      "참고 자료는 한국의 비슷한 소득 수준을 가진 사람들에 대한 재무 데이터를 통해서 진행해줘")

        return answer
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")

# -----------------------
# API 엔드포인트
# -----------------------
@documents_multi_agents_router.get("/tax-credit")
async def analyze_document(session_id: str = Depends(get_current_user)):
    try:

        content = redis_client.hgetall(session_id)
        pairs = []
        for k_bytes, v_bytes in content.items():
            try:
                if k_bytes == "USER_TOKEN":
                    continue

                key_plain = crypto.dec_data(k_bytes)
                val_plain = crypto.dec_data(v_bytes)

                # key_plain은 "type:field" 형태 — 원하는 대로 처리
                _, field_name = key_plain.split(':', 1)
                pairs.append(f"{field_name}: {val_plain}")

            except ValueError as e:
                # 복호화 실패 시 로깅/무시
                continue

        data_str = ", ".join(pairs)

        answer = await tax_on_document(data_str,
                                      "주어진 문서 본문을 바탕으로 내가 올린 자료 중 한국의 연말정산 소득공제 항목 중 받을 수 있는 혜택이 남아있다면 그 공제 가능 금액이 큰 순서대로 나열해줘. "
                                      "이 때 해당 세액공제 방법에 대한 간략한 설명을 100자 이내로 첨부해줘. 소득공제 가능 항목은 연말정산 홈텍스 시스템의 자료를 참조해. "
                                      "가능한 세액공제 항목은 다음과 같아. "
                                      "1. 자녀 세액공제"
                                      "2. 연금계좌 세액공제"
                                      "3. 월세 세액공제"
                                      "4. 보험료 세액공제"
                                      "5. 의료비 세액공제"
                                      "6. 교육비 세액공제"
                                      "7. 기부금 세액공제"
                                      "8. 혼인 세액공제"
                                      "9. 중소기업 취업자 소득세 감면"
                                      "10. 근로소득세액공제"
                                      "주어진 문서 본문에서 위 10가지 항목에 해당하는 것이 없다면 그 항목과 항목에 대한 설명, 해당 항목에서 최대로 받을 수 있는 세액공제 가능 금액을 표시해 "
                                      "(EX; 연금자료 세액공제 = 6,000,000)"
                                      "주어진 문서 본문에서 위 10가지 항목 중 해당하는 것이 있으며 그 공제액이 전체 가능 세액공제 가능 금액과 같다면 제외해"
                                      "주어진 문서 본문에서 위 10가지 항목 중 해당하지만 최대 세액공제 가능 금액 미만이라면 잔여 세액공제 가능 금액을 표기해"
                                      "(EX; 본문 자료의 연금자료 세액공제 = 1,000,000 일 경우 5,000,000)"
                                      "주어진 문서 본문의 항목과 내가 제시한 10가지 항목이 일치하지 않아도 유사도로 0.9 이상이라면 표기해 "
                                      "EX) 혼인 세액공제 = 결혼세액공제"
                                      "참고할 사이트는 https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6596&cntntsId=7875 국세청 공식 사이트야"
                                    
                                       )

        return answer
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


# -----------------------
# API 엔드포인트
# -----------------------
@documents_multi_agents_router.post("/income")
async def insert_income(
    request: InsertIncomeRequest,
    session_id: str = Depends(get_current_user)
):
    # 세션 유지 시간 (24시간)
    session_expire_seconds = 24 * 60 * 60  # 86400초
        
    # Redis에 소득 자료를 Hash 형태로 저장
    try:
        # session_id 없으면 (비 로그인 유저) 
        # GUEST로 redis에 session 생성
        if not session_id:
            session_id = str(uuid.uuid4())
            redis_client.hset(
                session_id,
                "USER_TOKEN",
                "GUEST"
            )
            redis_client.expire(session_id, 24 * 60 * 60)
        
        # session_id를 request에 추가
        request.session_id = session_id
        
        """
        Args:
            session_id: 세션 ID (Redis key)
            income_data: 소득 항목 딕셔너리 {"급여": "3000000", "상여": "500000", ...}
        
        Returns:
            저장된 데이터 정보
        """
        redis_key = f"income:{session_id}"
        
        # Redis Hash에 데이터 저장 (hset)
        # income_data의 각 항목을 field-value로 저장
        for field_key, field_value in request.income_data.items():
            redis_client.hset(redis_key, field_key, field_value)
        
        # 유효기간 설정 (24시간)
        redis_client.expire(redis_key, session_expire_seconds)
        
        # 저장된 데이터 확인
        saved_data = redis_client.hgetall(redis_key)
        
        return {
            "session_id": session_id,
            "saved_fields": list(saved_data.keys()),
            "expire_in_seconds": session_expire_seconds
        }
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail=str(e))    