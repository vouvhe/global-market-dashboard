"""
Vercel 서버리스 핸들러.
Mangum이 FastAPI(ASGI) 앱을 AWS Lambda / Vercel 서버리스 환경으로 변환합니다.
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가 (main, data_fetcher 등 임포트용)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum
from main import app

handler = Mangum(app, lifespan="off")
