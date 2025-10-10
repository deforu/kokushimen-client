#!/bin/bash

# =============================================================================
# モックサーバー起動スクリプト
# =============================================================================

set -e

echo "🖥️  モックサーバーを起動しています..."

# 現在のディレクトリを確認
if [[ ! -f "mock_server/app.py" ]]; then
    echo "❌ エラー: kokushimen-clientのルートディレクトリで実行してください"
    exit 1
fi

# 仮想環境をアクティベート
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
    echo "✅ 仮想環境をアクティベートしました"
else
    echo "⚠️  警告: 仮想環境が見つかりません。先にsetup_raspi.shを実行してください"
    exit 1
fi

# 必要なパッケージがインストールされているか確認
python -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "❌ エラー: 必要なパッケージがインストールされていません"
    echo "先にsetup_raspi.shを実行してください"
    exit 1
}

# ポート使用状況を確認
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  警告: ポート8000は既に使用中です"
    echo "既存のプロセスを停止するか、別のポートを使用してください"
fi

echo "🚀 モックサーバーを起動します..."
echo "📡 アクセスURL: http://$(hostname -I | awk '{print $1}'):8000"
echo "🔌 WebSocket URL: ws://$(hostname -I | awk '{print $1}'):8000/ws"
echo ""
echo "停止するには Ctrl+C を押してください"
echo ""

# モックサーバー起動
uvicorn mock_server.app:app --reload --host 0.0.0.0 --port 8000
