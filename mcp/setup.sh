#!/usr/bin/env sh
# 为某个本地 MCP 服务准备 Python 环境（venv 放在数据目录，不随包更新被清），
# 并生成机器本地启动器 run.sh（供 opencode 等按固定命令路径调用的客户端使用）。
#
#   ./setup.sh <name>        # name = mcp/ 下的目录名，如 yuque / weibo / qzone / processon
#
# 环境位置：$XDG_DATA_HOME/token-lens-ex/mcp/<name>/venv（默认 ~/.local/share/...）
# 启动器：  同目录 run.sh（内含本机 venv 与仓库绝对路径；路径变化时重跑本脚本刷新）
set -eu

NAME="${1:-}"
if [ -z "${NAME}" ]; then
  echo "用法: $0 <name>（mcp/ 下的目录名，如 yuque / weibo / qzone / processon）" >&2
  exit 1
fi

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REQ="${HERE}/${NAME}/requirements.txt"
if [ ! -f "${REQ}" ]; then
  echo "找不到 ${REQ}" >&2
  exit 1
fi

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/token-lens-ex/mcp/${NAME}"
VENV_DIR="${DATA_DIR}/venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3，请先安装 Python 3" >&2
  exit 1
fi

mkdir -p "${DATA_DIR}"
if [ ! -x "${VENV_DIR}/bin/python" ] && [ ! -x "${VENV_DIR}/Scripts/python.exe" ]; then
  python3 -m venv "${VENV_DIR}"
fi

if [ -x "${VENV_DIR}/bin/python" ]; then
  PY="${VENV_DIR}/bin/python"
else
  PY="${VENV_DIR}/Scripts/python.exe"
fi

"${PY}" -m pip install --upgrade pip >/dev/null
"${PY}" -m pip install -r "${REQ}"

# 机器本地启动器：opencode 的 opencode.json 不能写本机绝对路径，统一调用
# {env:HOME}/.local/share/token-lens-ex/mcp/<name>/run.sh（venv 优先，uv 回退）。
RUN="${DATA_DIR}/run.sh"
cat > "${RUN}" <<EOF
#!/usr/bin/env sh
# 由 token-lens-ex mcp/setup.sh 生成，请勿手改；仓库/环境路径变化时重跑：
#   sh <repo>/mcp/setup.sh ${NAME}
set -eu
DATA_DIR="\${XDG_DATA_HOME:-\$HOME/.local/share}/token-lens-ex/mcp/${NAME}"
if [ -x "\${DATA_DIR}/venv/bin/python" ]; then
  exec "\${DATA_DIR}/venv/bin/python" "${HERE}/${NAME}/server.py" "\$@"
fi
if command -v uv >/dev/null 2>&1; then
  exec uv run --quiet --with 'mcp>=1.2.0,<2' "${HERE}/${NAME}/server.py" "\$@"
fi
echo "缺少 Python venv 或 uv，请运行 mcp/setup.sh ${NAME}" >&2
exit 1
EOF
chmod +x "${RUN}"

echo "环境就绪：${PY}"
echo "数据目录：${DATA_DIR}（cookie/token 等放这里）"
echo "启动器：${RUN}"
