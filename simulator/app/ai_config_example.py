# AI导师 API 配置
# 
# 使用说明：
# 1. 复制这个文件为 ai_config_local.py（.gitignore已配置，不会上传）
# 2. 从这里获取你的API Key：https://gpt-api.hkust-gz.edu.cn/
# 3. 修改下面的 YOUR_API_KEY 为你的实际密钥
# 4. 修改 API_URL 如果需要使用不同的端点

# API配置
# Leave API_URL empty when using OpenAI-compatible providers via BASE_URL
API_URL = ""
API_KEY = "sk-99b958b0a12442fab5cf06ee6b7e6d76"  # 替换为你的实际API密钥 or leave empty to use DASHSCOPE_API_KEY env var

# 可选配置
TEMPERATURE = 0.7  # 回复的创意程度（0-1）
MAX_TOKENS = 2000   # 最大回复长度
TIMEOUT = 30        # 请求超时时间（秒）

# OpenAI-compatible client options (optional)
# If you use an OpenAI-compatible SDK (e.g. Alibaba/qwen or official OpenAI),
# you can set MODEL and BASE_URL here. Leave BASE_URL empty to use API_URL.
MODEL = "qwen-plus"
# Recommended BASE_URL for Dashscope (Alibaba compatible mode)
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # change if using a different provider
