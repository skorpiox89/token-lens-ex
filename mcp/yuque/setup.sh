#!/usr/bin/env sh
# 为 yuque MCP 准备 Python 环境（不放在包目录里，避免 pi 更新包时被清掉）。
#
#   ./setup.sh
#
# 环境位置：$XDG_DATA_HOME/token-lens-ex/mcp/yuque/venv（默认 ~/.local/share/...）
# cookie 放同目录的 cookie.txt（或设 YUQUE_COOKIE 环境变量）。
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/token-lens-ex/mcp/yuque"
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
"${PY}" -m pip install -r "${HERE}/requirements.txt"

echo "环境就绪：${PY}"
echo "cookie：把语雀登录 cookie 写到 ${DATA_DIR}/cookie.txt（或设置 YUQUE_COOKIE）"
