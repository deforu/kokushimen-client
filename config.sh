#!/bin/bash

# =============================================================================
# 設定編集スクリプト
# =============================================================================

echo "⚙️  設定ファイルを編集します..."

if [[ ! -f ".env" ]]; then
    echo "❌ エラー: 設定ファイル '.env' が見つかりません"
    echo "先にsetup_raspi.shを実行してください"
    exit 1
fi

echo "📝 現在の設定:"
cat .env

echo ""
echo "🔧 設定編集オプション:"
echo "1) nanoエディタで編集"
echo "2) サーバーIP変更"
echo "3) 音声入力方式変更"
echo "4) 音声出力ON/OFF"
echo "5) デバッグ設定"
echo "6) 設定をリセット"
read -p "選択してください [1-6]: " option

case $option in
    1)
        nano .env
        ;;
    2)
        read -p "サーバーIPアドレスを入力してください: " server_ip
        sed -i "s/SERVER_IP=.*/SERVER_IP=$server_ip/" .env
        echo "✅ サーバーIPを $server_ip に変更しました"
        ;;
    3)
        echo "入力方式を選択してください:"
        echo "1) tone (テスト用トーン)"
        echo "2) sounddevice (高機能)"
        echo "3) alsa (軽量)"
        read -p "選択 [1-3]: " input_choice
        case $input_choice in
            1) backend="tone" ;;
            2) backend="sounddevice" ;;
            3) backend="alsa" ;;
            *) echo "無効な選択"; exit 1 ;;
        esac
        sed -i "s/INPUT_BACKEND=.*/INPUT_BACKEND=$backend/" .env
        echo "✅ 入力方式を $backend に変更しました"
        ;;
    4)
        read -p "音声出力を有効にしますか？ [y/N]: " output_choice
        if [[ $output_choice =~ ^[Yy]$ ]]; then
            sed -i "s/USE_SD=.*/USE_SD=1/" .env
            echo "✅ 音声出力を有効にしました"
        else
            sed -i "s/USE_SD=.*/USE_SD=0/" .env
            echo "✅ 音声出力を無効にしました"
        fi
        ;;
    5)
        read -p "デバッグ出力を有効にしますか？ [y/N]: " debug_choice
        if [[ $debug_choice =~ ^[Yy]$ ]]; then
            echo "VAD_DEBUG=1" >> .env
            echo "✅ デバッグ出力を有効にしました"
        else
            sed -i "/VAD_DEBUG=/d" .env
            echo "✅ デバッグ出力を無効にしました"
        fi
        ;;
    6)
        cp .env .env.backup
        cat > .env << 'EOF'
# サーバー接続設定
SERVER_IP=127.0.0.1
SERVER_PORT=8000
SERVER_AUTH_TOKEN=dev-token

# 音声入力設定
INPUT_BACKEND=tone

# 音声出力設定
USE_SD=0

# VAD設定
VAD_THRESHOLD=0.02
VAD_MIN_SIL_MS=400
EOF
        echo "✅ 設定をリセットしました（バックアップ: .env.backup）"
        ;;
    *)
        echo "無効な選択です"
        exit 1
        ;;
esac

echo ""
echo "📝 更新後の設定:"
cat .env
