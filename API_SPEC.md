# 재정경제부_공공기관 채용정보 조회서비스 — API 명세 메모

출처: data.go.kr 데이터셋 15125273 페이지의 Swagger 명세, 코드 정의서 v1.2 (MOEF_NKOD_DB_05)

> 활용신청 화면의 `opendata.alio.go.kr/v1/recruit/*.do` 는 원본 시스템 주소라 직접 호출하면 메인 페이지로 리다이렉트된다.
> 실제 호출은 아래 data.go.kr 게이트웨이 주소로 한다.

## 엔드포인트

| 오퍼레이션 | URL |
|---|---|
| 목록 조회 | `https://apis.data.go.kr/1051000/recruitment/list` |
| 상세 조회 | `https://apis.data.go.kr/1051000/recruitment/detail` |

## 목록 조회 `/list` 요청 파라미터

| 이름 | 필수 | 설명 |
|---|---|---|
| serviceKey | ✅ | 공공데이터포털 인증키 (Decoding 키) |
| pageNo | | 페이지번호 (기본 1) |
| numOfRows | | 한 페이지 결과 수 (기본 10) |
| resultType | | 응답형태 (기본 json) |
| ongoingYn | | 진행여부 Y/N |
| pbancBgngYmd | | 공시 시작일 기준 조회시작일 `YYYY-MM-DD` |
| pbancEndYmd | | 공시 시작일 기준 조회종료일 `YYYY-MM-DD` |
| recrutPbancTtl | | 공고제목 (포함 검색) |
| hireTypeLst | | 고용유형 코드 (쉼표 구분) |
| recrutSe | | 채용구분 코드 |
| workRgnLst | | 근무지역 코드 (쉼표 구분) |
| ncsCdLst | | NCS 코드 (쉼표 구분) |
| acbgCondLst | | 학력 코드 (쉼표 구분) |
| replmprYn | | 대체인력여부 Y/N |
| instType / instClsf / pblntInstCd | | 기관유형 / 기관분류 / 기관코드 |

## 상세 조회 `/detail` 요청 파라미터

| 이름 | 필수 | 설명 |
|---|---|---|
| serviceKey | ✅ | 인증키 |
| sn | ✅ | 채용공시 일련번호 (`recrutPblntSn`) |
| resultType | | 응답형태 (기본 json) |

## 목록 응답

최상위: `resultCode`, `resultMsg`, `totalCount`, `result`(공고 배열)

| 필드 | 의미 |
|---|---|
| recrutPblntSn | 채용공시 일련번호 (공고 고유 ID → 중복 판별용) |
| recrutPbancTtl | 채용공고 제목 |
| instNm | 기관명 |
| pbancBgngYmd / pbancEndYmd | 공고 시작일 / 종료일 (`YYYYMMDD`) |
| decimalDay | 마감 D-day |
| ongoingYn | 진행여부 |
| hireTypeNmLst | 고용유형명 |
| recrutSeNm | 채용구분명 |
| workRgnNmLst | 근무지역명 |
| ncsCdNmLst | NCS 직무분야명 |
| acbgCondNmLst | 학력조건명 |
| recrutNope | 채용인원 |
| aplyQlfcCn / prefCn / disqlfcRsn | 신청자격 / 우대내용 / 결격사유 |
| scrnprcdrMthdExpln | 전형절차 설명 |
| srcUrl | 원문 공고 링크 |
| files, steps | 목록에서는 빈 배열 → 상세 조회로 받아야 함 |

## 주요 코드값

**고용형태 (hireTypeLst)**: R1010 정규직, R1020 계약직, R1030 무기계약직, R1040 비정규직, R1050 청년인턴, R1060 청년인턴(체험형), R1070 청년인턴(채용형)

**채용구분 (recrutSe)**: R2010 신입, R2020 경력, R2030 신입+경력, R2040 외국인 전형

**근무지 (workRgnLst)**: R3010 서울, R3011 인천, R3012 대전, R3013 대구, R3014 부산, R3015 광주, R3016 울산, R3017 경기, R3018 강원, R3019 충남, R3020 충북, R3021 경북, R3022 경남, R3023 전남, R3024 전북, R3025 제주, R3026 세종, R3030 해외

**학력 (acbgCondLst)**: R7010 학력무관, R7020 중졸이하, R7030 고졸, R7040 대졸(2~3년), R7050 대졸(4년), R7060 석사, R7070 박사

**NCS (ncsCdLst)**: R600001 사업관리, R600002 경영.회계.사무, R600003 금융.보험, R600004 교육.자연.사회과학, R600005 법률.경찰.소방.교도.국방, R600006 보건.의료, R600007 사회복지.종교, R600008 문화.예술.디자인.방송, R600009 운전.운송, R600010 영업판매, R600011 경비.청소, R600012 이용.숙박.여행.오락.스포츠, R600013 음식서비스, R600014 건설, R600015 기계, R600016 재료, R600017 화학, R600018 섬유.의복, R600019 전기.전자, R600020 정보통신, R600021 식품가공, R600022 인쇄.목재.가구.공예, R600023 환경.에너지.안전, R600024 농림어업, R600025 연구

## 에러 코드

| 코드 | 의미 |
|---|---|
| 30 | 등록되지 않은 서비스키 (키 오타, 승인 직후 반영 대기 1~2시간, 다른 API용 키) |
| 10 / 11 | 잘못된 파라미터 / 필수 파라미터 없음 |
| 3 | 데이터 없음 |
| 7 | 게이트웨이 인증 에러 |
