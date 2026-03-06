# NII-cloud-operation Code Guru

## 何ができるか
- NII-cloud-operation Organization の公開リポジトリについて、Codex に質問できる。
- 大量リポジトリでも、必要なものだけ取得して回答できる。

## 使い方
[![Launch Binder](https://binder.cs.rcos.nii.ac.jp/badge_logo.svg)](https://binder.cs.rcos.nii.ac.jp/v2/gh/yacchin1205/Jupyter-LC_code_guru/HEAD)  をクリックして環境を起動する。

> [国立情報学研究所 データ解析機能](https://support.rdm.nii.ac.jp/usermanual/DataAnalysis-01/) を利用可能なアカウントを所有している必要があります。
> なお、 `mybinder.org` の使用は推奨しません。（`codex login` で保存されうる機微情報を扱う用途は想定されていないため）。  

起動後は、以下のいずれかの方法で使用できる。

### A. JupyterLab Terminal で使う
1. JupyterLab で `Terminal` を開く。
2. `codex login --device-auth` を実行してログインする。
3. `codex` を実行する。
4. 質問する。

### B. Notebook（Codex Kernel）で使う
1. Notebook を新規作成し、Kernel を `Codex` に切り替える。
2. 必要なら最初のセルで `%%login` を実行してログインする。
3. Code Cell に自然文の指示を書いて実行する。

実行イメージは [EXAMPLE.ipynb](./EXAMPLE.ipynb) を参照すること。

## 開発者向け
### 前提
- 対象は公開情報のみ。
- private repository は扱わない。
- Binder 環境は一時的（セッション終了で消える）。

### 仕組み
1. Codex が `catalog/repos.jsonl` / `catalog/tree.jsonl` から候補リポジトリを絞る。
2. 必要なリポジトリだけ `workspace/repos/` に shallow clone する。
3. 該当箇所を調べて回答する。

### Catalog更新
Catalog は事前に生成しておく。 (リポジトリ管理者が実施)

```bash
python3 scripts/build_catalog.py --org NII-cloud-operation --out-dir catalog --limit 500
```

生成物:
- `catalog/repos.jsonl`: 公開リポジトリのメタ情報
- `catalog/tree.jsonl`: 軽量ディレクトリ情報
- `catalog/bootstrap.md`: 要約情報

### Codex Kernel
Notebook の Code Cell に Codex への指示だけを書ける実装を用意している。

```bash
python3 scripts/install_codex_kernel.py
```

Jupyter で Kernel を `Codex` に切り替え、Code Cell に自然文の指示を書いて実行する。
コンセプトは `scripts/CODEX_KERNEL_CONCEPT.md` を参照。
