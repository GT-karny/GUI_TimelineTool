# GUI Timeline Tool

GUI Timeline Tool は、モーションやアニメーションのパラメータをキーフレームで管理し、リアルタイムに再生・出力するための Python + Qt ベースの編集ツールです。最小限の操作でタイムラインを構築し、UDP テレメトリや CSV へのエクスポートを通じて外部システムへ値を連携できます。

## 主な機能
- キーフレームの追加・編集・削除、補間方式（Cubic / Linear / Step）の切り替え
- 再生・一時停止・停止・ループ再生の制御、および現在位置のシーク
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
3. 初回起動時は空のタイムラインが表示されます。必要に応じてトラックやキーフレームを追加してください。

## 基本操作
### 再生・停止・ループ
- ツールバーの ▶（再生）、⏸（一時停止）、■（停止）で再生状態を制御します。
- 🔁（ループ）を有効にすると、終端に達したときに先頭へ巻き戻ります。状態は設定として保存され、次回起動時にも復元されます。

### キーフレーム編集
- タイムライン上で右クリックしてキーフレームを追加します。
- キーフレームの補間方式はコンテキストメニューまたはプロパティパネルから選択できます（Cubic / Linear / Step）。

### CSV エクスポート
1. メニューバーの **File → Export CSV…** を選択します。
2. 保存先を指定すると、全トラックのキーフレームが時間順に書き出されます。

### UDP テレメトリの有効化
1. ツールバーまたはメニューから **Telemetry** パネルを開きます。
2. 「UDP 送信を有効化」をオンにし、宛先 IP・ポート・送信レート (Hz) を設定します。
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
│   ├── playback/     # 再生制御ロジック
│   ├── telemetry/    # テレメトリ生成とスケジューラ
│   ├── net/          # UDP 送信などネットワーク関連
│   └── io/           # CSV など入出力ユーティリティ
├── documents/        # ユーザー・開発者向けドキュメント
├── tools/            # 補助スクリプト（UDP 受信など）
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
