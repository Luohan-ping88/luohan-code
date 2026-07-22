#!/bin/bash
# PL5 GitHub 一键推送脚本
# 用法: ./push_to_github.sh <YOUR_GITHUB_TOKEN>
# Token生成: https://github.com/settings/tokens/new (勾选repo权限)

TOKEN="${1:-${GH_TOKEN:-${GITHUB_TOKEN}}}"

if [ -z "$TOKEN" ]; then
    echo "错误: 未提供GitHub Token"
    echo "用法: ./push_to_github.sh ghp_your_token_here"
    echo "或在 https://github.com/settings/tokens/new 生成Token后设置环境变量:"
    echo "  export GH_TOKEN=ghp_your_token_here && ./push_to_github.sh"
    exit 1
fi

REPO_DIR="/workspace"
cd "$REPO_DIR" || exit 1

echo "=== 配置Git凭据 ==="
echo "https://Luohan-ping88:${TOKEN}@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials
git config credential.helper store

echo "=== 配置GitHub CLI ==="
echo "$TOKEN" | gh auth login --with-token 2>/dev/null

echo "=== 当前待推送提交 ==="
git log origin/main..HEAD --oneline

echo "=== 推送到GitHub ==="
git push origin main

if [ $? -eq 0 ]; then
    echo "=== 推送成功! ==="
    gh auth status 2>/dev/null
else
    echo "=== 推送失败，请检查Token是否有效 ==="
    exit 1
fi
