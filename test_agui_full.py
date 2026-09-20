
# # # ---

# # # ## 二、测试程序

# # # 保存为 `test_agui_full.py`，与 `dist/agui.exe` 同目录，测试所有核心功能。

# # # ```python
# # # """
# # # agui 全面测试脚本 (HTTP API 模式)
# # # 功能：
  # # # 1. 启动 HTTP 服务（后台无 GUI）
  # # # 2. 添加三个任务（两个正常，一个错误 URL）
  # # # 3. 轮询所有任务状态，自动 kill 已完成的任务
  # # # 4. 错误任务等待其进入错误状态后 kill
  # # # 5. 所有任务处理完毕后，检查进程退出
  # # # 6. 验证文件完整性（无 .aria2 残留）
# # # """
import requests
import subprocess
import time
import os
import sys
import json

HTTP_PORT = 16800
BASE_URL = f"http://127.0.0.1:{HTTP_PORT}/api"

# 测试用 URL（建议使用小文件）
URL_SMALL = "https://httpbin.org/bytes/1024"
URL_MEDIUM = "https://httpbin.org/bytes/2048"
URL_INVALID = "https://invalid.domain.xyz/nonexistent"

def post_api(method, params):
    try:
        resp = requests.post(BASE_URL, json={"method": method, "params": params}, timeout=10)
        return resp.json()
    except Exception as e:
        return {"status": "failed", "message": str(e)}

def test():
    print("=" * 60)
    print("agui HTTP API 测试开始")

    # 1. 启动 agui HTTP 服务（后台）
    print("\n[1] 启动 agui HTTP 服务...")
    proc = subprocess.Popen(
        [os.path.join("dist", "agui.exe"), f"--http-port={HTTP_PORT}"],
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(2)  # 等待服务就绪

    # 2. 添加三个任务
    print("\n[2] 添加任务...")
    # 任务1：小文件
    res1 = post_api("add", ["--title", "SmallFile", URL_SMALL])
    print(f"  任务1: {res1}")
    gid1 = res1.get("GID") if res1.get("status") == "success" else None

    # 任务2：中等文件
    res2 = post_api("add", ["--title", "MediumFile", URL_MEDIUM])
    print(f"  任务2: {res2}")
    gid2 = res2.get("GID") if res2.get("status") == "success" else None

    # 任务3：无效URL（测试错误处理）
    res3 = post_api("add", ["--title", "InvalidURL", URL_INVALID])
    print(f"  任务3: {res3}")
    gid3 = res3.get("GID") if res3.get("status") == "success" else None

    if not any([gid1, gid2, gid3]):
        print("所有任务添加失败，退出。")
        proc.terminate()
        return

    # 3. 轮询并处理任务
    print("\n[3] 开始轮询任务状态...")
    active_gids = set()
    if gid1: active_gids.add(gid1)
    if gid2: active_gids.add(gid2)
    if gid3: active_gids.add(gid3)

    while active_gids:
        time.sleep(1)
        for gid in list(active_gids):
            query = post_api("query", {"gid": gid})
            if query.get("status") != "success":
                print(f"  GID {gid}: 查询失败，移除")
                active_gids.remove(gid)
                continue

            data = query.get("data", {})
            status = data.get("status", "unknown")
            progress = f"{data.get('completedLength', 0)}/{data.get('totalLength', 0)}"
            ready = data.get("downloadReady", False)
            error_msg = data.get("errorMessage", "")

            if ready or status == "complete":
                print(f"  GID {gid}: 完成，正在 kill...")
                kill_res = post_api("kill", {"gid": gid})
                print(f"    kill 结果: {kill_res}")
                active_gids.remove(gid)
            elif status == "error":
                print(f"  GID {gid}: 出错 ({error_msg})，正在 kill...")
                kill_res = post_api("kill", {"gid": gid})
                print(f"    kill 结果: {kill_res}")
                active_gids.remove(gid)
            else:
                print(f"  GID {gid}: {status} {progress}")

    print("\n[4] 所有任务已处理，等待进程退出...")
    time.sleep(2)

    # 检查进程是否退出（所有任务被kill后程序应退出）
    proc.poll()
    if proc.returncode is None:
        print("agui 进程仍在运行（可能有残留），强制终止。")
        proc.terminate()
    else:
        print("agui 进程已正常退出。")

    # 检查下载目录是否有 .aria2 残留（应无）
    aria2_files = [f for f in os.listdir(".") if f.endswith(".aria2")]
    if aria2_files:
        print(f"⚠️ 发现残留 .aria2 文件: {aria2_files}")
    else:
        print("✅ 无 .aria2 残留")

    print("\n测试完成。")

if __name__ == "__main__":
    test()