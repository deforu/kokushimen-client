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
 
