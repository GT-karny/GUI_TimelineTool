# UDP テレメトリ運用ガイド

## Overview
- **送信条件**: タイムラインが再生状態のときのみ送信します。停止・一時停止時は送信しません。
- **プロトコル**: UDP / JSON もしくは UDP / Binary Float32（Telemetry メニューで切替）。1 メッセージ = 最新フレームのスナップショット。
- **デフォルト送信先**: `127.0.0.1:9000`
- **レート指定**: 設定パネルの「Rate (Hz)」で 1〜240 Hz の整数を指定。UI 上の表示は内部ガバナーへ即時反映されます。

## JSON フォーマット (v0.9.0)
| フィールド | 型 | 説明 |
| ---------- | --- | ---- |
| `version` | string | アプリケーションバージョン（例: `"0.9.0"`） |
| `session_id` | string | 送信セッション識別子。未設定時は起動毎に自動生成 |
| `timestamp_ms` | integer | タイムライン内の現在位置（ミリ秒） |
| `frame_index` | integer | 再生開始からのフレーム数 (0 起点) |
| `tracks` | array<object> | 各トラックの値配列。要素は `{"name": str, "values": number[]}` |

### サンプルペイロード
```json
{
  "version": "0.9.0",
  "session_id": "demo-session",
  "timestamp_ms": 1320,
  "frame_index": 33,
  "tracks": [
    {"name": "camera.fov", "values": [65.0]},
    {"name": "rig.lift", "values": [1.42, -0.1]}
  ]
}
```

## Binary Float Payload (v0.9.0)
- **構成**: 各トラックの `values` 配列を little-endian float32 で連結。playhead や frame index、track 名は含まれません。
- **用途**: 固定レイアウトの受信側で低レイテンシに扱いたいケース向け。JSON とは排他で、Telemetry メニューか設定値 `telemetry/payload_format` で選択します。
- **整列**: 4 バイト境界。浮動小数へ変換できない値は送信前に除外されます。
- **レイアウト補助**: `tools/telemetry_binary_receiver.py --layout 1,1,3` のようにトラックごとの値数を渡すと可読性が向上します。

## 送信タイミングとレート制御
- 送信スレッドは UI スレッドから独立しており、`time.perf_counter_ns()` ベースの高精度ガバナーでスケジューリングします。
- 1 フレームごとに締切時刻を固定ステップで進め、遅延が発生した場合は次回送信でドリフトを補正します。
- 再生中に複数フレームがスキップされるケースでも、常に最新フレームのみ送信し、過去フレームのバースト送信は行いません。

## 設定方法
| UI 上の項目 | QSettings キー | 型 | 備考 |
| ------------ | --------------- | --- | ---- |
| Enable UDP telemetry | `/telemetry/enabled` | bool | 送信を有効化するとスレッドが起動します |
| Target IP address | `/telemetry/ip` | str | 例: `127.0.0.1` |
| Target port | `/telemetry/port` | int | 例: `9000` |
| Rate (Hz) | `/telemetry/rate_hz` | int | 1〜240 の整数 |
| Session ID | `/telemetry/session_id` | str | 空欄時は自動生成 |
| Payload Format | `/telemetry/payload_format` | str | `"json"` または `"binary"`（Telemetry メニューから変更） |
| Loop playback | `/playback/loop_enabled` | bool | ループ状態はテレメトリにも反映されます |

- 設定値はアプリ終了後も保持され、次回起動時に復元されます。
- QSettings の保存先は OS 依存ですが、Qt の標準パスを使用します（レジストリ/`~/.config` 等）。

## 動作確認手順
1. 別ターミナルで受信スクリプトを起動します。
   - JSON: `python tools/udp_recv.py`
   - Binary: `python tools/telemetry_binary_receiver.py --layout 1,1`
2. アプリケーションでテレメトリ設定を開き、送信を有効化します。
3. 宛先 IP を `127.0.0.1`、ポートを `9000`、適当なレート（例: 60 Hz）に設定します。
4. Telemetry メニューで送信形式と Debug Log を選び、タイムラインを再生します。
5. バイナリ受信経路を単体検証したい場合は `python tools/telemetry_binary_sender.py --values 0.0,1.0 --increment 0.1` を使用します。

## 制限事項とベストプラクティス
- UDP は非同期・非保証のため、パケットロスや順序入れ替わりが発生する可能性があります。重要な制御には補助の確認機構を併用してください。
- 1 パケットの目安サイズは数百バイトです。トラックが多い場合はネットワーク負荷を考慮し、必要に応じてレートやトラック数を調整してください。
- 送信先がファイアウォールで制限されているとパケットが破棄されるため、必要に応じて例外設定を行います。
- 遅延やスキップが目立つ場合は、送信レートを下げる・他プロセスの負荷を減らすなどで対応してください。
- テレメトリが受信できないときは、(1) `tools/udp_recv.py` でローカル受信を確認、(2) 宛先 IP/ポートとネットワーク疎通、(3) アプリ側で再生中かどうか、の順に切り分けると効率的です。
