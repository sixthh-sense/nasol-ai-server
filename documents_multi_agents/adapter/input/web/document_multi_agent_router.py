from fastapi import APIRouter, Depends, UploadFile, HTTPException, Form, Response
from openai import OpenAI
from pypdf import PdfReader
import asyncio
import io
import re
import uuid

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
async def qa_on_document(document: str, question: str, role: str) -> str:
    prompt = f"""
다음은 문서 자료이다. 이 문서 내의 정보만 사용하여 질문에 답해라.
답변 시 존댓말 사용을 유지해라.

요약:
{document}

질문:
{question}

규칙:
{role}
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
        
        print(f"[DEBUG] Extracted text length: {len(text)}")
        print(f"[DEBUG] Extracted text preview: {text[:300]}")  # 처음 300자

        # 2. QA (요약 기반)
        # type_of_doc에 따라 프롬프트 분기
        if "소득" in type_of_doc or "income" in type_of_doc.lower():
            extraction_question = (
                "PDF에서 소득 관련 항목과 금액만 추출해줘. "
                "반드시 다음 형식으로만 답변: 항목명: 금액 (한 줄에 하나씩) "
                "설명, 주석, 별표, 마크다운 등 절대 사용 금지 "
                "예시: "
                "급여: 3000000 "
                "식대: 200000 "
                "상여: 500000"
            )
            extraction_role = (
                "소득 항목만 포함: 급여, 상여, 식대, 수당, 총급여, 이자소득, 배당소득 "
                "절대 제외: 보험료, 세금, 공제액 등 차감/지출 항목 "
                "추론 금지, 문서 내 데이터만 사용 "
                "월별 구분 있으면 합계만 사용 "
                "설명문, 주석 절대 금지 - 순수 데이터만 반환"
            )
        elif "지출" in type_of_doc or "expense" in type_of_doc.lower():
            extraction_question = (
                "PDF에서 지출 관련 항목과 금액만 추출해줘. "
                "반드시 다음 형식으로만 답변: 항목명: 금액 (한 줄에 하나씩) "
                "설명, 주석, 별표, 마크다운 등 절대 사용 금지 "
                "예시: "
                "국민연금보험료: 500000 "
                "신용카드: 1000000 "
                "건강보험료: 300000"
            )
            extraction_role = (
                "지출 항목만 포함: 보험료, 카드사용액, 세금, 공과금, 대출, 월세, 통신비 "
                "절대 제외: 급여, 소득, 수당 등 수입 항목 "
                "추론 금지, 문서 내 데이터만 사용 "
                "월별 구분 있으면 합계만 사용 "
                "설명문, 주석 절대 금지 - 순수 데이터만 반환"
            )
        else:
            # 타입을 모를 경우 기본 프롬프트
            extraction_question = (
                "PDF의 항목과 금액을 추출해줘. "
                "형식: 항목명: 금액 (한 줄에 하나씩)"
            )
            extraction_role = (
                "문서 내 모든 금액 찾기 "
                "월별 구분 있으면 합계만 사용 "
                "설명문 금지 - 순수 데이터만"
            )
        
        answer = await qa_on_document(text, extraction_question, extraction_role)
        
        print(f"[DEBUG] AI raw answer: {answer[:500]}")  # 처음 500자만
        
        # AI 응답 전처리: 마크다운, 설명문 제거
        answer = answer.replace("**", "")  # 볼드 제거
        answer = answer.replace("*", "")   # 이탤릭 제거
        answer = re.sub(r'※.*', '', answer)  # 주석 제거
        answer = re.sub(r'---.*', '', answer, flags=re.DOTALL)  # 구분선 이후 제거
        
        print(f"[DEBUG] AI cleaned answer: {answer[:500]}")
        
        pattern = re.compile(r'([가-힣\w\s]+)\s*:\s*([\d,]+)')
        matches = list(pattern.finditer(answer))
        
        print(f"[DEBUG] Pattern matches found: {len(matches)}")
        
        # 추출된 항목들을 저장하고 동시에 수집
        extracted_items = {}
        duplicate_keywords = ["총급여", "총소득", "합계", "총합", "총액"]  # 중복 가능성 있는 키워드
        
        try:
            for match in matches:
                field, value = match.groups()
                field_clean = field.strip()
                value_clean = value.replace(",", "").strip()
                
                # 중복 체크: 같은 금액의 유사 항목이 이미 있으면 스킵
                is_duplicate = False
                for existing_field, existing_value in extracted_items.items():
                    if value_clean == existing_value:  # 금액이 같고
                        # 하나가 다른 하나의 "합계" 버전이면 중복으로 간주
                        if any(keyword in field_clean for keyword in duplicate_keywords) or \
                           any(keyword in existing_field for keyword in duplicate_keywords):
                            is_duplicate = True
                            print(f"[DEBUG] Skipping duplicate: {field_clean} (same as {existing_field}: {value_clean})")
                            break
                
                if is_duplicate:
                    continue
                
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
        
        print(f"[DEBUG] Total extracted_items: {len(extracted_items)}")
        
        if not extracted_items:
            print("[WARNING] No items were extracted from PDF!")
            return {
                "success": False,
                "message": "PDF에서 데이터를 추출하지 못했습니다. PDF 형식을 확인해주세요.",
                "session_id": session_id,
                "document_type": type_of_doc,
                "extracted_count": 0,
                "categorized_data": {}
            }

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

        answer = await qa_on_document(data_str,
                                      "현재 내 소득/지출 자료야. 이 자료를 토대로 앞으로의 내 미래 자산에 대한 재무 컨설팅을 듣고 싶어. "
                                      "어떤 방식으로 자산을 분배하면 좋을지, 세액을 줄이는 방법은 있을지. 현재의 소득수준이 10%증가했을 때, 20% 증가했을 때를 대비한 미래 예측 시뮬레이션도 있으면 좋겠어. "
                                      "참고 자료는 한국의 비슷한 소득 수준을 가진 사람들에 대한 재무 데이터를 통해서 진행해줘",
                                       "주어진 문서 본문의 자료를 토대로 한국의 비슷한 소득수준의 재무정보를 분석하여 가이드가 될 수 있는 포토폴리오 자료를 제출하라."
                                       "웹 검색을 사용하여 현재 소득 수준에 대한 포토폴리오 자료, 소득 수준이 10% 상승되었을 때, 20% 상승되었을 때에 대한 미래 예측 자료를 함께 제출하라."
                                       "추가적인 질문을 요구하는 문장은 제외하라."
                                       "-- 등으로 불필요한 줄나눔은 없게 하라."
                                      )

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

        answer = await qa_on_document(data_str,
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
                                      "참고할 사이트는 https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6596&cntntsId=7875 국세청 공식 사이트야",
                                       "주어진 문서 본문의 자료를 토대로 질문에 답변하라."
                                       "추가적인 질문을 요구하는 문장은 제외하라."
                                       "-- 등으로 불필요한 줄나눔은 없게 하라."
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

        answer = await qa_on_document(data_str,
                                       "주어진 문서 본문을 활용하여 연말정산에서 받을 수 있는 총 공제 예상 금액을 산출해줘. "
                                       "이 때 내가 받을 수 있는 총 공제 예상 금액을 먼저 산출해서 보여주고, "
                                       "앞으로 받을 수 있는 추가적인 공제내역이 있다면 해당 항목에 대한 간결한 설명과 함께 알려줘."
                                       "참고할 사이트는 https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6596&cntntsId=7875 국세청 공식 사이트야",
                                      "주어진 문서 본문의 자료를 토대로 질문에 답변하라."
                                      "추가적인 질문을 요구하는 문장은 제외하라."
                                      "-- 등으로 불필요한 줄나눔은 없게 하라."
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
        
        # 소득 항목 중 지출성 항목을 지출로 재분류
        # 1. 보험료
        insurance_keywords = ["보험료", "보험", "연금"]
        # 2. 세금
        tax_keywords = ["소득세", "지방소득세", "세액"]
        
        items_to_move = []
        
        for field_name, value in list(income_items.items()):
            should_move = False
            
            # 보험료 관련 항목 체크
            if any(keyword in field_name for keyword in insurance_keywords):
                # 공제 금액이 아닌 실제 보험료만 이동
                if "공제" not in field_name and "대상" not in field_name:
                    should_move = True
            
            # 세금 관련 항목 체크
            if any(keyword in field_name for keyword in tax_keywords):
                # 공제 금액이 아닌 실제 세금만 이동
                if "공제" not in field_name and "과세표준" not in field_name and "산출" not in field_name:
                    should_move = True
            
            if should_move:
                items_to_move.append(field_name)
                print(f"[DEBUG] Moving to expense: {field_name} = {value}")
        
        # 실제 이동
        for field_name in items_to_move:
            expense_items[field_name] = income_items.pop(field_name)
        
        print(f"[DEBUG] After reclassification - income: {len(income_items)}, expense: {len(expense_items)}")
        
        # AI로 카테고리 분류
        from documents_multi_agents.domain.service.financial_analyzer_service import FinancialAnalyzerService
        
        analyzer = FinancialAnalyzerService()
        
        print(f"[DEBUG] Before AI categorization - income_items: {income_items}")
        print(f"[DEBUG] Before AI categorization - expense_items: {expense_items}")
        
        income_categorized = analyzer._categorize_income(income_items) if income_items else {}
        expense_categorized = analyzer._categorize_expense(expense_items) if expense_items else {}
        
        print(f"[DEBUG] After AI categorization - income_categorized keys: {income_categorized.keys()}")
        print(f"[DEBUG] After AI categorization - expense_categorized keys: {expense_categorized.keys()}")
        print(f"[DEBUG] income_categorized 총소득: {income_categorized.get('총소득')}")
        print(f"[DEBUG] expense_categorized 총지출: {expense_categorized.get('총지출')}")
        
        # 요약 정보 계산 (안전한 타입 변환) - 한글 키 우선, 없으면 영문 키
        try:
            total_income = int(income_categorized.get("총소득") or income_categorized.get("total_income", 0)) if (income_categorized.get("총소득") or income_categorized.get("total_income")) else 0
            print(f"[DEBUG] Calculated total_income: {total_income}")
        except (ValueError, TypeError) as e:
            print(f"[ERROR] Failed to calculate total_income: {e}")
            total_income = 0
            
        try:
            total_expense = int(expense_categorized.get("총지출") or expense_categorized.get("total_expense", 0)) if (expense_categorized.get("총지출") or expense_categorized.get("total_expense")) else 0
            print(f"[DEBUG] Calculated total_expense: {total_expense}")
        except (ValueError, TypeError) as e:
            print(f"[ERROR] Failed to calculate total_expense: {e}")
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
