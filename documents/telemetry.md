# Overview
- UDP ベースで JSON テレメトリを送信します。
- 再生中のみ送出され、停止・一時停止時は送信されません。
- 送信先のデフォルトは 127.0.0.1:9000 です。
- レートは設定パネルの "Rate (Hz)" で 1〜240 Hz の範囲で指定できます。

# JSON Schema (v1.0)
- `version`: プロトコルバージョン（例: "1.0"）
- `session_id`: 送信セッション識別子（自動生成または設定値）
- `timestamp_ms`: タイムラインの再生位置をミリ秒で表す整数
- `frame_index`: 再生開始からのフレーム番号（0 起点）
- `tracks`: `name`（トラック名）と `value`（値）を持つオブジェクトの配列

# Settings
- `/telemetry/enabled` (bool) — UDP テレメトリ送信の有効/無効
- `/telemetry/ip` (str) — 送信先 IP アドレス
- `/telemetry/port` (int) — 送信先ポート番号
- `/telemetry/rate_hz` (int, 1..240) — 送信レート（Hz）
- `/telemetry/session_id` (str, optional) — セッション ID（未指定時は自動生成）
- `/playback/loop_enabled` (bool) — ループ再生の有効/無効

# How to use
1. 設定パネルまたは QSettings で上記項目を設定します。
2. `Enable UDP telemetry` をオンにし、送信先 IP/Port/Rate を指定します。
3. 再生ボタンを押すとテレメトリが送信され、停止・一時停止で送信が止まります。
4. Toolbar の "Loop" ボタンでループ可否を切り替えられます。オンの場合は終端到達時に自動で巻き戻し、オフの場合は一巡で停止します。

# Timing
- 高精度レートガバナーを採用し、`time.perf_counter_ns()` を基準に送信周期を管理します。
- 期限ごとに固定ステップで締切を前進させ、オーバーラン時はドリフトを補正します。
- UI スレッドとは独立したバックグラウンドスレッドで送信が行われ、UI の描画や操作をブロックしません。

# Packet size & performance
- JSON エンコード時に `separators=(",", ":")` を指定して余分な空白を削減しています。
- 常に最新フレームのみを送信し、過去フレームのバースト送信は行いません。
- 送信スレッドは締切まで適切にスリープし、CPU 負荷を抑制します。

# Known limitations
- UDP の特性上、パケットロスが発生する可能性があります。
- 同一 LAN 以外への送信は推奨されません。
- トラック数が多い場合、JSON ペイロードが肥大化しネットワーク負荷が増大します。

# Test
1. `tools/udp_recv.py` を実行して待ち受けます。
2. アプリでテレメトリ送信を有効にし、タイムラインを再生します。
3. 受信側に JSON メッセージが表示されることを確認します。
