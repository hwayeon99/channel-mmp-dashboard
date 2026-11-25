# 채널 × MMP 일별 대시보드

매체(채널) CSV와 MMP(AppsFlyer) CSV를 일 단위로 조인해 KPI, 드릴다운, 정합성(격차) 검증을 보여주는 Streamlit 앱.

## 데이터 취급
- 이 저장소에는 **코드만** 있습니다. CSV(광고주 비용·매출)는 커밋하지 않습니다(`.gitignore`).
- 클라우드에서는 사이드바에서 CSV를 직접 업로드합니다. 파일은 서버 메모리에서만 처리됩니다.
- 파일명 규칙: `YYYY-MM-DD_channel.csv`, `YYYY-MM-DD_appsflyer.csv`

## 로컬 실행
```
pip install -r requirements.txt
streamlit run app.py
```
로컬에서는 `config.py`의 `DATA_DIR`(기본: 이 폴더의 상위 폴더, 또는 환경변수 `DASHBOARD_DATA_DIR`)에 있는 CSV를 자동으로 읽습니다.

## 구성
- `app.py` UI(요약 / 드릴다운 / 정합성·검증)
- `loader.py` 파일 탐색·조인·검증
- `metrics.py` KPI·격차 계산
- `config.py` 경로, 미디어소스 매핑, 격차 임계치
