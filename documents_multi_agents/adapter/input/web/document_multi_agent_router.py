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

from documents_multi_agents.adapter.input.web.request.insert_income_request import InsertDocumentRequest

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
async def analyze_document(
    response: Response,
    file: UploadFile, 
    type_of_doc: str = Form(...), 
    session_id: str = Depends(get_current_user)
):
    try:
        # 쿠키에 session_id 명시적으로 설정
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=24 * 60 * 60,
            httponly=True,
            samesite="lax"
        )
        
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
        
        # 추출된 항목들을 저장하고 동시에 수집
        extracted_items = {}
        try:
            for match in pattern.finditer(answer):
                field, value = match.groups()
                field_clean = field.strip()
                value_clean = value.replace(",", "").strip()
                
                # 암호화된 키/값 생성
                encrypted_key = crypto.enc_data(f"{type_of_doc}:{field_clean}")
                encrypted_value = crypto.enc_data(value_clean)
                
                print(f"[DEBUG] Saving to Redis - session_id: {session_id}")
                print(f"[DEBUG] Original key: {type_of_doc}:{field_clean}")
                print(f"[DEBUG] Original value: {value_clean}")
                
                # Redis에 저장
                redis_client.hset(
                    session_id,
                    encrypted_key,
                    encrypted_value
                )
                
                # 저장 확인
                saved_value = redis_client.hget(session_id, encrypted_key)
                print(f"[DEBUG] Saved successfully: {saved_value is not None}")
                
                # 응답용 데이터 수집
                extracted_items[field_clean] = value_clean
                
        except Exception as e:
            print("[ERROR] Failed to save to Redis:", str(e))
            import traceback
            traceback.print_exc()
            
        redis_client.expire(session_id, 24 * 60 * 60)

        # AI로 카테고리 분류
        from documents_multi_agents.domain.service.financial_analyzer_service import FinancialAnalyzerService
        
        analyzer = FinancialAnalyzerService()
        
        # type_of_doc에 따라 소득/지출 분류
        categorized_data = {}
        if "소득" in type_of_doc or "income" in type_of_doc.lower():
            categorized_data = analyzer._categorize_income(extracted_items)
        elif "지출" in type_of_doc or "expense" in type_of_doc.lower():
            categorized_data = analyzer._categorize_expense(extracted_items)
        else:
            # 타입을 모를 경우 원본 데이터만 반환
            categorized_data = {"raw_items": extracted_items}
        
        # 성공 응답 반환 (session_id 포함)
        return {
            "success": True,
            "message": "분석 완료",
            "session_id": session_id,  # 프론트엔드에서 사용할 수 있도록 명시적으로 반환
            "document_type": type_of_doc,
            "extracted_count": len(extracted_items),
            "categorized_data": categorized_data
        }

    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


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
@documents_multi_agents_router.get("/deduction-expectation")
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
                                       "주어진 문서 본문을 활용하여 연말정산에서 받을 수 있는 총 공제 예상 금액을 산출해줘. "
                                       "이 때 내가 받을 수 있는 총 공제 예상 금액을 먼저 산출해서 보여주고, "
                                       "앞으로 받을 수 있는 추가적인 공제내역이 있다면 해당 항목에 대한 간결한 설명과 함께 알려줘."
                                       "참고할 사이트는 https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6596&cntntsId=7875 국세청 공식 사이트야"
                                       )

        return answer
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")

