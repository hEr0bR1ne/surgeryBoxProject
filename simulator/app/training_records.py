"""
Training Records Module
负责保存和管理训练记录
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path


class TrainingRecordManager:
    """训练记录管理器"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
    
    def get_user_training_log_path(self, username):
        """获取用户的训练日志文件路径"""
        user_dir = self.data_dir / username
        user_dir.mkdir(exist_ok=True)
        
        training_logs_dir = user_dir / "training_logs"
        training_logs_dir.mkdir(exist_ok=True)
        
        return training_logs_dir
    
    def save_training_record(self, username, training_data):
        """
        保存训练记录
        
        Args:
            username: 用户名
            training_data: 训练数据字典，应包含以下字段：
                - completed_at: 训练完成时间（ISO格式）
                - elapsed_time: 训练耗时（秒）
                - training_mode: 训练类型（如"remove_needle_no_simulator"）
                - events: 4个事件触发时的详细信息
                - performance_metrics: 性能指标
                - quiz_results: Quiz答题结果
        
        Returns:
            保存的文件路径
        """
        logs_dir = self.get_user_training_log_path(username)
        
        # 生成唯一的文件名：timestamp_type.json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        training_type = training_data.get("training_mode", "unknown").replace("_", "")
        filename = f"{timestamp}_{training_type}.json"
        
        filepath = logs_dir / filename
        
        # 确保数据完整性
        record = {
            "username": username,
            "completed_at": datetime.now().isoformat(),
            "training_data": training_data
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        
        print(f"[TrainingRecordManager] Training record saved: {filepath}")
        return filepath
    
    def get_user_training_records(self, username, limit=None):
        """
        获取用户的所有训练记录（按时间倒序）
        
        Args:
            username: 用户名
            limit: 限制返回的记录数（None表示返回全部）
        
        Returns:
            训练记录列表，每个记录包含文件名和数据
        """
        logs_dir = self.get_user_training_log_path(username)
        
        records = []
        if logs_dir.exists():
            for file_path in sorted(logs_dir.glob("*.json"), reverse=True):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["file_path"] = str(file_path)
                        records.append(data)
                except Exception as e:
                    print(f"[TrainingRecordManager] Error reading {file_path}: {e}")
                    continue
        
        if limit:
            return records[:limit]
        return records
    
    def get_training_statistics(self, username):
        """
        获取用户的训练统计信息
        
        Args:
            username: 用户名
        
        Returns:
            统计信息字典：
                - total_trainings: 总训练次数
                - total_time: 总训练时间（秒）
                - avg_time: 平均训练时间（秒）
                - last_training: 最后一次训练信息
                - best_time: 最快完成时间（秒）
        """
        records = self.get_user_training_records(username)
        
        if not records:
            return {
                "total_trainings": 0,
                "total_time": 0,
                "avg_time": 0,
                "last_training": None,
                "best_time": None,
                "details": []
            }
        
        # 计算统计数据
        total_trainings = len(records)
        times = []
        
        for record in records:
            elapsed_time = record.get("training_data", {}).get("elapsed_time", 0)
            if elapsed_time:
                times.append(elapsed_time)
        
        total_time = sum(times)
        avg_time = total_time / total_trainings if total_trainings > 0 else 0
        best_time = min(times) if times else None
        
        return {
            "total_trainings": total_trainings,
            "total_time": total_time,
            "avg_time": avg_time,
            "last_training": records[0] if records else None,
            "best_time": best_time,
            "details": records
        }
    
    def get_all_users_statistics(self):
        """
        获取所有用户的统计信息
        
        Returns:
            用户统计字典 {username: statistics}
        """
        all_stats = {}
        
        if self.data_dir.exists():
            for user_dir in self.data_dir.iterdir():
                if user_dir.is_dir() and (user_dir / "profile.json").exists():
                    username = user_dir.name
                    all_stats[username] = self.get_training_statistics(username)
        
        return all_stats
    
    def delete_training_record(self, username, filename):
        """
        删除特定的训练记录
        
        Args:
            username: 用户名
            filename: 记录文件名
        
        Returns:
            True if successful, False otherwise
        """
        logs_dir = self.get_user_training_log_path(username)
        filepath = logs_dir / filename
        
        if filepath.exists():
            filepath.unlink()
            print(f"[TrainingRecordManager] Training record deleted: {filepath}")
            return True
        return False


# 全局实例
_record_manager = None

def get_training_record_manager(data_dir="data"):
    """获取全局训练记录管理器实例"""
    global _record_manager
    if _record_manager is None:
        _record_manager = TrainingRecordManager(data_dir)
    return _record_manager
