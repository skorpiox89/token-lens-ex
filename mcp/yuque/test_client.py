"""
协议级自测：模拟 MCP 客户端，通过 stdio 与 server.py 对话。

验证内容：
    1. initialize 握手（MCP 协议第一步）
    2. tools/list 能列出 6 个工具
    3. tools/call 实际调用 get_user：
       - token 模式（假 token）→ 预期语雀返回 401
       - cookie 模式（假 cookie）→ 预期语雀返回 401/403
       两种都报错 = 链路是通的（JSON-RPC → server → 语雀），只是凭证无效。

用法：python test_client.py
"""

import json
import os
import subprocess
import sys

SERVER = os.path.join(os.path.dirname(__file__), "server.py")
PYTHON = sys.executable


def run_session(extra_env: dict, label: str) -> str:
    """开一个 server 进程，跑完整握手流程，调用 get_user，返回其返回文本"""
    proc = subprocess.Popen(
        [PYTHON, SERVER],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8",
        env=dict(os.environ, **extra_env),
    )
    _id = 0

    def send(msg: dict) -> dict:
        nonlocal _id
        _id += 1
        msg["id"] = _id
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    # 握手 + 列工具
    resp = send({"jsonrpc": "2.0", "method": "initialize",
                 "params": {"protocolVersion": "2025-03-26",
                            "capabilities": {},
                            "clientInfo": {"name": "test-client", "version": "1.0"}}})
    assert "result" in resp, f"[{label}] initialize 失败: {resp}"
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized",
                                 "params": {}}) + "\n")
    proc.stdin.flush()
    resp = send({"jsonrpc": "2.0", "method": "tools/list", "params": {}})
    tools = resp["result"]["tools"]
    assert len(tools) == 6, f"[{label}] 工具数量不对: {[t['name'] for t in tools]}"

    # 调用 get_user，观察返回
    resp = send({"jsonrpc": "2.0", "method": "tools/call",
                 "params": {"name": "get_user", "arguments": {}}})
    assert "result" in resp, f"[{label}] tools/call 失败: {resp}"
    text = resp["result"]["content"][0]["text"]

    proc.stdin.close()
    proc.wait(timeout=10)
    return text


# 1. token 模式（假 token）：预期 401
print("== 测试 1：token 模式（假 token）==")
text = run_session({"YUQUE_TOKEN": "dummy_token_for_test"}, "token")
print("get_user 返回:", text[:200])
assert "401" in text or "错误" in text, "token 模式链路异常"
print("[OK] token 模式链路通（凭证无效被语雀拒绝，符合预期）\n")

# 2. cookie 模式（假 cookie）：预期 401/403
print("== 测试 2：cookie 模式（假 cookie）==")
text = run_session({"YUQUE_COOKIE": "_yuque_session=fake_session; yuque_ctoken=fake_ctoken"},
                   "cookie")
print("get_user 返回:", text[:200])
assert "401" in text or "403" in text or "错误" in text, "cookie 模式链路异常"
print("[OK] cookie 模式链路通（凭证无效被语雀拒绝，符合预期）\n")

# 3. 什么都不设：预期提示缺少凭证
print("== 测试 3：未设置任何凭证 ==")
env = dict(os.environ)
env.pop("YUQUE_TOKEN", None)
env.pop("YUQUE_PERSONAL_TOKEN", None)
env.pop("YUQUE_COOKIE", None)
text = run_session(env, "no-auth")
print("get_user 返回:", text[:150])
assert "未检测到语雀凭证" in text, "缺少凭证时应有明确提示"
print("[OK] 缺少凭证时提示清晰\n")

print("✅ 全部测试通过：MCP 协议 + 双认证模式链路正常")
