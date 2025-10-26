# 開発者ガイド

## ディレクトリ構成と責務
| パス | 役割 |
| ---- | ---- |
| `app/app.py` | アプリケーションのエントリーポイント。Qt アプリと `MainWindow` を初期化します。 |
| `app/ui/` | `MainWindow`、`TimelinePlot`、`KeyInspector`、ツールバーなど UI レイヤを構成するウィジェット群。 |
| `app/core/` | タイムライン (`Timeline`/`Track`/`Keyframe`) のデータモデルと補間ロジック。単一 Float トラック前提の実装です。 |
| `app/interaction/` | マウス操作と選択状態 (`MouseController`, `SelectionManager`) のハンドリング。 |
| `app/actions/` | Undo/Redo に対応した `QUndoCommand` 実装をまとめています。 |
| `app/playback/` | プレイヘッド制御 (`PlaybackController`) と Telemetry 連携 (`telemetry_bridge.py`)。 |
| `app/telemetry/` | Telemetry 設定 (`settings.py`) と JSON ペイロード生成 (`assembler.py`)。 |
| `app/net/` | 非同期 UDP 送信を担う `UdpSenderService`。 |
| `app/io/` | CSV エクスポートと JSON プロジェクト入出力。 |
| `app/tests/` | `pytest` ベースのユニットテストと GUI スモークテスト。 |
| `tools/` | `udp_recv.py` や `run_checks.sh` などの開発支援スクリプト。 |

## セットアップ
1. 仮想環境を作成して依存パッケージをインストールします。
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows は .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
2. ランタイム依存に加えて、`pytest` / `pytest-qt` / `black` / `isort` / `mypy` など開発用ツールも `requirements.txt` に含まれています。

## コーディング規約と自動チェック
- フォーマッタは `black` (line-length 100)、インポート整形は `isort` (`profile = "black"`) を使用します。
- 型チェックには `mypy`（Python 3.10 ターゲット、Qt 系は `ignore_missing_imports`）を用います。
- ルートに配置した `tools/run_checks.sh` で `black --check` / `isort --check-only` / `mypy app` / `pytest` を一括実行できます。
  ```bash
  ./tools/run_checks.sh
  ```
- CI へ統合する場合も同スクリプトの呼び出しを推奨します。

## データフロー概要
1. `MainWindow` が `Timeline` モデルと `TimelinePlot` を接続し、`MouseController` でキーフレーム操作を受け取ります。
2. 編集操作は `app/actions/undo_commands.py` の `QUndoCommand` を通じて `QUndoStack` に積まれ、Undo/Redo に対応します。
3. `PlaybackController` が Qt の `QTimer` で再生ヘッドを進め、描画更新と Telemetry 送信をトリガします。
4. Telemetry が有効な場合、`TelemetryBridge` が最新スナップショットを `TelemetryAssembler` で JSON 化し、`UdpSenderService` が非同期送信します。

## テスト
- ユニットテストは `pytest` を用いて `app/tests/` から実行します。
- GUI スモークテスト（`test_main_window_smoke.py`）は `pytest-qt` の `qtbot` フィクスチャで `MainWindow` を生成し、主要ウィジェットの存在と基本操作を検証します。
- 新しい UI を追加する際は同テストを拡張し、ウィジェットの生成に失敗しないことを確認してください。

## PyInstaller による配布
- フェーズ 0 で Windows 向けスタンドアロン配布を整備する方針です。PyInstaller ベースでバンドル構成を検証し、最初の実行ファイル生成を優先して実施します。
- バンドル設定（spec ファイル）は `tools/` 配下に追加し、生成手順を `documents/` に追記する予定です。
- PyInstaller パイプラインを更新した際は、最低限 GUI 起動と CSV エクスポートが動作することを手動確認してください。

## トラブルシュートのヒント
- Telemetry 送信が不要なテストケースでは `MainWindow.close()` を呼び、`TelemetryBridge.shutdown()` が確実に実行されるようにします。
- `pyqtgraph` のシーンを触るテストを追加する場合は、`qtbot.wait()` を挟んでイベントループを回すと安定します。
- 依存ライブラリの更新時は `requirements.txt` と `pyproject.toml` の設定が整合しているか確認してください。
