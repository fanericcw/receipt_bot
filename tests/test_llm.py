import pytest
import os
from google import genai
from llm_service import read_receipt, query_llm

MODEL = "gemini-2.5-flash"

@pytest.fixture
def client():
    """Set up new Gemini client with fresh context before each test"""
    return genai.Client(api_key=os.environ.get("GENAI_API_KEY"))

