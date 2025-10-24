#!/bin/bash

# =============================================================================
# Raspberry Pi 5用 LED制御セットアップスクリプト
# =============================================================================

set -e

echo "💡 Raspberry Pi 5用 LED制御セットアップ"
echo "========================================"

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

# 仮想環境の確認
if [[ -z "$VIRTUAL_ENV" ]]; then
    print_warning "仮想環境が有効になっていません"
    if [[ -f ".venv/bin/activate" ]]; then
        print_info "仮想環境をアクティベートします..."
        source .venv/bin/activate
    else
        print_error "仮想環境が見つかりません。先にsetup_raspi.shを実行してください"
        exit 1
    fi
fi

# 1. gpiozeroとlgpioのインストール
print_info "Raspberry Pi 5用のGPIOライブラリをインストールしています..."
pip install gpiozero lgpio

print_success "GPIOライブラリのインストールが完了しました"

# 2. GPIOグループの確認と追加
print_info "GPIOアクセス権限を確認しています..."
if groups $USER | grep -q "gpio"; then
    print_success "ユーザーは既にgpioグループに所属しています"
else
    print_info "ユーザーをgpioグループに追加しています..."
    sudo usermod -a -G gpio $USER
    print_warning "gpioグループへの追加が完了しました"
    print_warning "変更を反映するには、一度ログアウトまたは再起動が必要です"
fi

# 3. 設定ファイルの更新
print_info "LED制御設定を.envに追加しています..."
if [[ -f ".env" ]]; then
    # 既存の設定を削除（あれば）
    sed -i '/# LED制御設定/,/^$/d' .env
    
    # 新しい設定を追加
    cat >> .env << 'EOF'

# LED制御設定（Raspberry Pi 5）
USE_LED=1
LED_PIN_RED=17
LED_PIN_GREEN=27
LED_PIN_BLUE=22
LED_COMMON_ANODE=1
EOF
    print_success "LED制御設定を.envに追加しました"
else
    print_warning ".envファイルが見つかりません"
    print_info "手動で以下の設定を追加してください:"
    echo ""
    echo "USE_LED=1"
    echo "LED_PIN_RED=17"
    echo "LED_PIN_GREEN=27"
    echo "LED_PIN_BLUE=22"
    echo "LED_COMMON_ANODE=1"
fi

# 4. 接続テスト用スクリプトの作成
print_info "LED接続テスト用スクリプトを作成しています..."
cat > test_led.py << 'EOF'
#!/usr/bin/env python3
"""
RGB LED接続テストスクリプト（Raspberry Pi 5用）
"""
import os
import time

# 環境変数を設定
os.environ['USE_LED'] = '1'
os.environ['LED_PIN_RED'] = '17'
os.environ['LED_PIN_GREEN'] = '27'
os.environ['LED_PIN_BLUE'] = '22'
os.environ['LED_COMMON_ANODE'] = '1'

from client.emotion_led import EmotionLED

def test_led():
    print("🔍 RGB LED接続テスト開始")
    print("=" * 50)
    
    try:
        led = EmotionLED()
        
        if not led.enabled:
            print("❌ LED制御が無効です")
            return
        
        emotions = ["喜び", "怒り", "悲しみ", "平常", "驚き", "恐れ"]
        
        print("\n各色を2秒ずつ点灯します...")
        for emotion in emotions:
            print(f"\n→ {emotion}")
            led.set_emotion(emotion)
            time.sleep(2)
        
        print("\n→ 消灯")
        led.clear()
        time.sleep(1)
        
        print("\n✅ テスト完了！")
        led.cleanup()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  テストが中断されました")
        led.cleanup()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    test_led()
EOF

chmod +x test_led.py
print_success "test_led.py を作成しました"

echo ""
print_success "🎉 セットアップが完了しました！"
echo ""
echo "📝 次のステップ:"
echo "1. RGB LEDをGPIOピンに接続:"
echo "   - 赤LED   → GPIO 17"
echo "   - 緑LED   → GPIO 27"
echo "   - 青LED   → GPIO 22"
echo "   - 共通端子 → 3.3V（共通アノード）または GND（共通カソード）"
echo ""
echo "2. LED接続テスト:"
echo "   python test_led.py"
echo ""
echo "3. クライアント実行（LED有効）:"
echo "   export USE_LED=1"
echo "   python -m client.run"
echo ""
print_warning "注意: gpioグループへの追加後は、以下のコマンドで再起動してください:"
echo "sudo reboot"
