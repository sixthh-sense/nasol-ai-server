"""
재무 분석 AI 프롬프트 템플릿
Domain Service 계층에서 관리하는 비즈니스 로직
"""


class PromptTemplates:
    """재무 분석 관련 AI 프롬프트 템플릿 관리"""

    @staticmethod
    def get_future_assets_prompt() -> tuple[str, str]:
        """
        미래 자산 시뮬레이션 프롬프트
        Returns:
            tuple[str, str]: (question, role)
        """
        question = (
            "현재 내 소득/지출 자료야. 이 자료를 토대로 앞으로의 내 미래 자산에 대한 재무 컨설팅을 듣고 싶어. "
            "어떤 방식으로 자산을 분배하면 좋을지, 세액을 줄이는 방법은 있을지. "
            "현재의 소득수준이 10%증가했을 때, 20% 증가했을 때를 대비한 미래 예측 시뮬레이션도 있으면 좋겠어. "
            "참고 자료는 한국의 비슷한 소득 수준을 가진 사람들에 대한 재무 데이터를 통해서 진행해줘"
        )

        role = (
            "주어진 문서 본문(사용자가 업로드한 소득/지출 자료)을 분석하여 "
            "미래 자산 관리 전략을 제시하라. "
            "현재 소득 수준, 소득 10% 증가 시, 소득 20% 증가 시 각각의 자산 분배 전략을 제시하라. "
            "추가적인 질문을 요구하는 문장은 제외하라. "
            "\n\n"
            "=== HTML 포맷팅 규칙 (엄격히 준수) === \n"
            "\n"
            "반드시 HTML 태그만 사용하여 출력하라. 마크다운 사용 금지. \n"
            "\n"
            "1. 서문: \n"
            "   <p style='font-size: 1.1em;'>사용자 데이터 기반 분석 서문 2-3줄</p> \n"
            "\n"
            "2. 구분선: \n"
            "   <hr style='border: 1px solid #ccc; margin: 20px 0;'> \n"
            "\n"
            "3. 대제목: \n"
            "   <h2 style='font-size: 1.5em; font-weight: bold; margin-top: 20px;'>1. 제목</h2> \n"
            "\n"
            "4. 리스트 계층 구조 (매우 중요): \n"
            "<span>☑️</span><span style='margin-left: 0; padding-left: 20px; margin-bottom: 10px;'><strong>상위 항목</strong></span>\n"
            "       <div style='margin-left: 20px; padding-left: 20px;'> \n"
            "         <span>↳ </span><span>하위 항목 1</span> \n"
            "         <span>↳ </span><span>하위 항목 2</span>> \n"
            "         <span>↳ </span><span>하위 항목 3</span> \n"
            "       </div> \n"
            "\n"
            "5. 결론: \n"
            "   <hr style='border: 1px solid #ccc; margin: 20px 0;'> \n"
            "   <h2 style='font-size: 1.5em; font-weight: bold;'>결론</h2> \n"
            "   <p style='font-size: 1.1em;'>결론 내용 2-3줄</p> \n"
            "\n"
            "6. 참고사항: \n"
            "   <p style='color: #666; font-size: 0.95em;'>※ 자세한 내용은 금융감독원 등에서 확인하실 수 있습니다.</p> \n"
            "\n"
            "=== 절대 금지 사항 === \n"
            "1. 마크다운 문법(##, *, ---, ** 등) 사용 금지 \n"
            "2. 상위 항목과 하위 항목을 같은 <ul> 안에 병렬로 나열하는 것 절대 금지 \n"
            "3. 하위 항목은 반드시 상위 <li> 태그 안에 중첩된 <ul>로 작성 \n"
            "4. 사용자가 업로드한 소득/지출 데이터를 기반으로 분석할 것 \n"
        )

        return question, role

    @staticmethod
    def get_tax_credit_prompt() -> tuple[str, str]:
        """
        세액 공제 가능 항목 확인 프롬프트
        Returns:
            tuple[str, str]: (question, role)
        """
        question = (
            "주어진 문서 본문을 바탕으로 내가 올린 자료 중 한국의 연말정산 소득공제 항목 중 "
            "받을 수 있는 혜택이 남아있다면 그 공제 가능 금액이 큰 순서대로 나열해줘. "
            "이 때 해당 세액공제 방법에 대한 간략한 설명을 100자 이내로 첨부해줘. "
            "소득공제 가능 항목은 연말정산 홈텍스 시스템의 자료를 참조해. "
            "\n"
            "가능한 세액공제 항목은 다음과 같아: "
            "1. 자녀 세액공제, "
            "2. 연금계좌 세액공제, "
            "3. 월세 세액공제, "
            "4. 보험료 세액공제, "
            "5. 의료비 세액공제, "
            "6. 교육비 세액공제, "
            "7. 기부금 세액공제, "
            "8. 혼인 세액공제, "
            "9. 중소기업 취업자 소득세 감면, "
            "10. 근로소득세액공제 "
            "\n"
            "주어진 문서 본문에서 위 10가지 항목에 해당하는 것이 없다면 "
            "그 항목과 항목에 대한 설명, 해당 항목에서 최대로 받을 수 있는 세액공제 가능 금액을 표시해 "
            "(예: 연금계좌 세액공제 = 6,000,000원) "
            "\n"
            "주어진 문서 본문에서 위 10가지 항목 중 해당하는 것이 있으며 "
            "그 공제액이 전체 가능 세액공제 가능 금액과 같다면 제외해. "
            "\n"
            "주어진 문서 본문에서 위 10가지 항목 중 해당하지만 최대 세액공제 가능 금액 미만이라면 "
            "잔여 세액공제 가능 금액을 표기해 "
            "(예: 본문 자료의 연금계좌 세액공제 = 1,000,000원일 경우 잔여 5,000,000원) "
            "\n"
            "주어진 문서 본문의 항목과 내가 제시한 10가지 항목이 일치하지 않아도 "
            "유사도로 0.9 이상이라면 표기해 (예: 혼인 세액공제 = 결혼세액공제) "
            "\n"
            "참고할 사이트는 https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6596&cntntsId=7875 국세청 공식 사이트야"
        )

        role = (
            "주어진 문서 본문의 자료를 토대로 질문에 답변하라. "
            "추가적인 질문을 요구하는 문장은 제외하라. "
            "\n\n"
            "=== HTML 포맷팅 규칙 (엄격히 준수) === \n"
            "\n"
            "반드시 HTML 태그만 사용하여 출력하라. 마크다운 절대 사용 금지. \n"
            "\n"
            "1. 서문: <p style='font-size: 1.1em;'>서문 2-3줄</p> \n"
            "\n"
            "2. 구분선: <hr style='border: 1px solid #ccc; margin: 20px 0;'> \n"
            "\n"
            "3. 대제목: <h2 style='font-size: 1.5em; font-weight: bold;'>1. 항목명: 금액</h2> \n"
            "\n"
            "4. 설명: <p>설명 내용</p> \n"
            "\n"
            "5. 리스트: \n"
            "   <ul style='margin-left: 20px; padding-left: 20px;'> \n"
            "     <li>항목 1</li> \n"
            "     <li>항목 2</li> \n"
            "   </ul> \n"
            "\n"
            "6. 결론: \n"
            "   <hr style='border: 1px solid #ccc; margin: 20px 0;'> \n"
            "   <h2 style='font-size: 1.5em; font-weight: bold;'>요약</h2> \n"
            "   <p style='font-size: 1.1em;'>요약 내용</p> \n"
            "\n"
            "7. 참고: <p style='color: #666; font-size: 0.95em;'>※ 자세한 내용은 국세청 홈택스에서 확인하실 수 있습니다.</p> \n"
            "\n"
            "=== 절대 금지 === \n"
            "1. 마크다운(##, *, --- 등) 절대 사용 금지 \n"
            "2. HTML 태그 없이 일반 텍스트로 출력 금지 \n"
        )

        return question, role

    @staticmethod
    def get_deduction_expectation_prompt() -> tuple[str, str]:
        """
        연말정산 공제 예상 금액 산출 프롬프트
        Returns:
            tuple[str, str]: (question, role)
        """
        question = (
            "주어진 문서 본문을 활용하여 연말정산에서 받을 수 있는 총 공제 예상 금액을 산출해줘. "
            "이 때 내가 받을 수 있는 총 공제 예상 금액을 먼저 산출해서 보여주고, "
            "앞으로 받을 수 있는 추가적인 공제내역이 있다면 해당 항목에 대한 간결한 설명과 함께 알려줘. "
            "참고할 사이트는 https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6596&cntntsId=7875 국세청 공식 사이트야"
        )

        role = (
            "주어진 문서 본문의 자료를 토대로 질문에 답변하라. "
            "추가적인 질문을 요구하는 문장은 제외하라. "
            "\n\n"
            "=== HTML 포맷팅 규칙 (엄격히 준수) === \n"
            "\n"
            "반드시 HTML 태그만 사용하여 출력하라. 마크다운 절대 사용 금지. \n"
            "\n"
            "1. 서문: <p style='font-size: 1.1em;'>서문</p> \n"
            "\n"
            "2. 구분선: <hr style='border: 1px solid #ccc; margin: 20px 0;'> \n"
            "\n"
            "3. 대제목: <h2 style='font-size: 1.5em; font-weight: bold;'>1. 항목명: 금액</h2> \n"
            "\n"
            "4. 리스트: \n"
            "<span>☑️</span><span style='font-size: 1.2em; margin-left: 0; padding-left: 20px; margin-bottom: 10px;'><strong>항목명</strong></span> \n"
            "<h5 style='margin-left: 20px; padding-left: 20px;'> \n"
            "<p>설명</p> \n"
            "<span>↳ </span><span>계산식</span> \n"
            "</h5> \n"
            "\n"
            "5. 총 공제 금액: \n"
            "   <hr style='border: 1px solid #ccc; margin: 20px 0;'> \n"
            "   <div style='text-align: right; font-size: 1.3em;'><strong>총 공제 예상 금액: {금액}원</strong></div> \n"
            "\n"
            "6. 추가 공제: \n"
            "   <hr style='border: 1px solid #ccc; margin: 20px 0;'> \n"
            "<span>✅ </span><span style='font-size: 1.5em; font-weight: bold;'>추가 공제 가능 항목</span> \n"
            "\n"
            "7. 참고: <p style='color: #666; font-size: 0.95em;'>※ 자세한 내용은 국세청 홈택스에서 확인하실 수 있습니다.</p> \n"
            "\n"
            "=== 절대 금지 === \n"
            "1. 마크다운(##, *, --- 등) 절대 사용 금지 \n"
            "2. 상위/하위 항목 병렬 나열 금지 \n"
        )

        return question, role
