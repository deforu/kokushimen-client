# kokusimen-client (MVP)

クライアント（ラズパイ想定）と、疎通確認用のモックサーバの雛形です。

## 構成

- `client/` クライアント実装（asyncio + websockets）。
  - 音声入力: `ToneGeneratorSource`（テスト用）。`SoundDeviceSource` は任意依存。
  - 無音検出: NumPy 非依存の RMS 実装（閾値と連続時間）。
  - 送信: 20ms/640bytes の PCM_S16LE を WS で送信。無音>=400ms で `{"type":"stop"}`。
  - 受信: 200ms チャンク→ジッタバッファで20ms整流→出力。
- `mock_server/` FastAPI + WebSocket の簡易モック。
  - `sender` から `stop` を受けると、`playback` に 1秒のビープ音を 200ms 刻みで送信。

## 動作イメージ（音声の流れ）

```
┌──────────┐    20ms/640B        ┌────────────┐     200ms/6400B      ┌──────────┐
│  client  │ ───────────────▶ │  mock_server │ ───────────────────▶ │ playback │
│  sender  │  PCM_S16LE       │   /ws (WS)   │   TTS(擬似ビープ)     │  client  │
└──────────┘  無音>=400msでstop └────────────┘   final_asr/tts_done   └──────────┘

説明:
- sender: クライアントの送信役。20msごと（640バイト）に音声の生データを送信。
- mock_server: `stop` を受けたら、TTSの代わりに1秒のビープを200ms刻みで返す。
- playback: 受信した200msチャンクをジッターバッファで20ms単位に整えて再生。
```

用語ミニ解説:
- PCM_S16LE: 音の生データ形式（16ビット整数、リトルエンディアン）。
- フレーム/チャンク: 小分けした音データの単位（本プロジェクトでは20ms=フレーム、200ms=チャンク）。
- VAD: Voice Activity Detection。発話があるか（無音か）を判定する仕組み。
- ジッターバッファ: ネットワーク到着のばらつきを吸収し、一定間隔で出力するためのバッファ。

## 依存関係（任意/最小）

- 必須: `websockets`, `fastapi`, `uvicorn`
- 任意: `sounddevice`（入出力）。Pi Zero 2 W で軽量にする場合は未導入でも動作（NullPlayer / ToneGenerator）。
- 任意: `pyalsaaudio`（`alsaaudio`モジュール）: NumPyなしの軽量録音バックエンド。
- 任意: `webrtcvad`（将来 VAD 差し替え）。

## クイックスタート（初心者向け）

1) Python 仮想環境（任意）を用意

- Windows PowerShell:
  - `python -m venv .venv`
  - `./.venv/Scripts/Activate.ps1`
- macOS/Linux:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`

2) 必要パッケージをインストール

```
pip install websockets fastapi uvicorn
# 任意: 再生/録音を実機で使う場合
# pip install sounddevice         # 再生/録音（NumPy依存あり）
# pip install pyalsaaudio         # Linux/ALSAでの軽量録音
```

3) モックサーバを起動（別ターミナルで実行）

```
uvicorn mock_server.app:app --reload --host 0.0.0.0 --port 8000
```

4) クライアントを実行

- macOS/Linux（bash/zsh）
  ```bash
  export SERVER_WS=ws://127.0.0.1:8000/ws
  export AUTH_TOKEN=dev-token
  # 音を出す場合（sounddeviceを入れているとき）
  # export USE_SD=1
  python -m client.run
  ```

- Windows PowerShell
  ```powershell
  $env:SERVER_WS = "ws://127.0.0.1:8000/ws"
  $env:AUTH_TOKEN = "dev-token"
  # 音を出す場合
  # $env:USE_SD = "1"
  python -m client.run
  ```

動作の見え方:
- 既定では NullPlayer（音は鳴らさず待つだけ）なので、音は出ません。
- `USE_SD=1` かつ `sounddevice` が導入されていれば、サーバからのビープ音が再生されます。
- 送信側は無音が約400ms続くと `stop` を出し、サーバがTTS（ビープ）を返します。この間はクライアントのマイク送信がミュートされます。

## 実行（モックサーバ）

```bash
uvicorn mock_server.app:app --reload --host 0.0.0.0 --port 8000
```

## 実行（クライアント）

```bash
export SERVER_WS=ws://127.0.0.1:8000/ws
export AUTH_TOKEN=dev-token
python -m client.run
```

sounddevice を使う場合:

```bash
pip install sounddevice
export USE_SD=1
python -m client.run
```

ALSAバックエンド（NumPyなしで録音）:

```bash
pip install pyalsaaudio
export INPUT_BACKEND=alsa
python -m client.run
```

## 次の実装ポイント

- 実マイク入力（`SoundDeviceSource`）のデバイス指定 / 並列 2 系統同時稼働
- webrtcvad による VAD 置換（低負荷）
- 再生中ミュート・録音バッファクリアの制御線（実装済み・要調整）
- ジッタバッファ（200ms受信→20ms出力）（実装済み・要調整）
- 認証（JWT 検証方式の確定: HS256/RS256）
 

## Raspberry Pi 5 セットアップ（Raspberry Pi OS 64-bit/Bookworm）

最小構成（疎通確認）→ 実機動作（再生/録音）へ段階的に進めます。

### 前提
- Python 3.10+ がインストール済み（Raspberry Pi OS 標準で可）。
- サーバは同リポジトリ内の `kokushimen-server` を推奨（モックサーバは一部プロトコル非互換）。

### APT 依存のインストール
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev build-essential \
  libportaudio2 portaudio19-dev \
  libasound2-dev alsa-utils
# 音声デバイス権限
sudo usermod -a -G audio $USER  # 反映には再ログイン（または再起動）が必要
```

