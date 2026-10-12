# pi-token-lens-ttft

pi 扩展：把每次 assistant 请求的 **TTFT（首 token 延迟）** 写进 pi 的会话 JSONL，
供 TokenLens 的 `lens-agent` 采集器读取并填入使用记录的 `first_token_ms`。

pi 本身不持久化 TTFT（只在流式过程中存在），`pi-token-speed` 这类展示插件也只
保存在内存里。本扩展用 `pi.appendEntry()` 追加一个自定义 session entry，采集器
tail 的正是同一个文件，因此不需要额外的 sidecar 文件或进程通信。

## 安装

```bash
# 从 git 包安装（固定 tag，推荐）
pi install git:github.com/skorpiox89/token-lens-ex@v0.2.0

# 本地开发
pi install /path/to/token-lens-ex
```

Windows 机器用 `make collector-bundle` 的发布包时无需手动安装：`install-windows.ps1`
会自动把发布包自带的 `pi-token-lens-ttft` 拷到 `%APPDATA%\lens-agent\` 并 `pi install`
（检测到 `pi` 命令时）。

安装后无需配置。TTFT 只在**新产生**的请求上记录，历史会话不会补写。

## 写入格式

每次 assistant 请求完成后，会话 JSONL 里会多一行（追加在 assistant entry 之后，
`parentId` 指向它）：

```json
{
  "type": "custom",
  "id": "h8i9j0k1",
  "parentId": "<assistant entry id>",
  "timestamp": "2026-10-06T13:00:56.000Z",
  "customType": "token-lens.ttft",
  "data": {
    "assistant_ts": 1791291656933,
    "message_entry_id": "d09ee87f",
    "response_id": "chatcmpl-...",
    "ttft_ms": 742,
    "model": "deepseek-v4.1-flash",
    "provider": "opencode-go"
  }
}
```

- `message_entry_id`：assistant session entry 的 id（`turn_end` 事件提供），采集器
  优先用它对齐；`assistant_ts`（assistant 消息的嵌套 `message.timestamp`，unix 毫秒，
  = 请求开始时间）作为兼容兜底。
- `ttft_ms`：从 `assistant_ts` 到第一个流式事件（`text_start` / `thinking_start` /
  `toolcall_start`）的毫秒数。只覆盖请求本身的等待时间，不含 pi 侧的排队。
- 写入时机是 `turn_end`（assistant entry 已落盘），因此不会插在 user 和 assistant
  之间；自定义 entry 不参与模型上下文，也不影响分支树。

## 与 lens-agent 的配合

`collector/pi.go` 在同一次文件读取中解析 `customType == "token-lens.ttft"` 的行，
按 `message_entry_id`（无则 `assistant_ts`）挂到对应记录上；无论 custom entry 写在
assistant 行之前还是之后都能匹配。若采集器恰好在两行写入之间读取（极小概率），
该条记录会缺少 TTFT，下轮不会补推（服务端按 `remote_usage_id` 去重，重复推送也
不会覆盖缺失值）。

其他来源（opencode / commandcode / cline）的本地数据里没有首 token 事件，
`first_token_ms` 保持为空。
