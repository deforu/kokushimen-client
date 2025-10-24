# 💡 Raspberry Pi 5用 LED制御ガイド

このガイドでは、Raspberry Pi 5で感情に応じたRGB LED制御を設定する方法を説明します。

## 🔧 必要なもの

### **ハードウェア**
- Raspberry Pi 5
- RGB LED（共通アノードまたは共通カソード）
- 抵抗器 x3（220Ω～330Ω推奨）
- ジャンパーワイヤー

### **ソフトウェア**
- Python 3.10以上
- gpiozero ライブラリ
- lgpio ライブラリ

## 🚀 クイックセットアップ

### **1. LEDセットアップスクリプトの実行**

```bash
./setup_led.sh
```

このスクリプトは以下を自動実行します：
- `gpiozero`と`lgpio`のインストール
- GPIOアクセス権限の設定
- LED制御設定の追加
- テストスクリプトの作成

### **2. RGB LEDの配線**

#### **共通アノード型（デフォルト）**

```
RGB LED配線図（共通アノード）

    Raspberry Pi 5                RGB LED
    ┌─────────────┐              ┌──────┐
    │ GPIO 17 ────┼──[220Ω]─────┼─ R   │
    │ GPIO 27 ────┼──[220Ω]─────┼─ G   │
    │ GPIO 22 ────┼──[220Ω]─────┼─ B   │
    │ 3.3V    ────┼──────────────┼─ +   │
    └─────────────┘              └──────┘
```

**ピン配置:**
- GPIO 17 (ピン11) → 赤LED → 220Ω抵抗
- GPIO 27 (ピン13) → 緑LED → 220Ω抵抗
- GPIO 22 (ピン15) → 青LED → 220Ω抵抗
- 3.3V (ピン1または17) → 共通アノード（長いピン）

#### **共通カソード型**

```
RGB LED配線図（共通カソード）

    Raspberry Pi 5                RGB LED
    ┌─────────────┐              ┌──────┐
    │ GPIO 17 ────┼──[220Ω]─────┼─ R   │
    │ GPIO 27 ────┼──[220Ω]─────┼─ G   │
    │ GPIO 22 ────┼──[220Ω]─────┼─ B   │
    │ GND     ────┼──────────────┼─ -   │
    └─────────────┘              └──────┘
```

共通カソード型を使用する場合は、`.env`ファイルで以下を設定：
```bash
LED_COMMON_ANODE=0
```

### **3. 接続テスト**

```bash
python test_led.py
```

各色が順番に2秒ずつ点灯すれば成功です！

### **4. クライアント実行**

```bash
export USE_LED=1
python -m client.run
```

## ⚙️ 環境変数設定

### **LED制御の有効化**
```bash
export USE_LED=1  # LED制御を有効化（0=無効）
```

### **GPIOピン番号のカスタマイズ**
```bash
export LED_PIN_RED=17      # 赤LEDのGPIOピン番号
export LED_PIN_GREEN=27    # 緑LEDのGPIOピン番号
export LED_PIN_BLUE=22     # 青LEDのGPIOピン番号
```

### **LED種類の指定**
```bash
export LED_COMMON_ANODE=1  # 共通アノード（1）または共通カソード（0）
```

## 🎨 感情とLED色の対応

| 感情 | RGB値 | 色 |
|------|-------|-----|
| 喜び | (0, 1, 0) | 緑 |
| 怒り | (1, 0, 0) | 赤 |
| 悲しみ | (0, 0, 1) | 青 |
| 平常 | (1, 1, 1) | 白 |
| 驚き | (1, 0.5, 0) | オレンジ |
| 恐れ | (0.5, 0, 0.5) | 紫 |

## 🔍 トラブルシューティング

### **エラー: "Cannot determine SOC peripheral base address"**

**原因:** 古い`RPi.GPIO`ライブラリがRaspberry Pi 5に対応していない

**解決策:** 
```bash
# 古いRPi.GPIOをアンインストール
pip uninstall RPi.GPIO

# gpiozeroとlgpioをインストール
pip install gpiozero lgpio
```