# -----------------------
# API 엔드포인트 - 사용자 입력 폼 데이터
# -----------------------
@documents_multi_agents_router.post("/analyze_form")
async def insert_document(
        response: Response,
        request: InsertDocumentRequest,
        session_id: str = Depends(get_current_user)
):
    session_expire_seconds = 24 * 60 * 60

    try:
        # 쿠키에 session_id 명시적으로 설정
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=24 * 60 * 60,
            httponly=True,
            samesite="lax"
        )
        
        # 세션 처리
        if not session_id:
            session_id = str(uuid.uuid4())
            redis_client.hset(session_id, "USER_TOKEN", "GUEST")
            redis_client.expire(session_id, 24 * 60 * 60)

        # 암호화해서 저장 및 데이터 수집
        extracted_items = {}
        for field_key, field_value in request.data.items():
            value_clean = field_value.replace(",", "").strip()
            
            # 암호화된 키/값 생성
            encrypted_key = crypto.enc_data(f"{request.document_type}:{field_key}")
            encrypted_value = crypto.enc_data(value_clean)
            
            print(f"[DEBUG] Saving to Redis (form) - session_id: {session_id}")
            print(f"[DEBUG] Original key: {request.document_type}:{field_key}")
            print(f"[DEBUG] Original value: {value_clean}")
            
            redis_client.hset(
                session_id,
                encrypted_key,
                encrypted_value
            )
            
            # 저장 확인
            saved_value = redis_client.hget(session_id, encrypted_key)
            print(f"[DEBUG] Saved successfully: {saved_value is not None}")
            
            # 응답용 데이터 수집
            extracted_items[field_key] = value_clean

        redis_client.expire(session_id, session_expire_seconds)

        # AI로 카테고리 분류
        from documents_multi_agents.domain.service.financial_analyzer_service import FinancialAnalyzerService
        
        analyzer = FinancialAnalyzerService()
        
        # type에 따라 소득/지출 분류
        categorized_data = {}
        if "소득" in request.document_type or "income" in request.document_type.lower():
            categorized_data = analyzer._categorize_income(extracted_items)
        elif "지출" in request.document_type or "expense" in request.document_type.lower():
            categorized_data = analyzer._categorize_expense(extracted_items)
        else:
            categorized_data = {"raw_items": extracted_items}

        return {
            "success": True,
            "message": "분석 완료",
            "session_id": session_id,
            "document_type": request.document_type,
            "extracted_count": len(extracted_items),
            "categorized_data": categorized_data,
            "expire_in_seconds": session_expire_seconds
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# 디버그: Redis 데이터 확인
# -----------------------
@documents_multi_agents_router.get("/debug/redis-data")
async def debug_redis_data(session_id: str = Depends(get_current_user)):
    """Redis에 저장된 원본 데이터 확인 (디버깅용)"""
    try:
        raw_data = redis_client.hgetall(session_id)
        
        result = {
            "session_id": session_id,
            "total_keys": len(raw_data),
            "keys": []
        }
        
        for key_bytes, value_bytes in raw_data.items():
            try:
                # bytes를 문자열로 변환
                if isinstance(key_bytes, bytes):
                    key_str = key_bytes.decode('utf-8')
                else:
                    key_str = str(key_bytes)
                
                if isinstance(value_bytes, bytes):
                    value_str = value_bytes.decode('utf-8')
                else:
                    value_str = str(value_bytes)
                
                # USER_TOKEN은 암호화되지 않음
                if key_str == "USER_TOKEN":
                    result["keys"].append({
                        "key": key_str,
                        "value": "[REDACTED]",  # 보안을 위해 숨김
                        "encrypted": False
                    })
                else:
                    # 복호화 시도
                    try:
                        decrypted_key = crypto.dec_data(key_str)
                        decrypted_value = crypto.dec_data(value_str)
                        result["keys"].append({
                            "key_encrypted": key_str[:50] + "...",
                            "key_decrypted": decrypted_key,
                            "value_decrypted": decrypted_value,
                            "encrypted": True
                        })
                    except Exception as decrypt_err:
                        result["keys"].append({
                            "key": key_str[:50] + "...",
                            "value": value_str[:50] + "...",
                            "error": f"복호화 실패: {str(decrypt_err)}",
                            "encrypted": False
                        })
            except Exception as e:
                result["keys"].append({
                    "error": f"키 처리 실패: {str(e)}"
                })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# 통합 결과 조회 (소득 + 지출)
# -----------------------
@documents_multi_agents_router.get("/result")
async def get_combined_result(session_id: str = Depends(get_current_user)):
    """
    Redis에 저장된 소득+지출 데이터를 복호화하고 카테고리별로 분류하여 반환
    시각화에 적합한 형태로 데이터 구조화
    """
    try:
        print(f"[DEBUG] /result called with session_id: {session_id}")
        
        # Redis에서 모든 데이터 가져오기
        encrypted_data = redis_client.hgetall(session_id)
        
        print(f"[DEBUG] Total keys in Redis: {len(encrypted_data)}")
        
        if not encrypted_data:
            raise HTTPException(
                status_code=404,
                detail="저장된 재무 데이터가 없습니다"
            )
        
        # 복호화 및 소득/지출 분리
        income_items = {}
        expense_items = {}
        
        for key_bytes, value_bytes in encrypted_data.items():
            try:
                # bytes를 문자열로 변환
                if isinstance(key_bytes, bytes):
                    key_str = key_bytes.decode('utf-8')
                else:
                    key_str = str(key_bytes)
                
                if isinstance(value_bytes, bytes):
                    value_str = value_bytes.decode('utf-8')
                else:
                    value_str = str(value_bytes)
                
                # USER_TOKEN 제외
                if key_str == "USER_TOKEN":
                    print("[DEBUG] Skipping USER_TOKEN")
                    continue
                
                print(f"[DEBUG] Decrypting key: {key_str[:50]}...")
                key_plain = crypto.dec_data(key_str)
                value_plain = crypto.dec_data(value_str)
                
                print(f"[DEBUG] Decrypted: {key_plain} = {value_plain}")
                
                # "타입:필드명" 형태 파싱
                if ":" in key_plain:
                    doc_type, field_name = key_plain.split(":", 1)
                    
                    if "소득" in doc_type or "income" in doc_type.lower():
                        income_items[field_name] = value_plain
                        print(f"[DEBUG] Added to income: {field_name} = {value_plain}")
                    elif "지출" in doc_type or "expense" in doc_type.lower():
                        expense_items[field_name] = value_plain
                        print(f"[DEBUG] Added to expense: {field_name} = {value_plain}")
            except Exception as decrypt_error:
                print(f"[ERROR] Decryption failed for key: {key_str[:50] if 'key_str' in locals() else 'unknown'}")
                print(f"[ERROR] Error: {str(decrypt_error)}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"[DEBUG] Total income items: {len(income_items)}")
        print(f"[DEBUG] Total expense items: {len(expense_items)}")
        
        # AI로 카테고리 분류
        from documents_multi_agents.domain.service.financial_analyzer_service import FinancialAnalyzerService
        
        analyzer = FinancialAnalyzerService()
        
        income_categorized = analyzer._categorize_income(income_items) if income_items else {}
        expense_categorized = analyzer._categorize_expense(expense_items) if expense_items else {}
        
        # 요약 정보 계산 (안전한 타입 변환) - 한글 키 우선, 없으면 영문 키
        try:
            total_income = int(income_categorized.get("총소득") or income_categorized.get("total_income", 0)) if (income_categorized.get("총소득") or income_categorized.get("total_income")) else 0
        except (ValueError, TypeError):
            total_income = 0
            
        try:
            total_expense = int(expense_categorized.get("총지출") or expense_categorized.get("total_expense", 0)) if (expense_categorized.get("총지출") or expense_categorized.get("total_expense")) else 0
        except (ValueError, TypeError):
            total_expense = 0
        
        surplus = total_income - total_expense
        surplus_ratio = (surplus / total_income * 100) if total_income > 0 else 0
        
        # 시각화용 데이터 구조
        return {
            "success": True,
            "summary": {
                "total_income": total_income,
                "total_expense": total_expense,
                "surplus": surplus,
                "surplus_ratio": round(surplus_ratio, 2),
                "status": "흑자" if surplus > 0 else "적자" if surplus < 0 else "수지균형"
            },
            "income": income_categorized,
            "expense": expense_categorized,
            "chart_data": {
                "income_by_category": income_categorized.get("카테고리별 합계") or income_categorized.get("카테고리별합계") or income_categorized.get("total_by_category", {}),
                "expense_by_main_category": expense_categorized.get("카테고리별 합계") or expense_categorized.get("카테고리별합계") or expense_categorized.get("total_by_main_category", {}),
                "expense_detail": expense_categorized
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")
