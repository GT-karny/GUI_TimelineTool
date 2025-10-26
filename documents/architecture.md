# アーキテクチャ概要

## スコープと現状
GUI Timeline Tool は単一 Float トラックを編集して再生・エクスポートするデスクトップアプリケーションです。PySide6 と pyqtgraph を用いて UI を構築しており、トラックは `app/core` に定義されたシンプルなデータモデル (`Timeline` → `Track` → `Keyframe`) で管理されます。

## 主なモジュールと責務
| モジュール | 役割 |
| ---------- | ---- |
| `app/ui` | `MainWindow`、タイムライン描画 (`TimelinePlot`)、Inspector、ツールバーなどのウィジェットを提供。 |
| `app/core` | タイムライン・トラック・キーフレームのデータモデルと補間 (`core/interpolation.py`) を実装。 |
| `app/interaction` | マウス操作と選択状態 (`MouseController`, `SelectionManager`) を管理。 |
| `app/actions` | Undo/Redo に利用する `QUndoCommand` 実装をまとめる。 |
| `app/playback` | 再生制御 (`PlaybackController`) と Telemetry 連携 (`telemetry_bridge.py`) を担当。 |
| `app/telemetry` | Telemetry の設定保持 (`settings.py`) と JSON ペイロード生成 (`assembler.py`)。 |
| `app/net` | 非同期 UDP 送信 (`udp_sender.py`) の軽量サービス。 |
| `app/io` | CSV エクスポートとプロジェクト保存/読込ユーティリティ。 |
| `app/tests` | コアロジックと GUI のスモークテスト。 |

## データフロー
1. `MainWindow` が `Timeline` モデルと `TimelinePlot` を接続し、`MouseController` を通じてキーフレーム操作を受け取ります。
2. 編集操作は Undo/Redo 可能な `QUndoCommand` によって `QUndoStack` に積まれます。
3. `PlaybackController` が QTimer でプレイヘッドを進め、`playhead_changed` シグナルで UI 描画と Telemetry を更新します。
4. Telemetry 有効時は `TelemetryBridge` が現在値を `TelemetryAssembler` に渡し、`UdpSenderService` が最新ペイロードを送信します。

## スレッドとライフサイクル
- **UI スレッド**: Qt のメインループ。すべてのウィジェットとユーザー操作を処理します。
- **TelemetryBridge スレッド**: `TelemetryBridge` 内で起動し、送信タイミングのガバナーを担当します。
- **UDP 送信スレッド**: `UdpSenderService` が保持。最新フレームのみを送信します。
- `MainWindow.closeEvent` で TelemetryBridge を確実に停止し、テストやアプリ終了時にスレッドが残らないようにしています。

## 永続化と設定
- QSettings (`TimelineTool` 名義) で Telemetry とループ設定を保存します。
- プロジェクトファイルは JSON フォーマットで単一トラックのキー列と補間モードを保持します。

## 今後の拡張ポイント
- 複数トラックやトラック種別の導入は `Timeline`/`Track` モデルと UI (`TimelinePlot`, Inspector) の抽象化が必要です。
- テスト層は `pytest-qt` による GUI スモークテストを起点に、操作シナリオの自動化へ拡張できます。
- PyInstaller を用いたスタンドアロン配布をフェーズ 0 で整備し、以降の機能強化と並行して保守します。