### Python 仮想環境
```bash
cd kokusimen-client
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### Python パッケージ
- 最小（疎通確認のみ）
```bash
pip install websockets fastapi uvicorn
```
- 再生（sounddevice を使う場合）
```bash
pip install numpy sounddevice
```
- 軽量録音（ALSA）
```bash
pip install pyalsaaudio   # 失敗する場合は:  sudo apt install -y python3-alsaaudio
```

### サーバ接続の設定
- 推奨: `kokushimen-server` を起動（同一機/別機どちらでも）
  ```bash
  # 別シェルで
  cd kokushimen-server
  python main.py
  ```
- クライアント側（本プロジェクト）
  ```bash
  # サーバのIPを設定（例）
  export SERVER_IP=192.168.1.50
  # 認証トークン（開発中は dev-token）
  export SERVER_AUTH_TOKEN=dev-token
  ```

モックサーバを使う場合（注意: 現行クライアントと一部非互換）
```bash
uvicorn mock_server.app:app --reload --host 0.0.0.0 --port 8000
# クライアント側は /ws に上書き（既定は /ws/self などのため）
export SERVER_WS_SELF=ws://$SERVER_IP:8000/ws
export SERVER_WS_OTHER=ws://$SERVER_IP:8000/ws
export SERVER_WS_PLAYBACK=ws://$SERVER_IP:8000/ws
export SERVER_AUTH_TOKEN=dev-token
```

### 基本起動（疎通確認・音なし）
```bash
export INPUT_BACKEND=tone   # 内蔵トーンを送信
export USE_SD=0             # 再生は無効（NullPlayer）
python -m client.run
```
期待動作: 無音が約400ms続くたび `stop` を送信。サーバがTTS応答を返す構成なら動作が進みます。

### 再生を有効化（sounddevice）
```bash
export SD_LIST_DEVICES=1    # 一度デバイス一覧を表示
export USE_SD=1
python -m client.run
# 出力デバイスを指定する場合（番号 or 名前部分一致）
# export SD_OUTPUT_DEVICE=1
# export SD_OUTPUT_DEVICE='USB'
# export SD_MATCH_EXACT=1    # 厳密一致に切り替え
```

### 録音を有効化
- 軽量（ALSA）
```bash
pip install pyalsaaudio
export INPUT_BACKEND=alsa
python -m client.run
# デバイス確認: arecord -l
```
- sounddevice（NumPy依存あり）
```bash
pip install numpy sounddevice
export INPUT_BACKEND=sounddevice
# 入力デバイスの指定（self/other）
# export SD_INPUT_DEVICE_SELF='1'        # 例: 番号
# export SD_INPUT_DEVICE_SELF='USB Mic'  # 例: 名称部分一致
# export SD_INPUT_DEVICE_OTHER='...'     # 2系統目を使う場合
python -m client.run
```

### VAD（無音検出）の調整（必要に応じて）
```bash
export VAD_THRESHOLD=0.02   # 小さくすると敏感
export VAD_MIN_SIL_MS=400   # 無音継続時間
export VAD_DEBUG=1          # デバッグ出力
```

### ラズパイのIPを確認（SERVER_IP 設定用）
```bash
hostname -I | awk '{print $1}'
# もしくは
ip -4 addr show scope global | grep -oP 'inet \K[\d.]+'
```

### トラブルシュート
- 音が出ない: `alsamixer` でミュート解除/音量調整、`aplay /usr/share/sounds/alsa/Front_Center.wav` で確認。
- 権限エラー: `audio` グループ反映のため再ログイン（または `sudo reboot`）。
- sounddevice エラー: `numpy` 未導入 or PortAudio 不足。APT と `pip install numpy sounddevice` を再確認。
- モックサーバで音が返らない: 現行クライアントは `hello` を送らないため挙動が限定的。`kokushimen-server` での検証を推奨。
