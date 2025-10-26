# GUI Timeline Tool

GUI Timeline Tool は、単一の Float トラックをキーフレームで編集し、再生や外部出力に活用できる Python + Qt ベースのタイムラインエディタです。現在はシンプルな 1 トラック構成にフォーカスしており、CSV エクスポートや UDP テレメトリを備えたスタンドアロンアプリケーションとして開発を進めています。

## 主な機能
- 単一 Float トラックでのキーフレーム追加・編集・削除、補間方式（Cubic / Linear / Step）の切り替え
- Inspector パネルからの数値編集、Undo/Redo 対応のドラッグ操作
- 再生・停止・ループ切り替え、ズーム/フィットなどのビュー操作
- タイムライン内容の CSV エクスポート
- 再生中のみ発火する UDP JSON テレメトリ送信（送信先・周波数を指定可能）
- 設定内容の永続化（QSettings 利用）

## 動作環境
- Python 3.10 以上を推奨
- PySide6 または PyQt6（`requirements.txt` に準拠）
- Windows / macOS / Linux いずれかのデスクトップ環境

## セットアップ
1. 依存パッケージをインストールします。
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows は .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
2. アプリケーションを起動します。
   ```bash
   python -m app.app
   ```
3. 初回起動時は 0 秒と duration 秒に 2 つのキーフレームを持つ単一トラックが表示されます。ダブルクリックやツールバーからキーを追加して編集を開始してください。

## パッケージング (Windows 向け実行ファイル)
開発環境で PyInstaller を利用してスタンドアロンの実行ファイルを生成できます。

```bash
pyinstaller --clean --noconfirm tools/timeline_tool.spec
```

コマンド完了後、`dist/TimelineTool/TimelineTool.exe` が生成されます。Windows 環境でこのファイルを実行して GUI アプリケーションが起動することを確認してください。

## 基本操作
### 再生・停止・ループ
- ツールバーの ▶（再生）、⏸（一時停止）、■（停止）で再生状態を制御します。
- 🔁（ループ）を有効にすると、終端に達したときに先頭へ巻き戻ります。状態は設定として保存され、次回起動時にも復元されます。

### キーフレーム編集
- タイムラインをダブルクリックするとその位置にキーフレームが追加されます。ツールバーの `+` ボタンでもプレイヘッド位置に追加できます。
- 単一キーを選択すると Inspector パネルに時刻と値が表示され、直接編集できます。
- 右クリックメニューの *Delete Nearest* で近傍キーを削除できます。

### CSV エクスポート
1. メニューバーの **File → Export CSV…** を選択します。
2. 保存先を指定すると、全トラックのキーフレームが時間順に書き出されます。

### UDP テレメトリの有効化
1. メインウィンドウ上部の Telemetry グループで「Enable UDP telemetry」をオンにします。
2. 宛先 IP・ポート・送信レート (Hz)・Session ID を入力します。
3. 再生ボタンを押すと、再生中のみ JSON メッセージが送出されます。詳しい仕様は [documents/telemetry.md](documents/telemetry.md) を参照してください。

## UDP テレメトリの概要
- 送信プロトコル: UDP / JSON
- 送信タイミング: 再生中のみ。停止・一時停止時は送信されません。
- 既定宛先: `127.0.0.1:9000`
- 最小受信確認: `python tools/udp_recv.py`
- 詳細仕様とトラブルシュートは [documents/telemetry.md](documents/telemetry.md) にまとめています。

## 設定 (QSettings)
主要なキーと用途は次のとおりです。値は OS ごとの標準ロケーションに保存され、次回起動時に自動復元されます。

| キー | 型 | 説明 |
| ---- | --- | ---- |
| `/telemetry/enabled` | bool | UDP テレメトリ送信の有効 / 無効 |
| `/telemetry/ip` | str | 送信先 IP アドレス |
| `/telemetry/port` | int | 送信先ポート番号 |
| `/telemetry/rate_hz` | int | 送信周波数 (Hz) |
| `/telemetry/session_id` | str | 送信セッション識別子 |
| `/playback/loop_enabled` | bool | ループ再生設定 |

個別の設定値や UI 操作との対応は [documents/telemetry.md](documents/telemetry.md) および [documents/user_guide.md](documents/user_guide.md) を参照してください。

## ディレクトリ構成
```
GUI_TimelineTool/
├── app/              # アプリケーション本体
│   ├── ui/           # Qt UI レイヤ
│   ├── interaction/  # マウス操作と選択ハンドリング
│   ├── actions/      # QUndoCommand ベースの操作群
│   ├── playback/     # 再生制御ロジックと TelemetryBridge
│   ├── telemetry/    # テレメトリ設定と JSON 生成
│   ├── net/          # UDP 送信サービス
│   └── io/           # CSV・プロジェクト入出力ユーティリティ
├── documents/        # ユーザー・開発者向けドキュメント
├── tools/            # 補助スクリプト（UDP 受信など）
├── pyproject.toml    # black/isort/mypy の設定
├── requirements.txt  # 依存パッケージ一覧
└── README.md
```

詳細な構造やコードの責務は [documents/architecture.md](documents/architecture.md) と [documents/developer_guide.md](documents/developer_guide.md) にまとめています。

## 貢献・開発の始め方
1. 本リポジトリをフォークし、ローカルへクローンします。
2. 上記セットアップ手順に従って実行環境を整えます。
3. 機能追加や修正はトピックブランチ（例: `feature/xxxx`）で行い、テストと lint を実行したうえで Pull Request を作成してください。
4. 詳細な開発方針は [documents/developer_guide.md](documents/developer_guide.md) を参照してください。

## ライセンス
本リポジトリの正式なライセンスは未定です。プロジェクト方針に合わせて本節を更新してください。
