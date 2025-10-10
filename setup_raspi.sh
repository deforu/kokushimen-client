#!/bin/bash

# =============================================================================
# Raspberry Pi 5用 kokushimen-client セットアップスクリプト
# =============================================================================

set -e  # エラー時に停止

echo "🍓 Raspberry Pi 5用 kokushimen-client セットアップを開始します..."

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

# 現在のディレクトリを確認
if [[ ! -f "client/run.py" ]]; then
    print_error "kokushimen-clientのルートディレクトリで実行してください"
    exit 1
fi

# 1. システム依存パッケージのインストール
print_info "システム依存パッケージをインストールしています..."
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev build-essential \
    libportaudio2 portaudio19-dev \
    libasound2-dev alsa-utils

# 2. audioグループへの追加
print_info "ユーザーをaudioグループに追加しています..."
sudo usermod -a -G audio $USER

# 3. Python仮想環境の作成
print_info "Python仮想環境を作成しています..."
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
    print_success "仮想環境を作成しました"
else
    print_info "仮想環境は既に存在します"
fi

# 4. 仮想環境をアクティベート
source .venv/bin/activate

# 5. Pythonパッケージのインストール
print_info "必要なPythonパッケージをインストールしています..."
pip install --upgrade pip

# 基本パッケージ
pip install websockets fastapi uvicorn

# インストールオプションの確認
echo ""
echo "📦 追加パッケージのインストールオプション:"
echo "1) 最小構成（疎通確認のみ）"
echo "2) sounddevice追加（高機能音声入出力）"
echo "3) pyalsaaudio追加（軽量音声入力）"
echo "4) 全部インストール（推奨）"
read -p "選択してください [1-4]: " package_option

case $package_option in
    1)
        print_info "最小構成でセットアップします"
        ;;
    2)
        print_info "sounddeviceをインストールしています..."
        pip install numpy sounddevice
        ;;
    3)
        print_info "pyalsaaudioをインストールしています..."
        pip install pyalsaaudio
        ;;
    4)
        print_info "全パッケージをインストールしています..."
        pip install numpy sounddevice pyalsaaudio
        ;;
    *)
        print_warning "無効な選択です。最小構成でセットアップします"
        ;;
esac

# 6. 設定ファイルの作成
print_info "設定ファイルを作成しています..."
cat > .env << 'EOF'
# サーバー接続設定
SERVER_IP=127.0.0.1
SERVER_PORT=8000
SERVER_AUTH_TOKEN=dev-token

# 音声入力設定
INPUT_BACKEND=tone
# INPUT_BACKEND=sounddevice  # 実マイクを使う場合
# INPUT_BACKEND=alsa         # 軽量入力を使う場合

# 音声出力設定
USE_SD=0
# USE_SD=1  # 音声出力を有効にする場合

# デバイス設定（必要に応じて調整）
# SD_INPUT_DEVICE_SELF=1
# SD_OUTPUT_DEVICE=1
# SD_LIST_DEVICES=1  # デバイス一覧を表示

# VAD設定
VAD_THRESHOLD=0.02
VAD_MIN_SIL_MS=400
# VAD_DEBUG=1  # デバッグ出力を有効にする場合
EOF

print_success "設定ファイル '.env' を作成しました"

print_success "🎉 セットアップが完了しました！"
echo ""
echo "📝 次のステップ:"
echo "1. 設定を確認・編集: nano .env"
echo "2. モックサーバー起動: ./start_mock_server.sh"
echo "3. クライアント実行: ./run_client.sh"
echo ""
print_warning "注意: audioグループの設定を反映するため、一度ログアウト・ログインまたは再起動してください"
echo "sudo reboot"
