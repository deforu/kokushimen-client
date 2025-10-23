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
    """感情に応じてLEDを制御するクラス"""
    
    # 感情とGPIOピンのマッピング
    EMOTION_PINS = {
        "喜び": int(os.getenv("LED_PIN_JOY", "17")),      # 緑
        "怒り": int(os.getenv("LED_PIN_ANGER", "27")),   # 赤
        "悲しみ": int(os.getenv("LED_PIN_SAD", "22")),    # 青
        "平常": int(os.getenv("LED_PIN_NORMAL", "23"))   # 白/黄
    }
    
    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: LED制御を有効にするか（環境変数 USE_LED でも制御可能）
        """
        self.enabled = enabled and GPIO_AVAILABLE
        self.enabled = self.enabled and os.getenv("USE_LED", "1") == "1"
        self.current_pin: Optional[int] = None
        
        if self.enabled:
            self._setup_gpio()
            print("✅ 感情LED制御を初期化しました")
            for emotion, pin in self.EMOTION_PINS.items():
                print(f"   {emotion}: GPIO {pin}")
        else:
            print("ℹ️  感情LED制御は無効です")
    
    def _setup_gpio(self):
        """GPIOの初期設定"""
        if not self.enabled:
            return
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # すべてのピンを出力モードに設定し、初期状態をOFFに
        for pin in self.EMOTION_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
    
    def set_emotion(self, emotion: str):
        """
        感情に応じたLEDを点灯
        
        Args:
            emotion: 感情（喜び、怒り、悲しみ、平常）
        """
        if not self.enabled:
            return
        
        # 現在点灯中のLEDを消灯
        if self.current_pin is not None:
            GPIO.output(self.current_pin, GPIO.LOW)
        
        # 新しい感情のLEDを点灯
        pin = self.EMOTION_PINS.get(emotion)
        if pin is not None:
            GPIO.output(pin, GPIO.HIGH)
            self.current_pin = pin
            print(f"💡 LED点灯: {emotion} (GPIO {pin})")
        else:
            print(f"⚠️  未知の感情: {emotion}")
            self.current_pin = None
    
    def clear(self):
        """すべてのLEDを消灯"""
        if not self.enabled:
            return
        
        for pin in self.EMOTION_PINS.values():
            GPIO.output(pin, GPIO.LOW)
        self.current_pin = None
        print("💡 すべてのLEDを消灯")
    
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
