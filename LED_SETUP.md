# 感情LED機能 セットアップガイド

## 概要

感情分析結果に応じてラズパイのGPIOピンに接続されたLEDを制御します。

## ハードウェア要件

### 必要な部品

- LED × 4個（赤、緑、青、白/黄）
- 抵抗器 × 4個（220Ω または 330Ω）
- ジャンパーワイヤー

### 配線図

```
ラズパイ GPIO → 抵抗器 → LED+ → LED- → GND

感情      | LED色  | GPIOピン | 用途
---------|--------|----------|-------------
喜び      | 緑     | GPIO 17  | 喜びの感情表現
怒り      | 赤     | GPIO 27  | 怒りの感情表現
悲しみ    | 青     | GPIO 22  | 悲しみの感情表現
平常      | 白/黄  | GPIO 23  | 平常時の感情表現
```

### 接続例

```
GPIO 17 (喜び・緑LED)
  └─ 220Ω ─ LED(緑) ─ GND

GPIO 27 (怒り・赤LED)
  └─ 220Ω ─ LED(赤) ─ GND

GPIO 22 (悲しみ・青LED)
  └─ 220Ω ─ LED(青) ─ GND

GPIO 23 (平常・白LED)
  └─ 220Ω ─ LED(白) ─ GND
```

## ソフトウェアセットアップ

### 1. 依存パッケージのインストール

```bash
# ラズパイで実行
pip install RPi.GPIO
```

### 2. .envファイルの設定

`.env`ファイルに以下を追加：

```bash
# LED制御の有効化
USE_LED=1

# GPIOピンのカスタマイズ（オプション）
LED_PIN_JOY=17      # 喜び（緑LED）
LED_PIN_ANGER=27    # 怒り（赤LED）
LED_PIN_SAD=22      # 悲しみ（青LED）
LED_PIN_NORMAL=23   # 平常（白LED）
```

### 3. LED制御の無効化

LED機能を使わない場合：

```bash
USE_LED=0
```

## 使用方法

### 基本的な使用

```bash
cd ~/Projects/kokushimen-client
source .venv/bin/activate
python -m client.run
```

マイクに話しかけると、感情分析結果に応じてLEDが点灯します：

- **喜び**: 緑LED点灯 😊💚
- **怒り**: 赤LED点灯 😠❤️
- **悲しみ**: 青LED点灯 😢💙
- **平常**: 白LED点灯 😐🤍

### デバッグ

LED制御のログを確認：

```bash
python -m client.run
```

出力例：
```
✅ 感情LED制御を初期化しました
   喜び: GPIO 17
   怒り: GPIO 27
   悲しみ: GPIO 22
   平常: GPIO 23

😊 [感情分析]: 喜び
💡 LED点灯: 喜び (GPIO 17)
```

## トラブルシューティング

### LEDが点灯しない

1. **配線を確認**
   ```bash
   # GPIOテスト（GPIO 17を手動で制御）
   python3 << EOF
   import RPi.GPIO as GPIO
   GPIO.setmode(GPIO.BCM)
   GPIO.setup(17, GPIO.OUT)
   GPIO.output(17, GPIO.HIGH)  # LED点灯
   input("Press Enter to turn off LED...")
   GPIO.output(17, GPIO.LOW)   # LED消灯
   GPIO.cleanup()
   EOF
   ```

2. **抵抗値を確認**
   - 220Ω ～ 330Ωの抵抗を使用

3. **GPIOピンの設定を確認**
   ```bash
   cat .env | grep LED_PIN
   ```

### "RPi.GPIO" が見つからない

```bash
pip install RPi.GPIO
```

### 権限エラー

```bash
# ユーザーをgpioグループに追加
sudo usermod -a -G gpio $USER

# ログアウト/ログインして反映
```

## カスタマイズ

### GPIOピンの変更

`.env`ファイルで自由に変更可能：

```bash
LED_PIN_JOY=18      # 喜びを GPIO 18 に変更
LED_PIN_ANGER=24    # 怒りを GPIO 24 に変更
```

### RGB LEDを使用する場合

RGB LED（共通カソード）を使う場合は、`emotion_led.py`を拡張：

```python
# RGBの場合
EMOTION_RGB = {
    "喜び": (0, 255, 0),    # 緑
    "怒り": (255, 0, 0),    # 赤
    "悲しみ": (0, 0, 255),  # 青
    "平常": (255, 255, 255) # 白
}
```

## 安全上の注意

- GPIOピンは最大3.3Vです
- 過電流に注意してください
- 必ず抵抗器を使用してください
- LED の極性を確認してください（長い足が+）

## 参考資料

- [Raspberry Pi GPIO公式ドキュメント](https://www.raspberrypi.com/documentation/computers/os.html#gpio-and-the-40-pin-header)
- [RPi.GPIO ライブラリ](https://pypi.org/project/RPi.GPIO/)
