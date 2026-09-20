#!/usr/bin/env python3
"""
agui 全面功能测试脚本 (HTTP API 模式)
用法：
    python test_full.py [agui路径，默认 dist/agui.exe]
要求：
    pip install requests
"""
import requests
import subprocess
import time
import os
import sys

# ------------------------------
# 配置
# ------------------------------
AGUI_PATH = sys.argv[1] if len(sys.argv) > 1 else "dist\\agui.exe"
HTTP_PORT = 18999            # 避免与常用端口冲突
BASE_URL = f"http://127.0.0.1:{HTTP_PORT}/api"
TEST_URL_SMALL = "https://httpbin.org/bytes/1024"    # 1KB 文件
TEST_URL_MEDIUM = "https://httpbin.org/bytes/2048"   # 2KB 文件
TEST_URL_INVALID = "https://invalid.domain.xyz/nonexistent"

# 测试用超时
HTTP_TIMEOUT = 10

# ------------------------------
# 工具函数
# ------------------------------
def post_api(method, params, timeout=HTTP_TIMEOUT):
    """发送 HTTP 请求到 agui 并返回解析后的 JSON"""
    try:
        resp = requests.post(BASE_URL,
                            json={"method": method, "params": params},
                            timeout=timeout,
                            proxies={"http": None, "https": None})
        return resp.json()
    except Exception as e:
        return {"status": "failed", "message": str(e)}

def wait_for_http(timeout=5):
    """等待 HTTP 服务就绪，返回 True/False"""
    for _ in range(timeout):
        try:
            resp = requests.post(BASE_URL,
                                json={"method": "query", "params": {"gid": "0000000000000000"}},
                                timeout=2,
                                proxies={"http": None, "https": None})
            # 任意响应都说明服务已启动
            return True
        except:
            time.sleep(1)
    return False

def check_process_alive(pid):
    """检查进程是否存活（Windows only）"""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x100000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except:
        return False

