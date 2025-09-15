#!/bin/bash

# =============================================================================
# クライアント実行スクリプト
# =============================================================================

set -e

# 色付きメッセージ用の関数
print_info() {
    echo -e "\033[36m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

echo "🎤 kokushimen-client を起動しています..."

# 現在のディレクトリを確認
if [[ ! -f "client/run.py" ]]; then
    print_error "kokushimen-clientのルートディレクトリで実行してください"
    exit 1
fi

# 仮想環境をアクティベート
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
    print_success "仮想環境をアクティベートしました"
else
    print_error "仮想環境が見つかりません。先にsetup_raspi.shを実行してください"
    exit 1
fi

# 設定ファイルの読み込み
if [[ -f ".env" ]]; then
    print_info "設定ファイル '.env' を読み込んでいます..."
    set -o allexport
    source .env
    set +o allexport
else
    print_warning "設定ファイル '.env' が見つかりません。デフォルト設定を使用します"
    export SERVER_IP=127.0.0.1
    export SERVER_PORT=8000
    export SERVER_AUTH_TOKEN=dev-token
    export INPUT_BACKEND=tone
    export USE_SD=0
fi

# 実行モード選択
echo ""
echo "🔧 実行モードを選択してください:"
echo "1) 疎通確認モード（音なし、トーン送信）"
echo "2) デバイス確認モード（利用可能な音声デバイス一覧表示）"
echo "3) 軽量モード（ALSA入力 + sounddevice出力）"
echo "4) 高機能モード（sounddevice入出力）"
echo "5) カスタムモード（.envファイルの設定を使用）"
echo "6) デバッグモード（VADデバッグ出力有効）"
read -p "選択してください [1-6]: " mode

case $mode in
    1)
        print_info "疎通確認モードで起動します"
        export INPUT_BACKEND=tone
        export USE_SD=0
        ;;
    2)
        print_info "デバイス確認モードで起動します"
        export SD_LIST_DEVICES=1
        export USE_SD=1
        export INPUT_BACKEND=sounddevice
        ;;
    3)
        print_info "軽量モードで起動します"
        export INPUT_BACKEND=alsa
        export USE_SD=1
        # ALSAが利用可能か確認
        python -c "import alsaaudio" 2>/dev/null || {
            print_error "pyalsaaudioがインストールされていません"
            print_info "pip install pyalsaaudio を実行してください"
            exit 1
        }
        ;;
    4)
        print_info "高機能モードで起動します"
        export INPUT_BACKEND=sounddevice
        export USE_SD=1
        # sounddeviceが利用可能か確認
        python -c "import sounddevice, numpy" 2>/dev/null || {
            print_error "sounddeviceまたはnumpyがインストールされていません"
            print_info "pip install numpy sounddevice を実行してください"
            exit 1
        }
        ;;
    5)
        print_info "カスタムモード（.env設定）で起動します"
        ;;
    6)
        print_info "デバッグモードで起動します"
        export VAD_DEBUG=1
        export VAD_DEBUG_EVERY=10
        ;;
    *)
        print_warning "無効な選択です。疎通確認モードで起動します"
        export INPUT_BACKEND=tone
        export USE_SD=0
        ;;
esac

# 現在の設定を表示
echo ""
print_info "現在の設定:"
echo "  サーバー: ${SERVER_IP}:${SERVER_PORT}"
echo "  認証トークン: ${SERVER_AUTH_TOKEN}"
echo "  入力バックエンド: ${INPUT_BACKEND}"
echo "  音声出力: $([ "$USE_SD" = "1" ] && echo "有効" || echo "無効")"
echo ""

# サーバー接続確認
print_info "サーバー接続を確認しています..."
if timeout 3 bash -c "</dev/tcp/${SERVER_IP}/${SERVER_PORT}" 2>/dev/null; then
    print_success "サーバー ${SERVER_IP}:${SERVER_PORT} に接続できます"
else
    print_warning "サーバー ${SERVER_IP}:${SERVER_PORT} に接続できません"
    print_info "モックサーバーを起動する場合: ./start_mock_server.sh"
fi

echo ""
print_info "クライアントを起動します..."
print_info "停止するには Ctrl+C を押してください"
echo ""

# クライアント実行
python -m client.run
