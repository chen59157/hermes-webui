#!/usr/bin/env python3
"""HermesWarden 任务脚本最小示例 —— 调API → 写output.jsonl
用户把这个文件复制一份，改成自己的API调用逻辑。"""
import os, json

API_KEY = os.environ.get("YOUR_API_KEY", "demo-key")
API_URL = os.environ.get("YOUR_API_URL", "https://api.example.com/v1/chat")
OUTPUT = os.environ.get("WARDEN_OUTPUT", "output/result.jsonl")

# 示例：产生一条数据
data = {
    "id": int(time.time()),
    "role": "user",
    "content": "这是一个示例产出。请替换为真实的API调用。"
}

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "a") as f:
    f.write(json.dumps(data, ensure_ascii=False) + "\n")

print(f"✅ 产出1条 → {OUTPUT}")
