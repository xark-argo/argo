#!/usr/bin/env python3
"""
演示 Argo 自动数据库创建功能

此脚本演示了当配置的 MySQL 数据库不存在时，系统如何自动创建它。
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def demo_auto_database_creation():
    """演示自动数据库创建功能"""
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("Argo 自动数据库创建功能演示")
    print("=" * 60)
    
    # 测试 MySQL 自动创建
    print("\n1. 测试 MySQL 数据库自动创建:")
    print("-" * 40)
    
    # 设置测试环境变量
    test_db_name = "argo_demo_test"
    os.environ.update({
        'DB_TYPE': 'mysql',
        'DB_HOST': 'localhost',
        'DB_PORT': '3306',
        'DB_NAME': test_db_name,
        'DB_USER': 'argo',
        'DB_PASSWORD': 'argo'
    })
    
    try:
        from database.db import ensure_database_exists
        
        print(f"正在检查数据库 '{test_db_name}' 是否存在...")
        ensure_database_exists()
        print("✅ MySQL 数据库检查/创建完成!")
        
    except Exception as e:
        print(f"❌ MySQL 测试失败: {e}")
        print("💡 提示: 请确保 MySQL 服务器正在运行，并且用户 'argo' 有创建数据库的权限")
    
    # 测试 SQLite 处理
    print("\n2. 测试 SQLite 数据库处理:")
    print("-" * 40)
    
    os.environ.update({
        'DB_TYPE': 'sqlite'
    })
    
    try:
        # 重新加载模块以获取新的环境变量
        import importlib
        import configs.settings
        import database.db
        importlib.reload(configs.settings)
        importlib.reload(database.db)
        
        from database.db import ensure_database_exists
        
        print("正在检查 SQLite 数据库处理...")
        ensure_database_exists()
        print("✅ SQLite 数据库处理完成!")
        
    except Exception as e:
        print(f"❌ SQLite 测试失败: {e}")
    
    print("\n3. 功能说明:")
    print("-" * 40)
    print("• 当 DB_TYPE=mysql 时，系统会检查数据库是否存在")
    print("• 如果数据库不存在，会自动创建（使用 utf8mb4 字符集）")
    print("• 当 DB_TYPE=sqlite 时，系统会跳过检查（SQLite 文件会自动创建）")
    print("• 此功能在服务启动时和数据库迁移前自动执行")
    print("• 现在使用 DB_SETTINGS 直接获取配置参数，更加清晰和一致")
    
    print("\n4. 配置示例:")
    print("-" * 40)
    print("在 backend/.env 文件中配置:")
    print("DB_TYPE=mysql")
    print("DB_HOST=localhost")
    print("DB_PORT=3306") 
    print("DB_NAME=argo")
    print("DB_USER=argo")
    print("DB_PASSWORD=argo")
    
    print("\n=" * 60)
    print("演示完成!")
    print("=" * 60)

if __name__ == "__main__":
    demo_auto_database_creation()