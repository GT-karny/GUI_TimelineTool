# GUI Timeline Tool v0.6.0 リリースノート

## ハイライト
- **UDP テレメトリの常時連携** — メインウィンドウに Telemetry 設定グループを追加し、送信の有効/無効や宛先、レート、セッション ID を直感的に編集できるようにしました。設定は QSettings に保存され、TelemetryBridge がバックグラウンドスレッドで再生状態を監視しながら最新フレームのみを高精度に UDP 送信します。【F:app/ui/main_window.py†L42-L177】【F:app/ui/main_window.py†L300-L352】【F:app/playback/telemetry_bridge.py†L1-L118】【F:app/telemetry/settings.py†L1-L85】
- **キーフレーム編集ワークフローの刷新** — 新設の Key Inspector で単一選択キーの時刻と値をスピンボックスから精密に変更でき、Undo/Redo 対応のキーフレーム追加・削除・移動・値編集コマンドとマウス操作が統合されました。【F:app/ui/main_window.py†L70-L267】【F:app/ui/main_window.py†L280-L294】【F:app/ui/inspector.py†L1-L83】【F:app/actions/undo_commands.py†L1-L109】
- **操作性を高めるタイムライン UI** — Timeline Toolbar が補間モード・デュレーション・サンプルレート・再生/ループ・フィットをワンクリックで切り替えられるようにし、TimelinePlot が曲線・ポイント・プレイヘッド表示と安定した X/Y レンジ管理を提供します。【F:app/ui/toolbar.py†L1-L119】【F:app/ui/timeline_plot.py†L1-L123】

## 改善点
- **データ保存と共有を強化** — File メニューに新規作成、読み込み、名前を付けて保存を用意し、タイムラインを JSON プロジェクトとして入出力できます。CSV エクスポートもツールバーから実行でき、サンプルレートに合わせて補間値をサンプリングして書き出します。【F:app/ui/main_window.py†L188-L239】【F:app/ui/main_window.py†L366-L483】【F:app/io/project_io.py†L1-L22】【F:app/io/csv_exporter.py†L1-L10】【F:app/core/sampler.py†L1-L10】
- **テレメトリペイロードにバージョン情報を付加** — TelemetryAssembler がアプリのバージョン、セッション ID、フレーム番号とトラック値を含むコンパクトな JSON を生成し、外部連携時の整合性を高めます。【F:app/telemetry/assembler.py†L1-L33】

## 既知の制限
- v0.6.0 は単一の Float トラックを対象とした構成であり、マルチトラック編集や Undo 非対応の一部設定操作は今後の開発項目です。【F:documents/user_guide.md†L3-L55】
