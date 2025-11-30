# 開発ガイド

GUI Timeline Tool プロジェクトへようこそ！このドキュメントは、プロジェクトの構造を理解し、開発をスムーズに開始するためのガイドです。

## プロジェクト概要

これは、**PySide6** (Qt for Python) と **pyqtgraph** を使用して構築された、タイムライン編集用の Python GUI アプリケーションです。トラックの管理、キーフレームの追加、再生制御などを行うことができます。

## ディレクトリ構成

ソースコードは `app` ディレクトリ内にあります。主なサブディレクトリの内訳は以下の通りです：

- **`app/`**: メインパッケージ。
    - **`app.py`**: アプリケーションのエントリーポイント。
    - **`core/`**: コアデータモデルとロジック。
        - `timeline.py`: `Timeline`、`Track`、`Keyframe` クラスを定義。
        - `interpolation.py`: カーブ補間ロジックを処理。
    - **`ui/`**: ユーザーインターフェースコンポーネント (Widgets)。
        - `main_window.py`: メインアプリケーションウィンドウ。
        - `track_container.py`: トラックリストを管理。
        - `track_row.py`: 単一のトラック行 (名前 + プロット) を表現。
        - `timeline_plot.py`: pyqtgraph を使用したカーブとキーフレームの描画を担当。
        - `theme.py`: アプリケーションのテーマ (ダークモード) を管理。
    - **`playback/`**: 再生制御ロジック。
        - `controller.py`: プレイヘッド位置と再生状態を管理。
    - **`interaction/`**: マウスとキーボードのインタラクションロジック。
        - `mouse_controller.py`: タイムライン上のマウスイベントを処理。
        - `selection.py`: 選択状態を管理。
    - **`actions/`**: Undo/Redo コマンド。

## 主要コンポーネント

### データモデル
- **`Timeline`**: `Track` のリストを持つルートオブジェクト。
- **`Track`**: `Keyframe` のリストを持つ単一のアニメーションチャンネル。
- **`Keyframe`**: 値を持つ時点 (`t`, `v`)。

### UI アーキテクチャ
- **`MainWindow`**: 中心となるハブ。モデル、コントローラー、UI コンポーネントを初期化します。
- **`TrackContainer`**: 全ての `TrackRow` をリスト表示するスクロール可能なウィジェット。トラックの追加/削除を処理します。
- **`TrackRow`**: 名前用の `QLineEdit` と `TimelinePlot` を含む複合ウィジェット。
- **`TimelinePlot`**: `pyqtgraph.PlotWidget` のラッパー。カーブを描画し、ズーム/パンを処理します。

## 実行方法

1. **仮想環境のアクティベート**:
   ```bash
   # Windows
   venv\Scripts\activate
   ```

2. **アプリケーションの実行**:
   ```bash
   python -m app.app
   ```

## 開発ガイドライン

- **コードスタイル**: PEP 8 に従ってください。
- **型ヒント**: 全ての関数の引数と戻り値に型ヒントを使用してください。
- **UI 更新**:
    - `TrackContainer` を変更する場合、`_rebuild_rows` または `refresh_all_rows` が効率的に更新を処理するようにしてください。
    - コンポーネント間の通信には `Signal` を使用してください。
- **ダークモード**: アプリは `app/ui/theme.py` で定義されたカスタムダークテーマを使用しています。新しいウィジェットが暗い背景で見栄えが良いことを確認してください。

## よくあるタスク

- **新しい UI 機能の追加**: `app/ui/` を確認してください。
- **再生ロジックの変更**: `app/playback/` を確認してください。
- **データ構造の変更**: `app/core/` を確認してください。

Happy Coding!
