"""공공기관 채용정보 API 호출 테스트.

.env 의 DATA_GO_KR_API_KEY 로 API를 한 번 호출해서 응답 구조를 확인한다.
실행: python test_api.py
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

# 윈도우 콘솔에서 한글이 깨지지 않도록
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "").strip()
if not API_KEY:
    sys.exit(".env 에 DATA_GO_KR_API_KEY 가 비어 있습니다.")

# data.go.kr Swagger 명세 기준 (opendata.alio.go.kr 주소는 원본 시스템이라 직접 호출 불가)
URL = "https://apis.data.go.kr/1051000/recruitment/list"
params = {
    "serviceKey": API_KEY,  # Decoding 키 (requests가 알아서 인코딩함)
    "pageNo": 1,
    "numOfRows": 3,
    "resultType": "json",
}

resp = requests.get(URL, params=params, timeout=20)

print("상태 코드:", resp.status_code)
print("Content-Type:", resp.headers.get("Content-Type"))
print("-" * 60)

try:
    data = resp.json()
except ValueError:
    # JSON이 아니면 (XML 에러 메시지 등) 원문 앞부분을 그대로 보여준다
    print(resp.text[:1500])
    sys.exit(1)

print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
