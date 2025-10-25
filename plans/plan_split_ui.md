```
app/
  __init__.py
  core/                          # 既存: Timeline/Keyframe/Interp/evaluate 等
    __init__.py
  io/                            # 既存: CSV 出力
    __init__.py
    csv_exporter.py
  ui/
    __init__.py
    main_window.py               # 画面統括・配線のみ（状態/ロジック持たない）
    toolbar.py                   # ツールバーUI。Signalだけ外に出す
    timeline_plot.py             # Plot描画・playhead表示・X/Yレンジ制御
  interaction/
    __init__.py
    selection.py                 # 選択集合・ヒットテスト・マルキー確定
    mouse_controller.py          # マウス仕様（eventFilter）・ドラッグ移動/ズーム/パン
  playback/
    __init__.py
    player.py                    # 再生タイマーとplayhead更新
  actions/
    __init__.py
    timeline_actions.py          # 追加/削除/リセット/エクスポートなどのコマンド群
```

# 各ファイルに“何を書くか”（超要約）

ui/main_window.py：モデル生成、各モジュール接続、再描画トリガ。

ui/toolbar.py：コンボ/ボタン群＋ sig_* を発火。

ui/timeline_plot.py：曲線・点・playheadの描画APIと fit_x/y。

interaction/selection.py：selected_ids 管理、ヒットテスト、矩形選択の開始/更新/確定。

interaction/mouse_controller.py：左=選択/移動/マルキー、中=パン、右=ピボット拡縮/メニュー。

playback/player.py：QTimer で set_playhead(t) を周期更新。

actions/timeline_actions.py：add_key_at(t), delete_selected(ids), reset_keys(), export_csv_dialog(parent)。

# 作成順のおすすめ（段階的に）

ui/timeline_plot.py

ui/toolbar.py

ui/main_window.py（ここで上2つを接続）

interaction/selection.py

interaction/mouse_controller.py

playback/player.py

actions/timeline_actions.py