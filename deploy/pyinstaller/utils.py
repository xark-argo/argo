import os
import glob
from PyInstaller.utils.hooks import collect_data_files

spec_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(spec_dir, "../.."))
backend_dir = os.path.abspath(os.path.join(project_dir, 'backend'))

def get_data_files():
    datas = []

    # 第三方模块资源
    datas += collect_data_files("swagger_ui")
    datas += collect_data_files("emoji")
    datas += collect_data_files("duckduckgo_search")
    datas += collect_data_files("llama_cpp")

    # 模型供应商文件
    yaml_files = glob.glob(os.path.join(backend_dir, "core/model_providers/*/provider.yaml"))
    for fpath in yaml_files:
        src_path = os.path.relpath(fpath, start=spec_dir)
        dest_path = os.path.relpath(fpath, start=backend_dir)
        datas.append((src_path, os.path.dirname(dest_path)))

    position_path = os.path.join(backend_dir, "core/model_providers/_position.yaml")
    datas.append((
        os.path.relpath(position_path, start=spec_dir),
        "core/model_providers"
    ))

    # 自定义资源目录（前端构建、静态资源等）
    custom_folders = ["dist", "resources", "alembic", "configs", "templates"]
    for folder in custom_folders:
        src = os.path.join(backend_dir, folder)
        datas.append((src, folder))

    return datas