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

## 依存関係（任意/最小）

- 必須: `websockets`, `fastapi`, `uvicorn`
- 任意: `sounddevice`（入出力）。Pi Zero 2 W で軽量にする場合は未導入でも動作（NullPlayer / ToneGenerator）。
- 任意: `pyalsaaudio`（`alsaaudio`モジュール）: NumPyなしの軽量録音バックエンド。
- 任意: `webrtcvad`（将来 VAD 差し替え）。

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
# kokushimen-client
