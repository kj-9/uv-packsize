# AGENTS.md

このファイルは、`uv-packsize`で作業するコーディングエージェント向けのプロジェクト指示である。リポジトリ全体に適用する。

## プロジェクト概要

`uv-packsize`は、`uv`を使用してPython packageとその依存関係を一時環境へインストールし、インストール後のlogical sizeをdistribution単位で分析するCLIである。

現在の実装は[`uv_packsize/cli.py`](./uv_packsize/cli.py)に集約されている。`click`でCLIを提供し、各distributionの`.dist-info/RECORD`をファイル所有権の基準としている。

長期的な目的は、単発のサイズ表ではなく、次を再現可能に扱うことである。

- packageとtransitive dependenciesのinstalled logical footprint
- 容量を占めるdistribution、ファイル種別、依存経路
- dependency変更前後のsize diff
- CIでの容量budget
- Python、platform、extras、versionなどの測定context

## 作業前に必ず読む文書

1. [`docs/roadmap.md`](./docs/roadmap.md): 目的、設計方針、Phase全体
2. [`docs/implementation-plan.md`](./docs/implementation-plan.md): 現在のタスク、状態、完了条件、検証記録
3. [`README.md`](./README.md): 現在公開されているCLI契約

実装作業では、`docs/implementation-plan.md`を進捗の単一管理先とする。GitHub Issueを通常のタスクボードとして使用しない。

## タスク進行ルール

1. 作業開始時に「現在の状態」と「次のタスク」を確認する。
2. 原則として、`in_progress`は同時に1タスクだけにする。
3. 着手時に対象タスクを`in_progress`へ変更する。
4. スコープ外の問題は黙って修正せず、「発見事項・後続候補」へ記録する。
5. 実装、テスト、文書、検証を1つの完了単位として扱う。
6. 完了条件を満たしてから`done`へ変更する。
7. 完了時に実行した検証コマンドと結果を作業記録へ追記する。
8. 次のタスクを「次のタスク」に設定する。

ユーザーが現在のタスクと異なる作業を明示的に依頼した場合は、ユーザーの依頼を優先し、計画側を現実に合わせて更新する。

## Definition of Done

詳細は[`docs/implementation-plan.md`](./docs/implementation-plan.md)を正とする。最低限、以下を満たすこと。

- 実装または文書変更が要求を満たしている。
- 変更された振る舞いに対応するテストがある。
- 関連テストと全体チェックが成功する。
- CLI契約や設定変更が文書へ反映されている。
- lock、build、release変更には専用検証がある。
- 既知の制約と未完了事項が記録されている。
- implementation planの状態と作業記録が更新されている。

## 開発コマンド

```bash
make sync       # 開発環境の同期
make test       # pytest
make ci-check   # format check、lint、typecheck、README生成整合性
make check      # README更新、format、lint、typecheck、test
make build      # wheelとsdistをbuild
uv lock --check # pyproject.tomlとuv.lockの整合性確認
```

タスクに応じて対象テストを先に実行し、完了前に全体チェックを行う。

現時点の`makefile`は`uv run --frozen`を使用しているが、Phase 1で`--locked`へ移行する計画である。移行前後の状態を混同しないこと。

## コード方針

- Pythonコードと識別子は英語を使用する。
- ユーザー向けCLIメッセージは既存の英語スタイルを維持する。
- 設計・進捗文書は日本語でよい。
- ファイル探索には`rg`または`rg --files`を優先する。
- 小規模で検証可能な変更を優先し、無関係なリファクタリングを混ぜない。
- subprocess処理、分析、集計、表示の責務を分離する方向で設計する。
- CLI関数だけでデータを組み立てず、機械可読なresult modelからtext/JSONを生成できる構造を目指す。
- 外部コマンド失敗を生のtracebackとして利用者へ見せない。
- 新しい依存ライブラリは、標準ライブラリで十分に実現できない場合だけ追加する。

## 測定上の不変条件

サイズ分析を変更するときは、以下を守る。

- `RECORD`をdistributionとinstalled filesの主要な所有権情報として扱う。
- global totalは、含有対象となるfile inventoryから導出する。
- distribution totalsの合計とglobal totalの関係を説明可能にする。
- Python interpreter、venv基礎ファイル、uv cacheをpackage sizeへ暗黙に含めない。
- logical sizeとfilesystem上のallocated sizeを混同しない。
- 1024基準の単位には`KiB`、`MiB`、`GiB`を使用する方針とする。
- platform、Python、extras、resolver条件が異なる結果を同一条件の値として扱わない。
- 欠損した`RECORD`、存在しないファイル、重複所有などを黙って正常値にしない。
- scripts、data、headersなどsite-packages外へ配置される所有ファイルを考慮する。
- 複数root packagesのshared dependencyをglobal totalで二重計上しない。

現在の実装がこれらをすべて満たしているわけではない。既存の不一致は[`docs/implementation-plan.md`](./docs/implementation-plan.md)の発見事項として管理し、Phaseに従って解消する。

## 安全性

- 任意packageのsdist build backendは第三者コードを実行し得る。
- 将来的なデフォルトはwheel-onlyを目標とする。
- buildを許可する機能を追加する場合は明示的なopt-inとし、結果にも記録する。
- private indexのcredential、token、環境変数、ローカル設定内容をログやfixtureへ保存しない。
- userやCI環境の既存Pythonへpackageを直接インストールしない。
- 一時環境または明示的なtarget/prefixだけを変更する。

## テスト方針

- unit testsではresolverやネットワークを必要としないfixtureを優先する。
- integration testsはlocal wheelsと`--find-links`で再現できる形を目標とする。
- PyPIを使うsmoke testは通常PRの必須テストから分離する。
- Linux、macOS、Windowsのpath layoutを検証する。
- error pathではexit code、利用者向けメッセージ、traceback非表示を確認する。
- JSONを追加した後はschema versionとdeterministic fieldsを検証する。
- size totalを変更する場合は、file inventoryとの一致を検証する。

## Gitとリリース

- userの既存変更を保持し、無関係な差分を戻さない。
- 明示的に依頼されない限り、commit、push、tag、release、PyPI publishを行わない。
- version、`uv.lock`、release artifact metadataは相互に一致させる。
- `--frozen`はlockの鮮度を検証しないため、CIの整合性確認には使用しない方針とする。
- release前には最低限、test、ci-check、lock check、build、artifact metadataを検証する。

## 文書と記録

- 戦略やPhase構成を変える場合は`docs/roadmap.md`を更新する。
- 作業状態、完了条件、検証結果は`docs/implementation-plan.md`を更新する。
- CLI利用方法や公開契約を変える場合は`README.md`を更新する。
- 会話や内部推論をそのまま文書へ保存せず、後から検証できる事実、判断、根拠、未解決事項だけを記録する。
- GitHub Issueを作成・更新する場合は、必ずユーザーの明示的な承認を得る。
- 関連するClosed Issueへの情報追記だけを理由に再オープンしない。
