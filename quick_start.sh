#!/bin/bash

# =============================================================================
# ワンライナー実行スクリプト（全部まとめて実行）
# =============================================================================

set -e

echo "🚀 kokushimen-client ワンライナー実行"
echo "セットアップ → モックサーバー起動 → クライアント実行"
echo ""

# セットアップ実行
echo "📦 セットアップを開始..."
chmod +x setup_raspi.sh
./setup_raspi.sh

echo ""
echo "⏱️  3秒後にモックサーバーを起動します..."
sleep 3

# モックサーバーをバックグラウンドで起動
echo "🖥️  モックサーバーをバックグラウンドで起動..."
chmod +x start_mock_server.sh
./start_mock_server.sh &
SERVER_PID=$!

# サーバー起動を待つ
echo "⏱️  サーバー起動を待機中..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:8000/ >/dev/null 2>&1; then
        echo "✅ モックサーバーが起動しました"
        break
    fi
    echo "待機中... ($i/10)"
    sleep 2
done

echo ""
echo "🎤 クライアントを起動します..."
echo "停止するには Ctrl+C を押してください"
echo ""

# クライアント実行
chmod +x run_client.sh
./run_client.sh

# 終了時にサーバーも停止
trap "kill $SERVER_PID 2>/dev/null" EXIT
