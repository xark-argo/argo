#!/usr/bin/env python3
"""
验证 DB_SETTINGS.get() 方法的使用

此脚本验证 ensure_database_exists 函数正确使用了 DB_SETTINGS.get() 方法获取配置参数。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_db_settings_get_usage():
    """测试 DB_SETTINGS.get() 方法的使用"""
    
    print("=" * 60)
    print("验证 DB_SETTINGS.get() 方法的使用")
    print("=" * 60)
    
    # 测试 1: 正常配置情况
    print("\n1. 测试正常配置情况:")
    print("-" * 40)
    
    os.environ.update({
        'DB_TYPE': 'mysql',
        'DB_HOST': 'test_host',
        'DB_PORT': '3307',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass'
    })
    
    # 重新加载模块以获取新的环境变量
    import importlib
    import configs.settings
    importlib.reload(configs.settings)
    
    from configs.settings import DB_SETTINGS
    
    print(f"DB_HOST: {DB_SETTINGS.get('db_host', 'localhost')}")
    print(f"DB_PORT: {DB_SETTINGS.get('db_port', 3306)}")
    print(f"DB_NAME: {DB_SETTINGS.get('db_name', 'argo')}")
    print(f"DB_USER: {DB_SETTINGS.get('db_user', 'argo')}")
    print(f"DB_PASSWORD: {DB_SETTINGS.get('db_password', '')}")
    
    # 测试 2: 缺少配置时使用默认值
    print("\n2. 测试缺少配置时的默认值:")
    print("-" * 40)
    
    # 模拟 DB_SETTINGS 中缺少某些键的情况
    partial_settings = {'db_type': 'mysql'}
    
    print(f"db_host (默认): {partial_settings.get('db_host', 'localhost')}")
    print(f"db_port (默认): {partial_settings.get('db_port', 3306)}")
    print(f"db_name (默认): {partial_settings.get('db_name', 'argo')}")
    print(f"db_user (默认): {partial_settings.get('db_user', 'argo')}")
    print(f"db_password (默认): {partial_settings.get('db_password', '')}")
    
    # 测试 3: 验证函数中的 .get() 使用
    print("\n3. 验证 ensure_database_exists 函数使用 .get() 方法:")
    print("-" * 40)
    
    # 检查函数源码中是否使用了 .get() 方法
    import inspect
    from database.db import ensure_database_exists
    
    source = inspect.getsource(ensure_database_exists)
    get_usages = source.count('.get(')
    
    print(f"函数中使用 .get() 方法的次数: {get_usages}")
    
    if get_usages >= 5:  # db_type, db_host, db_port, db_user, db_password, db_name
        print("✅ 函数正确使用了 .get() 方法获取配置参数")
    else:
        print("❌ 函数可能没有正确使用 .get() 方法")
    
    # 显示使用 .get() 的代码行
    lines = source.split('\n')
    get_lines = [line.strip() for line in lines if '.get(' in line]
    
    if get_lines:
        print("\n使用 .get() 方法的代码行:")
        for i, line in enumerate(get_lines, 1):
            print(f"  {i}. {line}")
    
    print("\n4. 优势说明:")
    print("-" * 40)
    print("• 使用 .get() 方法提供默认值，避免 KeyError")
    print("• 提高代码的健壮性和容错性")
    print("• 配置缺失时仍能使用合理的默认值")
    print("• 遵循 Python 最佳实践")
    
    print("\n=" * 60)
    print("验证完成!")
    print("=" * 60)

if __name__ == "__main__":
    test_db_settings_get_usage()