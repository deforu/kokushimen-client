#!/usr/bin/env python3
"""
サーバー接続テストスクリプト
ラズパイでこのスクリプトを実行して、サーバーに接続できるか確認します
"""
import asyncio
import websockets
import os
from pathlib import Path

# .envファイルから環境変数を読み込む
def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        print(f"📄 .envファイルを読み込み中: {env_path}")
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
    else:
        print(f"⚠️  .envファイルが見つかりません: {env_path}")

load_env()

SERVER_IP = os.getenv("SERVER_IP", "220.158.21.165")
SERVER_PORT = os.getenv("SERVER_PORT", "8000")
AUTH_TOKEN = os.getenv("SERVER_AUTH_TOKEN", "dev-token")

# デバッグ: 環境変数の値を表示
print(f"🔍 読み込まれた環境変数:")
print(f"   SERVER_IP: {SERVER_IP}")
print(f"   SERVER_PORT: {SERVER_PORT}")
print(f"   AUTH_TOKEN: {AUTH_TOKEN}")
print()

async def test_connection():
    uri = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/test"
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    
    print(f"🔍 接続テスト開始...")
    print(f"   URI: {uri}")
    print(f"   Token: {AUTH_TOKEN}")
    
    try:
        print(f"⏳ 接続中... (タイムアウト: 10秒)")
        async with websockets.connect(
            uri, 
            additional_headers=headers,
            ping_interval=30,
            open_timeout=10
        ) as ws:
            print(f"✅ 接続成功！")
            print(f"   サーバー: {SERVER_IP}:{SERVER_PORT}")
            
            # playbackクライアントとして hello を送信
            import json
            await ws.send(json.dumps({"type": "hello", "role": "playback"}))
            print(f"📤 hello メッセージ送信完了")
            
            # サーバーからの応答を3秒待つ
            print(f"⏳ サーバーからの応答を待機中...")
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                print(f"📥 サーバーから応答受信: {response}")
            except asyncio.TimeoutError:
                print(f"ℹ️  タイムアウト: サーバーからの応答なし (正常)")
            
            print(f"✅ テスト成功！接続は正常です。")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ 接続失敗: HTTPステータスコードエラー")
        print(f"   ステータス: {e.status_code}")
        print(f"   考えられる原因:")
        print(f"   - サーバーが起動していない")
        print(f"   - 認証トークンが間違っている")
        
    except websockets.exceptions.InvalidURI as e:
        print(f"❌ 接続失敗: 無効なURI")
        print(f"   エラー: {e}")
        print(f"   考えられる原因:")
        print(f"   - SERVER_IPまたはSERVER_PORTの設定が間違っている")
        
    except asyncio.TimeoutError:
        print(f"❌ 接続タイムアウト")
        print(f"   考えられる原因:")
        print(f"   - サーバーが起動していない")
        print(f"   - ファイアウォールでポート {SERVER_PORT} がブロックされている")
        print(f"   - ネットワークが到達できない")
        
    except ConnectionRefusedError:
        print(f"❌ 接続拒否")
        print(f"   考えられる原因:")
        print(f"   - サーバーが {SERVER_IP}:{SERVER_PORT} で起動していない")
        print(f"   - ポート番号が間違っている")
        
    except OSError as e:
        print(f"❌ ネットワークエラー: {e}")
        print(f"   考えられる原因:")
        print(f"   - ネットワーク接続の問題")
        print(f"   - DNSの解決失敗")
        
    except Exception as e:
        print(f"❌ 予期せぬエラー: {type(e).__name__}")
        print(f"   詳細: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket接続テスト")
    print("=" * 60)
    asyncio.run(test_connection())
    print("=" * 60)
