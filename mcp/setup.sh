#!/usr/bin/env sh
# 为某个本地 MCP 服务准备 Python 环境（venv 放在数据目录，不随包更新被清）。
#
#   ./setup.sh <name>        # name = mcp/ 下的目录名，如 yuque / weibo / qzone / processon
#
# 环境位置：$XDG_DATA_HOME/token-lens-ex/mcp/<name>/venv（默认 ~/.local/share/...）
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

echo "环境就绪：${PY}"
echo "数据目录：${DATA_DIR}（cookie/token 等放这里）"
