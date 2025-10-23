"""
感情に応じたLED制御モジュール
"""
import os
from typing import Optional

# ラズパイ環境でのみRPi.GPIOをインポート
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("⚠️  RPi.GPIOが利用できません。LED制御は無効化されています。")


class EmotionLED:
    """感情に応じてLEDを制御するクラス（RGB LED対応）"""
    
    # RGB LEDの各色ピン
    PIN_RED = int(os.getenv("LED_PIN_RED", "17"))
    PIN_GREEN = int(os.getenv("LED_PIN_GREEN", "27"))
    PIN_BLUE = int(os.getenv("LED_PIN_BLUE", "22"))
    
    # 共通ピンのタイプ（common_anode=True or common_cathode=False）
    IS_COMMON_ANODE = os.getenv("LED_COMMON_ANODE", "1") == "1"
    
    # 感情とRGB値のマッピング (0=OFF, 1=ON)
    EMOTION_COLORS = {
        "喜び": (0, 1, 0),    # 緑
        "怒り": (1, 0, 0),    # 赤
        "悲しみ": (0, 0, 1),  # 青
        "平常": (1, 1, 1)     # 白（全色点灯）
    }
    
    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: LED制御を有効にするか（環境変数 USE_LED でも制御可能）
        """
        self.enabled = enabled and GPIO_AVAILABLE
        # デフォルトは無効（"1"を設定した場合のみ有効）
        self.enabled = self.enabled and os.getenv("USE_LED", "0") == "1"
        self.current_pin: Optional[int] = None
        
        if self.enabled:
            try:
                self._setup_gpio()
                print("✅ 感情RGB LED制御を初期化しました")
                print(f"   赤: GPIO {self.PIN_RED}")
                print(f"   緑: GPIO {self.PIN_GREEN}")
                print(f"   青: GPIO {self.PIN_BLUE}")
                print(f"   タイプ: {'共通アノード' if self.IS_COMMON_ANODE else '共通カソード'}")
            except Exception as e:
                print(f"⚠️  GPIO初期化に失敗しました: {e}")
                print(f"    LED制御を無効化します")
                self.enabled = False
        else:
            print("ℹ️  感情LED制御は無効です")
    
    def _setup_gpio(self):
        """GPIOの初期設定（RGB LED用）"""
        if not self.enabled:
            return
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # RGB各ピンを出力モードに設定
        for pin in [self.PIN_RED, self.PIN_GREEN, self.PIN_BLUE]:
            GPIO.setup(pin, GPIO.OUT)
            # 共通アノードの場合、HIGHでOFF（反転ロジック）
            initial_state = GPIO.HIGH if self.IS_COMMON_ANODE else GPIO.LOW
            GPIO.output(pin, initial_state)
    
    def set_emotion(self, emotion: str):
        """
        感情に応じてRGB LEDの色を制御
        
        Args:
            emotion: 感情（喜び、怒り、悲しみ、平常）
        """
        if not self.enabled:
            return
        
        # 感情に対応するRGB色を取得
        if emotion in self.EMOTION_COLORS:
            r, g, b = self.EMOTION_COLORS[emotion]
            
            # 共通アノードの場合は論理を反転（HIGH=OFF, LOW=ON）
            if self.IS_COMMON_ANODE:
                r, g, b = not r, not g, not b
            
            # RGB各ピンに出力
            GPIO.output(self.PIN_RED, GPIO.HIGH if r else GPIO.LOW)
            GPIO.output(self.PIN_GREEN, GPIO.HIGH if g else GPIO.LOW)
            GPIO.output(self.PIN_BLUE, GPIO.HIGH if b else GPIO.LOW)
            
            self.current_pin = (r, g, b)  # RGB状態を記録
            print(f"💡 LED点灯: {emotion} -> RGB({r}, {g}, {b})")
        else:
            print(f"⚠️  未知の感情: {emotion}")
            self.current_pin = None
    
    def clear(self):
        """RGB LEDを消灯（すべての色をOFF）"""
        if not self.enabled:
            return
        
        # 共通アノードの場合、HIGH=OFF / 共通カソードの場合、LOW=OFF
        off_state = GPIO.HIGH if self.IS_COMMON_ANODE else GPIO.LOW
        
        GPIO.output(self.PIN_RED, off_state)
        GPIO.output(self.PIN_GREEN, off_state)
        GPIO.output(self.PIN_BLUE, off_state)
        
        self.current_pin = None
        print("💡 RGB LEDを消灯")
    
    def cleanup(self):
        """GPIO資源を解放"""
        if not self.enabled:
            return
        
        self.clear()
        GPIO.cleanup()
        print("✅ GPIO資源を解放しました")
    
    def __enter__(self):
        """コンテキストマネージャー"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了時にクリーンアップ"""
        self.cleanup()
