#!/usr/bin/env bash
# Usage: ./push_to_github.sh <GITHUB_TOKEN>
# 环境变量方式也支持: GITHUB_TOKEN=xxx ./push_to_github.sh
set -e
REPO_URL="https://github.com/Luohan-ping88/luohan-code.git"
TOKEN="${1:-${GITHUB_TOKEN}}"
if [ -z "${TOKEN}" ]; then
  echo "错误: 请提供 GitHub Token."
  echo "用法: $0 <GITHUB_TOKEN>"
  echo "或者: GITHUB_TOKEN=<your_token> $0"
  exit 1
fi
AUTH_URL="https://${TOKEN}@github.com/Luohan-ping88/luohan-code.git"
cd "$(dirname "$0")"
echo ">>> git remote set-url origin ${AUTH_URL/\/\/*@/\/\/***@}"
git remote set-url origin "${AUTH_URL}"
echo ">>> git push origin main"
git push origin main
echo ">>> 推送成功。还原 remote URL"
git remote set-url origin "${REPO_URL}"
