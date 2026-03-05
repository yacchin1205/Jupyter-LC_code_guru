# Codex Kernel Concept

1. 目的は「布教と事例共有」であり、Notebook の Code Cell に Codex への指示だけを書けることを優先する。
2. 操作モデルは `1 Kernel = 1 Codex session` とする。
3. セル実行は `codex exec` を使い、同一Kernel内では `codex exec resume <thread_id>` で会話を継続する。
4. Kernel restart は新規セッション開始として扱う。
5. 追加のマジック記法（例: `%%codex`）は採用しない。
