# -*- coding: utf-8 -*-
import os
import subprocess

# プロジェクトルートを取得
project_root = os.path.dirname(os.path.abspath(__file__))
azure_func_path = os.path.join(project_root, "platforms", "azure")

print(f"Starting Azure Functions from: {azure_func_path}")
os.chdir(azure_func_path)
subprocess.run(["func", "start", "--python"])