### **エラー: "Permission denied"**

**原因:** GPIOアクセス権限がない

**解決策:**
```bash
# gpioグループに追加
sudo usermod -a -G gpio $USER

# 再起動して反映
sudo reboot
```

### **LEDが点灯しない**

**チェック項目:**
1. **配線確認**: GPIOピン番号が正しいか
2. **抵抗値**: 220Ω～330Ωを使用しているか
3. **LED種類**: 共通アノード/カソードの設定が正しいか
4. **環境変数**: `USE_LED=1`が設定されているか

**デバッグコマンド:**
```bash
# GPIO状態確認
gpio readall

# テストスクリプト実行
python test_led.py

# 詳細ログ付きで実行
python -c "import os; os.environ['USE_LED']='1'; from client.emotion_led import EmotionLED; led=EmotionLED(); led.set_emotion('喜び')"
```

### **LEDが逆の動作をする**

**原因:** LED種類の設定が間違っている

**解決策:**
```bash
# 共通アノード → 共通カソードに変更
export LED_COMMON_ANODE=0

# または逆
export LED_COMMON_ANODE=1
```

## 📐 回路図（詳細）

### **Raspberry Pi 5のGPIOピン配置**

```
     3.3V  (1) (2)  5V
   GPIO 2  (3) (4)  5V
   GPIO 3  (5) (6)  GND
   GPIO 4  (7) (8)  GPIO 14
      GND  (9) (10) GPIO 15
  GPIO 17 (11) (12) GPIO 18  ← 赤LED
  GPIO 27 (13) (14) GND      ← 緑LED
  GPIO 22 (15) (16) GPIO 23  ← 青LED
     3.3V (17) (18) GPIO 24
  GPIO 10 (19) (20) GND
   GPIO 9 (21) (22) GPIO 25
  GPIO 11 (23) (24) GPIO 8
      GND (25) (26) GPIO 7
      ...
```

### **抵抗値の計算**

RGB LEDの一般的な仕様：
- 順方向電圧: 2.0V～3.3V
- 順方向電流: 20mA

抵抗値の計算式：
```
R = (Vcc - Vf) / If
R = (3.3V - 2.0V) / 0.02A = 65Ω（最小）
```

安全マージンを考慮して**220Ω～330Ω**を推奨します。

## 🔄 統合例

### **完全なセットアップコマンド**

```bash
# 1. LEDセットアップ
./setup_led.sh

# 2. 再起動（GPIO権限反映）
sudo reboot

# 3. 環境変数設定
source .venv/bin/activate
export USE_LED=1

# 4. LED接続テスト
python test_led.py

# 5. クライアント実行
python -m client.run
```

### **.envファイルの設定例**

```bash
# サーバー接続設定
SERVER_IP=220.158.21.165
SERVER_PORT=80
SERVER_AUTH_TOKEN=your-token

# 音声設定
INPUT_BACKEND=sounddevice
USE_SD=1

# LED制御設定
USE_LED=1
LED_PIN_RED=17
LED_PIN_GREEN=27
LED_PIN_BLUE=22
LED_COMMON_ANODE=1
```

## 🎓 参考情報

### **gpiozeroの特徴**
- Raspberry Pi 5完全対応
- シンプルで使いやすいAPI
- PWM（明るさ調整）対応
- 自動クリーンアップ

### **公式ドキュメント**
- gpiozero: https://gpiozero.readthedocs.io/
- Raspberry Pi GPIO: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html

## ✅ 動作確認チェックリスト

- [ ] `gpiozero`と`lgpio`がインストール済み
- [ ] ユーザーが`gpio`グループに所属
- [ ] RGB LEDが正しく配線されている
- [ ] 抵抗器が各LEDに接続されている
- [ ] `USE_LED=1`が設定されている
- [ ] `test_led.py`が正常に動作する
- [ ] クライアント実行時にLEDが点灯する

すべてチェックできたら準備完了です！🎉
