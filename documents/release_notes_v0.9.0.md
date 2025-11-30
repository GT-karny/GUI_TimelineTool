# Timeline Tool v0.9.0 Release Notes

## 概要
- リリース日: 2025-11-21
- 主なテーマ: テレメトリ送信モードの拡張と Sync モードの安定化

## 追加機能
- **Telemetry メニューを新設**し、JSON / Binary Float32 の送信切替と Debug Log のオン/オフを GUI から即時操作できるようにしました。
- **バイナリペイロードモード**を実装。各トラックの Float 値のみを little-endian float32 で送出でき、受信側で固定レイアウトを想定した高速ストリーミングが可能です。
- **テスト用ツール**を追加:
  - `tools/telemetry_binary_receiver.py`: バイナリモードの受信レイアウトを確認。
  - `tools/telemetry_binary_sender.py`: 外部システムなしで受信経路を検証するための簡易送信機。

## 改善点
- テレメトリ設定・ユーザーガイド・README などのドキュメントを v0.9.0 内容に更新し、トラブルシュート手順を整理しました。
- Telemetry Panel の UI と設定保存にペイロード形式を追加し、QSettings へ永続化されるようにしました。

## バグ修正
- **Sync Mode**: 受信スレッドから UI へのディスパッチで `invokeMethod` の使用方法が誤っていた問題を修正し、`tools/sync_test.py` から送った float 値が確実にプレイヘッドへ反映されるようになりました。
- **Playback スケジューラ**: `force_send=False` かつ `next_deadline` が未設定の初回送信で即時送信されてしまう不具合を修正し、通常再生開始時もレートに沿って送出されます。
- Sync Mode のデバッグログを強化し、UDP スレッド/メインスレッド双方で受信値を確認できるようにしました。

## 互換性
- 既存のプロジェクトファイル形式に変更はありません。
- QSettings に `telemetry/payload_format` (既定値 `json`) が追加されます。アップデート後初回起動時に自動的に設定されます。

## 今後の予定
- バイナリモードのメタデータ付与や、固定長トラック構成の自動検出機能を検討中です。

---
v0.8.0 以前の変更履歴は `documents/release_notes_v0.6.0.md` を参照してください。

