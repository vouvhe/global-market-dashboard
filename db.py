import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_client() -> Client | None:
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")

    if not url or not key or "<" in url or "<" in key:
        return None  # Supabase 미설정 → 캐시 없이 진행

    _client = create_client(url, key)
    return _client