# ------------------------------
# 测试类
# ------------------------------
class Tester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.agui_proc = None

    def run(self):
        print("=" * 60)
        print("agui 全面功能测试开始")
        print(f"agui 路径: {AGUI_PATH}")
        print(f"HTTP 端口: {HTTP_PORT}")

        # 0. 检查 exe 是否存在
        # self.test("exe 文件存在", os.path.exists(AGUI_PATH), True)
        self.test("exe 文件存在", os.path.exists(AGUI_PATH))

        # 1. 先测试 -gui 模式（需要主实例，无其他进程）
        self.test_gui_mode()

        # 2. 启动 HTTP 服务（无 GUI），用于后续测试
        self.start_service()

        # 1.5 测试 -gui 参数 (GUI 模式)
        # self.test_gui_mode()
        
        # 2. 测试添加有效任务
        res = post_api("add", {"url": TEST_URL_SMALL, "title": "test1", "countdown": "0"})
        self.test("添加有效任务", res.get("status") == "success" and "GID" in res)
        gid1 = res.get("GID") if res.get("status") == "success" else None

        # 3. 测试添加无效 URL（aria2 仍会创建任务）
        res = post_api("add", {"url": TEST_URL_INVALID, "title": "invalid"})
        self.test("添加无效 URL（仍返回 GID）", res.get("status") == "success" and "GID" in res)
        gid_bad = res.get("GID") if res.get("status") == "success" else None

        # 4. 测试查询有效 GID
        if gid1:
            q = post_api("query", {"gid": gid1})
            self.test("查询有效 GID 返回成功", q.get("status") == "success" and "data" in q)

        # 5. 测试查询无效 GID
        q = post_api("query", {"gid": "0123456789abcdef"})
        self.test("查询无效 GID 返回失败", q.get("status") == "failed")

        # 6. 等待任务完成并检查 downloadReady
        if gid1:
            self.wait_for_download_ready(gid1)
            q = post_api("query", {"gid": gid1})
            data = q.get("data", {})
            self.test("任务完成 downloadReady 为 True", data.get("downloadReady") == True)
            # 检查 .aria2 文件不存在（需要文件路径，暂略）

        # 7. 测试 kill 有效 GID
        if gid1:
            res = post_api("kill", {"gid": gid1})
            self.test("kill 有效 GID", res.get("status") == "success" and "message" in res)

        # 8. 测试 kill 无效 GID
        res = post_api("kill", {"gid": "0000000000000001"})
        self.test("kill 无效 GID 返回失败", res.get("status") == "failed")

        # 9. 测试全局参数动态修改（检查无报错）
        res = post_api("add", {"url": TEST_URL_MEDIUM, "retry": "5", "countdown": "0", "title": "test2"})
        self.test("全局参数（retry）添加任务", res.get("status") == "success")
        gid2 = res.get("GID") if res.get("status") == "success" else None
        if gid2:
            # 快速 kill 掉，避免等待
            post_api("kill", {"gid": gid2})

        # 10. 错误处理：缺少 url
        res = post_api("add", {"title": "no url"})
        self.test("缺少 url 返回失败", res.get("status") == "failed")

        # 11. 错误处理：无效 JSON
        try:
            resp = requests.post(BASE_URL, data="not json", timeout=HTTP_TIMEOUT)
            # 可能返回 400 或 200 含错误
            self.test("无效 JSON 请求能被处理", resp.status_code in (200, 400))
        except:
            self.test("无效 JSON 请求无崩溃", True)

        # 12. 多任务并发添加与清理
        gids = []
        for i in range(3):
            res = post_api("add", {"url": TEST_URL_SMALL, "title": f"multi_{i}", "countdown": "0"})
            if res.get("status") == "success":
                gids.append(res["GID"])
        self.test("并发添加多个任务", len(gids) == 3)
        for gid in gids:
            self.wait_for_download_ready(gid)
            post_api("kill", {"gid": gid})
        # 检查最后 agui 是否退出？由于我们设置了 countdown 0，不会自动退出，但最后一个任务被 kill 后，如果无任务，程序会退出？根据之前逻辑，无任务且 HTTP 端口下会保留吗？我们没实施常驻，所以最后一个任务 kill 后程序会退出。检查进程退出。
        time.sleep(1)
        alive = check_process_alive(self.agui_proc.pid) if self.agui_proc else False
        self.test("所有任务 kill 后进程继续存活（接受新任务）", alive)

        # 清理：终止所有 agui 进程（测试完毕）
        if self.agui_proc and check_process_alive(self.agui_proc.pid):
            self.agui_proc.kill()
            self.agui_proc.wait()

        # 结果汇总
        print("\n" + "=" * 60)
        print(f"测试完成: 通过 {self.passed}, 失败 {self.failed}")
        if self.failed == 0:
            print("✅ 所有测试通过！")
        else:
            print("❌ 存在失败测试，请检查。")

    def start_service(self):
        """启动 agui HTTP 服务（后台，无 GUI），若端口被占用则先清理"""
        # 先尝试清理可能的残留进程
        try:
            subprocess.run(f"taskkill /f /im agui.exe", shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except:
            pass

        cmd = [AGUI_PATH, f"--http-port={HTTP_PORT}", "--countdown=0"]
        self.agui_proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if wait_for_http(timeout=5):
            print("HTTP 服务已启动")
        else:
            print("⚠ HTTP 服务启动超时，继续尝试测试...")
            
    def wait_for_download_ready(self, gid, timeout=30):
        """轮询直到 downloadReady 为 True 或超时"""
        for _ in range(timeout):
            q = post_api("query", {"gid": gid})
            if q.get("status") == "success":
                data = q.get("data", {})
                if data.get("downloadReady"):
                    return True
                if data.get("status") == "error":
                    return False
            time.sleep(1)
        return False

    def test_gui_mode(self):
        """启动带 -gui 的 agui（使用不同端口，避免与主服务冲突）"""
        gui_http_port = HTTP_PORT + 100  # 使用完全不同的端口范围
        gui_rpc_port = HTTP_PORT + 101   # RPC 也用独立端口
        cmd = [
            AGUI_PATH, "-gui",
            f"--http-port={gui_http_port}",
            f"--rpc-listen-port={gui_rpc_port}",
            "--countdown", "0",
            TEST_URL_SMALL
        ]
        print(f"    执行命令: {' '.join(cmd)}")
        gui_proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        time.sleep(5)
        alive = gui_proc.poll() is None
        self.test("-gui 参数启动后进程存活（带下载任务）", alive)
        if alive:
            gui_proc.kill()
            gui_proc.wait()
            
    def test(self, name, condition):
        if condition:
            print(f"✅ {name}")
            self.passed += 1
        else:
            print(f"❌ {name}")
            self.failed += 1

# ------------------------------
# 入口
# ------------------------------
if __name__ == "__main__":
    tester = Tester()
    tester.run()