"""공공기관 채용정보 API 호출과 코드표.

명세는 API_SPEC.md 참고.
"""
import requests

API_URL = "https://apis.data.go.kr/1051000/recruitment/list"
PAGE_SIZE = 100

# 코드 정의서 v1.2 기준
REGIONS = {
    "R3010": "서울", "R3011": "인천", "R3012": "대전", "R3013": "대구", "R3014": "부산",
    "R3015": "광주", "R3016": "울산", "R3017": "경기", "R3018": "강원", "R3019": "충남",
    "R3020": "충북", "R3021": "경북", "R3022": "경남", "R3023": "전남", "R3024": "전북",
    "R3025": "제주", "R3026": "세종", "R3030": "해외",
}
HIRE_TYPES = {
    "R1010": "정규직", "R1020": "계약직", "R1030": "무기계약직", "R1040": "비정규직",
    "R1050": "청년인턴", "R1060": "청년인턴(체험형)", "R1070": "청년인턴(채용형)",
}
RECRUIT_KINDS = {"R2010": "신입", "R2020": "경력", "R2030": "신입+경력", "R2040": "외국인 전형"}
EDUCATIONS = {
    "R7010": "학력무관", "R7020": "중졸이하", "R7030": "고졸", "R7040": "대졸(2~3년)",
    "R7050": "대졸(4년)", "R7060": "석사", "R7070": "박사",
}
NCS = {
    "R600001": "사업관리", "R600002": "경영·회계·사무", "R600003": "금융·보험",
    "R600004": "교육·자연·사회과학", "R600005": "법률·경찰·소방·교도·국방", "R600006": "보건·의료",
    "R600007": "사회복지·종교", "R600008": "문화·예술·디자인·방송", "R600009": "운전·운송",
    "R600010": "영업판매", "R600011": "경비·청소", "R600012": "이용·숙박·여행·오락·스포츠",
    "R600013": "음식서비스", "R600014": "건설", "R600015": "기계", "R600016": "재료",
    "R600017": "화학", "R600018": "섬유·의복", "R600019": "전기·전자", "R600020": "정보통신",
    "R600021": "식품가공", "R600022": "인쇄·목재·가구·공예", "R600023": "환경·에너지·안전",
    "R600024": "농림어업", "R600025": "연구",
}


def fetch_ongoing(api_key: str, filters: dict) -> list[dict]:
    """조건에 맞는 진행 중 공고를 전부 가져온다 (페이지를 끝까지 돈다).

    filters 는 API 파라미터 이름 그대로: workRgnLst, hireTypeLst, recrutSe,
    ncsCdLst, acbgCondLst, recrutPbancTtl. 빈 값은 보내지 않는다.
    """
    params = {
        "serviceKey": api_key,
        "resultType": "json",
        "ongoingYn": "Y",
        "numOfRows": PAGE_SIZE,
        "pageNo": 1,
        **{k: v for k, v in filters.items() if v},
    }
    items: list[dict] = []
    while True:
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("resultCode") != 200:
            raise RuntimeError(f"API 오류: {data.get('resultMsg') or data}")
        page = data.get("result") or []
        items.extend(page)
        if not page or len(items) >= data.get("totalCount", 0):
            return items
        params["pageNo"] += 1
