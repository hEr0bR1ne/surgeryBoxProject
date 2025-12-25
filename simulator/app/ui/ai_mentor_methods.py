"""
AI Nursing Mentor集成到main_window的方法
这个文件包含添加到MainWindow中的方法代码
"""

def _init_ai_mentor(self):
    """初始化AI Nursing Mentor"""
    try:
        from app.ai_mentor import AIMentor
        from app.ui.ai_mentor_widget import AIMentorWidget
        
        # 尝试导入配置
        try:
            from app.ai_config_local import API_URL, API_KEY
        except ImportError:
            # 使用示例配置
            from app.ai_config_example import API_URL, API_KEY
            print("[MainWindow] Warning: Using example config. Please create ai_config_local.py with your API key")
            return None
        
        # 验证API配置
        if API_KEY == "your-api-key-here" or not API_KEY:
            print("[MainWindow] Error: API key not configured. Please set it in app/ai_config_local.py")
            return None
        
        # 创建AI导师实例
        self.ai_mentor = AIMentor(API_URL, API_KEY)
        print("[MainWindow] AI Mentor initialized successfully")
        return self.ai_mentor
        
    except ImportError as e:
        print(f"[MainWindow] Error importing AI Mentor: {e}")
        return None
    except Exception as e:
        print(f"[MainWindow] Error initializing AI Mentor: {e}")
        return None


def _show_ai_mentor(self):
    """显示AI Nursing Mentor对话界面"""
    try:
        from app.ui.ai_mentor_widget import AIMentorWidget
        
        # 初始化AI Mentor（如果还没初始化）
        if not hasattr(self, 'ai_mentor') or self.ai_mentor is None:
            self._init_ai_mentor()
        
        # 创建或获取AI Mentor Widget
        if not hasattr(self, 'ai_mentor_widget') or self.ai_mentor_widget is None:
            self.ai_mentor_widget = AIMentorWidget(self.ai_mentor, self.content)
            content_l = self.content.layout()
            content_l.insertWidget(2, self.ai_mentor_widget)
        
        # 隐藏所有其他容器
        self._hide_all_content_containers()
        
        # 显示AI Mentor
        self.ai_mentor_widget.setVisible(True)
        self.content_title.setText("AI Nursing Mentor")
        self.content_title.setVisible(True)
        
    except Exception as e:
        print(f"Error showing AI Mentor: {e}")
        import traceback
        traceback.print_exc()
        
        # 显示错误信息
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            self,
            "Error",
            "Failed to load AI Mentor.\n\n"
            "Please ensure:\n"
            "1. Create app/ai_config_local.py with your API key\n"
            "2. Copy from app/ai_config_example.py\n"
            "3. Fill in your actual API key"
        )
