# Local AI config - create this file from ai_config_example.py and fill your real API key
# This file is ignored by .gitignore to avoid committing secrets.

# API配置
# Prefer using environment variable DASHSCOPE_API_KEY for security.
# If you prefer to store a key here (not recommended), set API_KEY to the string.
import os
API_URL = ""
#API_KEY = os.getenv("DASHSCOPE_API_KEY")  # set via env var or replace with "sk-..." (not recommended)
API_KEY = "sk-99b958b0a12442fab5cf06ee6b7e6d76"
# 可选配置
TEMPERATURE = 0.7
MAX_TOKENS = 2000
TIMEOUT = 30

# OpenAI-compatible client options
MODEL = "qwen-plus"
# Recommended BASE_URL for Dashscope (Alibaba compatible mode)
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Usage notes:
# 1. Replace API_KEY with the real key string.
# 2. If you're using an OpenAI-compatible SDK, set BASE_URL and MODEL as needed.
# 3. Restart the application after editing this file.
