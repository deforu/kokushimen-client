"""
感情に応じたLED制御モジュール
Raspberry Pi 5対応版（gpiozero使用）
"""
import os
from typing import Optional

# Raspberry Pi 5対応: gpiozeroを使用
try:
    from gpiozero import LED as GPIO_LED
    from gpiozero import RGBLED
    GPIO_AVAILABLE = True
    print("✅ gpiozero を使用してGPIO制御を初期化します（Raspberry Pi 5対応）")
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️  gpiozeroが利用できません。LED制御は無効化されています。")
    print("    インストール: pip install gpiozero lgpio")


class EmotionLED:
    """感情に応じてLEDを制御するクラス（RGB LED対応・Raspberry Pi 5対応）"""
    
    # RGB LEDの各色ピン
    PIN_RED = int(os.getenv("LED_PIN_RED", "17"))
    PIN_GREEN = int(os.getenv("LED_PIN_GREEN", "27"))
    PIN_BLUE = int(os.getenv("LED_PIN_BLUE", "22"))
    
    # 共通ピンのタイプ（共通アノード=True、共通カソード=False）
    IS_COMMON_ANODE = os.getenv("LED_COMMON_ANODE", "1") == "1"
    
    # 感情とRGB値のマッピング (0.0=OFF, 1.0=ON)
    EMOTION_COLORS = {
        "喜び": (0.0, 1.0, 0.0),    # 緑
        "怒り": (1.0, 0.0, 0.0),    # 赤
        "悲しみ": (0.0, 0.0, 1.0),  # 青
        "平常": (1.0, 1.0, 1.0),    # 白（全色点灯）
        "驚き": (1.0, 0.5, 0.0),    # オレンジ
        "恐れ": (0.5, 0.0, 0.5),    # 紫
    }
    
    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: LED制御を有効にするか（環境変数 USE_LED でも制御可能）
        """
        self.enabled = enabled and GPIO_AVAILABLE
        # デフォルトは無効（"1"を設定した場合のみ有効）
        self.enabled = self.enabled and os.getenv("USE_LED", "0") == "1"
        self.rgb_led: Optional[RGBLED] = None
        
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
            print("ℹ️  感情LED制御は無効です（有効にするには: export USE_LED=1）")
    
    def _setup_gpio(self):
        """GPIOの初期設定（RGB LED用・gpiozero使用）"""
        if not self.enabled:
            return
        
        # RGBLEDオブジェクトを作成
        # active_high: 共通カソードならTrue、共通アノードならFalse
        self.rgb_led = RGBLED(
            red=self.PIN_RED,
            green=self.PIN_GREEN,
            blue=self.PIN_BLUE,
            active_high=not self.IS_COMMON_ANODE  # 共通アノードの場合は反転
        )
        
        # 初期状態: 消灯
        self.rgb_led.off()
    
    def set_emotion(self, emotion: str):
        """
        感情に応じてRGB LEDの色を制御
        
        Args:
            emotion: 感情（喜び、怒り、悲しみ、平常、驚き、恐れ）
        """
        if not self.enabled or self.rgb_led is None:
            return
        
        # 感情に対応するRGB色を取得
        if emotion in self.EMOTION_COLORS:
            r, g, b = self.EMOTION_COLORS[emotion]
            
            # RGBLEDの色を設定（0.0～1.0の値）
            self.rgb_led.color = (r, g, b)
            
            print(f"💡 LED点灯: {emotion} -> RGB({r:.1f}, {g:.1f}, {b:.1f})")
        else:
            print(f"⚠️  未知の感情: {emotion}")
            # デフォルトは白色
            self.rgb_led.color = (1.0, 1.0, 1.0)
    
    def clear(self):
        """RGB LEDを消灯（すべての色をOFF）"""
        if not self.enabled or self.rgb_led is None:
            return
        
        self.rgb_led.off()
        print("💡 RGB LEDを消灯")
    
    def cleanup(self):
        """GPIO資源を解放"""
        if not self.enabled or self.rgb_led is None:
            return
        
        self.clear()
        self.rgb_led.close()
        print("✅ GPIO資源を解放しました")
    
    def __enter__(self):
        """コンテキストマネージャー"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー終了時にクリーンアップ"""
        self.cleanup()

