# NII-cloud-operation Code Guru
[![Launch Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/yacchin1205/Jupyter-LC_code_guru/HEAD)

## 何ができるか
- NII-cloud-operation Organization の公開リポジトリについて、Codex に質問できる。
- 大量リポジトリでも、必要なものだけ取得して回答できる。

## ユーザー向け使い方（mybinder）
1. mybinder.org でこのリポジトリを起動する。
2. JupyterLab で `Terminal` を開く。
3. Terminal で `codex login --device-auth` を実行してログインする。
4. Terminal で `codex` を実行する。
5. 質問する。

## 前提
- 対象は公開情報のみ。
- private repository は扱わない。
- Binder 環境は一時的（セッション終了で消える）。

## 開発者向け（Catalog更新）
Catalog は事前に生成しておく。

```bash
python3 scripts/build_catalog.py --org NII-cloud-operation --out-dir catalog --limit 500
```

生成物:
- `catalog/repos.jsonl`: 公開リポジトリのメタ情報
- `catalog/tree.jsonl`: 軽量ディレクトリ情報
- `catalog/bootstrap.md`: 要約情報

## 仕組み（概要）
1. Codex が `catalog/repos.jsonl` / `catalog/tree.jsonl` から候補リポジトリを絞る。
2. 必要なリポジトリだけ `workspace/repos/` に shallow clone する。
3. 該当箇所を調べて回答する。

## Codex Kernel
Notebook の Code Cell に Codex への指示だけを書ける実装を用意している。

```bash
python3 scripts/install_codex_kernel.py
```

Jupyter で Kernel を `Codex` に切り替え、Code Cell に自然文の指示を書いて実行する。
コンセプトは `scripts/CODEX_KERNEL_CONCEPT.md` を参照。
