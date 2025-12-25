"""
AI护理导师模块 - 用于与GPT API交互
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict


class AIMentor:
    """AI护理导师 - 处理与GPT API的交互"""
    
    # 系统提示词 - 定义AI的角色和行为
    SYSTEM_PROMPT = """You are an expert nursing mentor specializing in epidural catheter removal procedures. 
Your role is to provide educational guidance, answer questions, and help healthcare professionals understand best practices.

Key responsibilities:
1. Explain epidural catheter removal procedures in detail
2. Answer questions about safety precautions and complications
3. Provide evidence-based recommendations
4. Guide on proper hand hygiene and aseptic techniques
5. Explain pain management and patient comfort considerations
6. Discuss emergency procedures and troubleshooting
7. Provide information about equipment and monitoring

Always:
- Be professional and educational
- Provide accurate medical information
- Ask clarifying questions when needed
- Suggest when to consult with senior staff
- Maintain patient safety as the top priority
- Use clear, understandable language

    Please answer in English. Always respond in English unless explicitly requested otherwise.
If asked "Who are you?" reply exactly: "I am an AI nursing mentor."""
    
    def __init__(self, api_url: str, api_key: Optional[str], model: str = "qwen-plus", base_url: Optional[str] = None):
        """
        初始化 AI 导师（使用 OpenAI-compatible 客户端，例如 Dashscope / Alibaba compatible-mode）

        Args:
            api_url: （保留，兼容旧配置）API URL placeholder
            api_key: 可选，若为空将尝试从环境变量 DASHSCOPE_API_KEY 读取
            model: 模型名称（例如 qwen-plus）
            base_url: OpenAI-compatible provider base URL（例如 Dashscope）
        """
        self.api_url = api_url
        self.base_url = base_url or os.getenv("DASHSCOPE_BASE_URL")
        # 支持从环境变量读取 API Key
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model
        self.conversation_history: List[Dict] = []
    
    def chat(self, user_message: str, temperature: float = 0.7) -> Optional[str]:
        """
        发送消息到AI并获取回复
        
        Args:
            user_message: 用户输入的消息
            temperature: 温度参数（0-1），控制回复的随机性
                        0.0 = 确定性，1.0 = 更有创意
        
        Returns:
            AI的回复文本，如果出错返回None
        """
        # 添加用户消息到历史
        self.conversation_history.append({"role": "user", "content": user_message})


        # 简化为 OpenAI-compatible 客户端的标准调用流程
        try:
            from openai import OpenAI
        except Exception as e:
            print(f"[AIMentor] OpenAI SDK not installed: {e}")
            return "Error: OpenAI SDK not installed. Please pip install openai or provider SDK."

        key = self.api_key or os.getenv("DASHSCOPE_API_KEY")
        if not key:
            print("[AIMentor] API key not provided or DASHSCOPE_API_KEY not set")
            return "Error: API key not configured. Set DASHSCOPE_API_KEY environment variable or provide key in config."

        client = OpenAI(api_key=key, base_url=self.base_url)

        completion = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": self.SYSTEM_PROMPT}] + self.conversation_history,
            temperature=temperature,
        )

        # 返回完整 JSON（如果需要）或只取 content
        try:
            # 最简单直接的方法：库对象访问
            content = completion.choices[0].message.content
        except Exception:
            # 回退到 model_dump_json
            if hasattr(completion, "model_dump_json"):
                data = json.loads(completion.model_dump_json())
                content = data["choices"][0]["message"]["content"]
            else:
                # 无法解析
                print("[AIMentor] Unable to parse completion response")
                return "Error: Unable to parse completion response"

        # 保存助手回复到历史并裁剪
        self.conversation_history.append({"role": "assistant", "content": content})
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]

        return content

    def load_context_files(self, paths: list):
        """
        Load plain-text or json files and append their contents as system-context

        Args:
            paths: list of file paths to read and add to conversation history
        """
        for p in paths:
            try:
                if not p or not os.path.exists(p):
                    continue
                with open(p, 'r', encoding='utf-8') as f:
                    data = f.read()

                # For JSON, keep as compact text
                if p.lower().endswith('.json'):
                    role = 'system'
                    content = f"[Reference JSON from {os.path.basename(p)}]\n" + data
                else:
                    role = 'system'
                    content = f"[Reference document {os.path.basename(p)}]\n" + data

                # Append as a system-level context message so model can use it
                self.conversation_history.append({"role": role, "content": content})
            except Exception as e:
                print(f"[AIMentor] Error loading context file {p}: {e}")
    
    def reset_conversation(self):
        """重置对话历史"""
        self.conversation_history = []
        print("[AIMentor] Conversation history cleared")
    
    def get_conversation_history(self) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_history
    
    def save_conversation(self, filepath: str):
        """
        保存对话历史到文件
        
        Args:
            filepath: 保存路径
        """
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "conversation": self.conversation_history
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[AIMentor] Conversation saved to {filepath}")
        except Exception as e:
            print(f"[AIMentor] Error saving conversation: {e}")
