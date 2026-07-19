# uv-packsize 実装計画・進捗

最終更新: 2026-07-19

この文書は、[`roadmap.md`](./roadmap.md)を実行可能なタスクへ分解し、現在の作業位置、完了条件、検証結果を一か所で追跡するための単一の管理表である。エージェントの作業規則は[`AGENTS.md`](../AGENTS.md)を参照する。

## 現在の状態

| 項目 | 状態 |
|---|---|
| 現在のPhase | Phase 1: リリース品質の回復 |
| `in_progress` | なし |
| 次のタスク | P1-08: distribution artifactの検証 |
| Phase 1進捗 | 7 / 9 完了 |
| Blocker | なし |
| 次の成果物 | wheel/sdistとartifact metadata、CLI entry pointの検証 |

## ステータス定義

各タスクは、次のいずれかの状態を取る。

| 状態 | 意味 |
|---|---|
| `todo` | 未着手。前提条件が満たされれば開始できる |
| `in_progress` | 作業中。原則として同時に1件だけにする |
| `blocked` | 外部判断、権限、前提作業などを待っている |
| `done` | 完了条件を満たし、検証結果が記録されている |

## 作業ルール

1. 作業開始前に、この文書の「現在の状態」と対象タスクを確認する。
2. 着手するタスクを`in_progress`にし、「現在の状態」を更新する。
3. タスクの範囲を超える問題を発見した場合は、既存タスクへ黙って混ぜず、後続タスクまたは「発見事項」へ記録する。
4. 関連する最小テストを先に実行し、その後に全体チェックを実行する。
5. 完了条件とDefinition of Doneを満たした場合だけ`done`にする。
6. 完了時に検証コマンドと結果を「作業記録」へ追記する。
7. 次の`todo`を「次のタスク」に設定する。

## Definition of Done

タスクは、該当する以下の条件をすべて満たしたときに完了とする。

- 要求された実装または文書変更が存在する。
- 変更された振る舞いを検証する自動テストがある。
- 既存テストが成功する。
- format、lint、typecheckが成功する。
- CLIや設定が変わった場合、READMEまたは関連文書が更新されている。
- lock、build、releaseに関係する場合、専用の整合性チェックが成功する。
- 検証コマンドと結果がこの文書に記録されている。
- 既知の制約や未完了事項が隠されずに記録されている。

通常の最終検証は次を基準とする。

```bash
make ci-check
make test
uv lock --check
```

release関連タスクでは、これにbuildとartifact検証を追加する。

## Phase概要

| Phase | 目的 | 状態 |
|---|---|---|
| Phase 0 | 測定契約とプロダクト方針の整理 | `done` |
| Phase 1 | リリース品質の回復 | `in_progress` |
| Phase 2 | 信頼できる測定エンジン | `todo` |
| Phase 3 | サイズの理由を説明する | `todo` |
| Phase 4 | CIでの継続管理 | `todo` |
| Phase 5 | project/lockと比較分析 | `todo` |
| Phase 6 | エコシステム連携 | `todo` |

詳細な目的と判断背景は[`roadmap.md`](./roadmap.md)を参照する。

## Phase 0: 測定契約とプロダクト方針

| ID | タスク | 状態 | 完了条件 |
|---|---|---|---|
| P0-01 | 現在の実装、テスト、履歴、公開状態を調査する | `done` | 実装フローと主要課題がroadmapへ記録されている |
| P0-02 | 競合と現行uv/Packaging仕様を確認する | `done` | 差別化対象と再実装しない領域がroadmapへ記録されている |
| P0-03 | プロダクトの中心目的を定義する | `done` | installed footprint、diff、budgetを中心とする方針が記録されている |
| P0-04 | 実行計画とエージェント運用規則を作成する | `done` | 本文書と[`AGENTS.md`](../AGENTS.md)が存在し、相互に参照できる |

Phase 0で定義した将来の測定契約は設計案である。P1-06では、現在の実装が提供する測定契約と既知の制約をREADMEへ記載した。Phase 2で予定する変更を現行仕様と混同しない。

## Phase 1: リリース品質の回復

| ID | タスク | 状態 | 依存 | 完了条件 |
|---|---|---|---|---|
| P1-01 | 現在のversion、lock、CI、テスト状態を基準化する | `done` | - | ベースラインと不整合が作業記録に残っている |
| P1-02 | リリース対象メタデータを更新する | `done` | P1-01 | versionが`0.1.2`、Python方針が明示され、metadata testがある |
| P1-03 | lockとローカル実行を厳格化する | `done` | P1-02 | `uv.lock`が同期し、通常チェックが`--locked`を使う |
| P1-04 | CIのlock検証とPython matrixを更新する | `done` | P1-03 | stale lockで失敗し、Python 3.10〜3.14を検証する |
| P1-05 | subprocessエラー処理を統一する | `done` | P1-01 | 無効なPythonやinstall失敗でtracebackを出さない |
| P1-06 | 測定契約と安全性をREADMEへ記載する | `done` | P1-01 | 含有範囲、単位、platform依存、sdistリスクが明記されている |
| P1-07 | Phase 1変更のテストを補強する | `done` | P1-02〜P1-06 | release metadata、lock、error pathの回帰テストがある |
| P1-08 | distribution artifactを検証する | `todo` | P1-07 | wheel/sdistがbuildでき、version、metadata、CLI entry pointが正しい |
| P1-09 | Phase 1総合検証と引き継ぎを行う | `todo` | P1-08 | 全検証が成功し、Phase 2の最初のタスクが具体化されている |

### P1-02 実施内容

完了したタスク。

予定する変更:

- `pyproject.toml`のversionを`0.1.2`へ更新する。
- Python 3.9のEOLを踏まえ、`requires-python`を`>=3.10`へ更新する。
- 対応Python versionのclassifiersを追加する。
- project metadataとCLIのversion表示を検証するテストを追加する。

注意:

- `uv.lock`の同期はP1-03で行う。
- 公開やGit tag作成は、この計画の完了には含めない。明示的な依頼がある場合だけ行う。

### P1-03 実施内容

完了したタスク。

変更:

- `uv.lock`をproject metadataと現在の依存解決結果へ同期する。
- 通常のローカルチェックを`uv run --locked`へ移行し、stale lockを拒否する。
- `make sync`は開発環境とlockを意図的に同期する入口として維持する。
- makefileのlock運用境界を検証する回帰テストを追加する。

### P1-04 実施内容

完了したタスク。

変更:

- CIのtest matrixをPython 3.10〜3.14へ更新する。
- 独立したlock jobで`uv lock --check`を実行し、stale lockを明示的に拒否する。
- CIのmatrixとlock checkを検証する回帰テストを追加する。

### P1-05 実施内容

完了したタスク。

変更:

- subprocess呼び出しを単一のuv adapterへ集約する。
- command、exit code、stdout、stderrを保持する専用例外を導入する。
- virtual environment作成とpackage installの失敗をCLI境界で利用者向けClick errorへ変換する。
- uv未検出を含む失敗でPython tracebackを表示せず、簡潔な診断をstderrへ出す。
- subprocess失敗時の公開CLI契約をREADMEへ記載する。

### P1-06 実施内容

完了したタスク。

変更:

- 現行実装の測定手順、含有範囲、除外範囲をREADMEへ記載する。
- `--bin`の集計対象とdistribution ownershipへ帰属しないことを明示する。
- site-packages外の`RECORD` path、Windows `Scripts`、`RECORD`欠損時fallback、単位表記の既知制約を記載する。
- Python、platform、extras、dependency resolutionによる結果差と、複数root packageの帰属情報がないことを明示する。
- sdist build backend実行リスク、wheel-only未実装、一時venvへ限定したinstallを安全性契約として記載する。

### P1-07 実施内容

完了したタスク。

変更:

- P1-02〜P1-06の既存test coverageをrelease metadata、lock policy、CI契約、subprocess/error pathごとに監査する。
- pyprojectとuv.lockのroot version、requires-python一致を検証する。
- uv adapterの成功、OS起動失敗、stdout fallback、診断切り詰めを検証する。
- `RECORD`欠損時にpackage本体を含めず`.dist-info`だけをfallback集計することを検証する。
- network依存の存在しないpackage testを、P1-05で追加したmock resolver failure testへ置き換える。

## Phase 2以降の入口タスク

Phase 1完了時に詳細分解する。現時点の入口は以下とする。

| ID | Phase | 入口タスク | 状態 |
|---|---|---|---|
| P2-01 | Phase 2 | `AnalysisResult`とfile inventoryのデータモデルを設計する | `todo` |
| P3-01 | Phase 3 | installed metadataからdependency graphを構築する | `todo` |
| P4-01 | Phase 4 | baseline JSONと差分ポリシーを設計する | `todo` |
| P5-01 | Phase 5 | `uv workspace metadata`の対応schemaを調査・固定する | `todo` |
| P6-01 | Phase 6 | 上流連携の費用対効果を再評価する | `todo` |

## 作業記録

### 2026-07-19: P1-07 Phase 1変更のテスト補強

状態: `done`

coverage監査:

- P1-02: project version、Python要件、classifiersと、隔離metadataによるCLI `--version` exact出力を既存テストで検証済み。
- P1-03: makefileの`--locked`境界を検証済み。追加でuv.lock root metadataとpyprojectのversion、requires-python一致を検証した。
- P1-04: CIのPython 3.10〜3.14 matrix、独立lock check、3 jobのuv version pinを検証済み。
- P1-05: adapter失敗情報、venv/install例外伝播、CLI traceback非表示、uv未検出を検証済み。追加でadapter成功、OSError変換、stdout fallback、診断3行制限、command secret非表示を検証した。
- P1-06: README本文の実装詳細を固定する脆い文字列テストは追加せず、既存のCog生成整合性とレビューで検証した。

変更:

- pyprojectとuv.lockのroot version、requires-python一致をstdlibだけで検証するテストを追加した。
- `_run_uv`が成功した`CompletedProcess`を返すことと、`OSError`をcommand、exit code 127、診断を保持する`UvCommandError`へ変換することを検証した。
- stderrが空の場合のstdout fallback、診断の3行制限、省略表示、command secret非表示を検証した。
- `RECORD`欠損時にpackage本体を含めず`.dist-info`内のfileだけを数えるfixture testを追加した。
- project version testはhard-codeを避け、CLI version testと同じ`EXPECTED_VERSION`を再利用するようにした。
- 既存の存在しないPyPI packageを使うerror testを削除した。resolver/install失敗はネットワーク不要のmock CLI testで同等以上に検証する。

検証:

```bash
uv run --locked pytest tests/test_uv_packsize.py -q -k 'lock_root or run_uv or command_failure or formats_uv_failures or missing_record'
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- P1-07の対象テスト8件は成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全23テストが成功した。
- `uv lock --check`は成功した。
- whitespace errorはなかった。

意図的に残したgap:

- wheel/sdist build artifactとentry pointの検証はP1-08で行う。
- 通常の成功経路に残るPyPI依存テストのlocal wheel fixture移行はF-004としてPhase 2で行う。
- README契約の文章表現を固定するテストは追加せず、文書レビューと生成整合性で管理する。

### 2026-07-19: P1-06 測定契約と安全性のREADME記載

状態: `done`

文書構造:

- READMEに`Measurement`を追加し、一時venvへのinstall、`RECORD`を所有権根拠とするlogical bytes集計、`.pyc`の扱いを記載した。
- デフォルトでPython interpreter、venv基礎ファイル、uv cache、site-packages外の所有ファイルを含めないことを記載した。
- `--bin`はUnix形式の`bin`にある通常ファイルを別集計し、distributionへ帰属しないことを記載した。
- `Current limitations`と`Installation safety`を分け、現在の挙動と将来の改善予定を区別した。

既知の制約:

- site-packages外のscripts/data/headersとWindows `Scripts`は現在の集計対象外。
- `RECORD`欠損時は`.dist-info`内だけをfallback集計し、不完全性を出力へ示さない。
- 1024基準の値を現行出力では`KB`/`MB`と表示しており、Phase 2で`KiB`/`MiB`へ修正予定。
- logical bytesはcompressed archive sizeやfilesystem allocated blocksではなく、hardlink等の物理共有による節約を反映しない。
- `RECORD`記載fileの欠損は黙って除外し、distribution間の重複所有をglobal totalでdeduplicateまたはwarning表示しない。
- Python、platform、extras、dependency resolutionが異なる結果は直接比較できない。
- 複数root packagesのshared dependencyは通常1環境へ1度installされるためcombined totalでは通常1度だが、direct/transitive/sharedの区別とroot別寄与を表示しない。
- 現行text出力はresolved versions、Python/platform、uv version、index/resolver条件、完全性を保存せず、再現可能な分析recordではない。
- wheel-only defaultは未実装で、direct sdist/pathや互換wheel不在などresolutionがsdistを選択した場合は第三者のbuild backendを実行し得る。
- 一時venvはinstall先の隔離であってsecurity sandboxではなく、build codeは実行user権限で外部filesystemやnetworkへ作用し得る。

検証:

```bash
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全19テストが成功した。
- `uv lock --check`は成功した。
- whitespace errorはなかった。

### 2026-07-19: P1-05 subprocessエラー処理の統一

状態: `done`

変更:

- `_run_uv`を導入し、`_create_venv`と`_install_package`のsubprocess呼び出しを集約した。
- `UvCommandError`を導入し、実行command、uv exit code、stdout、stderrを保持するようにした。
- subprocessのtext decodeをUTF-8、decode不能byteのreplacementへ固定し、stdout/stderrの欠損値を空文字へ正規化した。
- CLI境界でvenv作成失敗とinstall失敗を区別し、uv exit codeとstderr先頭3行までを含む`ClickException`へ変換した。command自体はcredential漏洩を避けるため利用者向けmessageへ含めない。
- subprocess失敗とuv未検出のCLI exit statusを1へ統一し、Python tracebackを表示しないようにした。
- adapterの情報保持、venv/installでの専用例外伝播、CLIのinvalid Python相当・resolver相当・uv未検出をネットワーク不要のunit testsで検証した。
- READMEへsubprocess失敗時のexit statusと診断表示を追記した。

利用者向けmessage:

- venv作成失敗: `Could not create the virtual environment (uv exit code N).`
- install失敗: `Could not install the requested packages (uv exit code N).`
- 続けて、credentialを含み得るcommandは表示せず、uvのstderrを最大3行表示する。

検証:

```bash
uv run --locked pytest tests/test_uv_packsize.py -q -k 'run_uv or propagates_uv_failure or formats_uv_failures or uv_not_found'
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- P1-05の対象テスト6件は成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全19テストが成功した。
- `uv lock --check`は成功した。
- whitespace errorはなかった。

後続作業:

- 通常テストに残るPyPI依存の全面的なlocal fixture移行はF-004としてPhase 2で行う。
- `--verbose`やerror taxonomyは今回追加せず、必要性を後続Phaseで検討する。

### 2026-07-19: P1-04 CIのlock検証とPython matrixの更新

状態: `done`

変更:

- CIのtest matrixからPython 3.9を除外し、Python 3.10〜3.14を明示した。
- 独立した`lock` jobを追加し、`uv lock --check`でstale lockを検出する構成にした。
- lock生成・ローカル検証に使用したuv `0.11.3`を、lock、test、lintの全jobで明示的に固定した。
- CIのtest matrixが3.10〜3.14の完全一致であることと、独立したlock jobにlock checkが存在することをstdlibだけで検証するテストを追加した。
- lock、test、lintの3 jobが同じuv version pinを持つことを回帰テストで検証した。
- publish workflowは変更せず、残っているPython 3.9〜3.13 matrixをF-006としてP1-08へ割り当てた。

検証:

```bash
uv run --locked pytest tests/test_uv_packsize.py::test_ci_checks_lock_and_supported_python_versions -q
ruby -e 'require "yaml"; YAML.safe_load(File.read(".github/workflows/ci.yml"), [], [], true)'
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- CI契約テストは成功した。
- CI workflowがYAMLとしてparseできることを確認した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全14テストが成功した。
- `uv lock --check`は成功した。
- whitespace errorはなかった。

未検証事項:

- GitHub Actions上でのworkflow実走はローカルでは未検証。次回pushまたはpull requestで確認する。

### 2026-07-19: P1-03 lockとローカル実行の厳格化

状態: `done`

変更:

- `uv.lock`を更新し、`requires-python = ">=3.10"`とproject version `0.1.2`をproject metadataへ一致させた。
- Python 3.9向けの解決分岐が不要になったため、Click 8.1.8と関連するresolution markersがlockから削除された。
- versionを固定していない開発依存`ty`は、lock再生成時点の解決結果である`0.0.61`へ更新された。
- makefileの`UV_RUN`を`uv run --frozen`から`uv run --locked`へ変更した。
- `make sync`は開発環境とlockを意図的に同期する入口として`uv sync`のまま維持した。
- 通常チェックが`--locked`を使い、`make sync`の役割が維持されることを検証するテストを追加した。

検証:

```bash
uv lock --check
uv run --locked pytest tests/test_uv_packsize.py::test_project_metadata tests/test_uv_packsize.py::test_makefile_uses_locked_uv_runs tests/test_uv_packsize.py::test_version -q
make ci-check
make test
git diff --check
```

結果:

- `uv lock --check`は成功し、project metadataとlockの同期を確認した。
- P1-03の対象テスト3件は成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて`--locked`実行で成功した。
- 全13テストが`--locked`実行で成功した。
- whitespace errorはなかった。

後続作業:

- CIでの独立した`uv lock --check`とPython 3.10〜3.14 matrixはP1-04で追加する。

### 2026-07-19: P1-02 リリース対象メタデータの更新

状態: `done`

変更:

- project versionを`0.1.2`へ更新した。
- `requires-python`を`>=3.10`へ更新した。
- Python 3 only、およびPython 3.10〜3.14のclassifiersを追加した。
- project metadataのversion、Python要件、対応version classifiersを検証するテストを追加した。
- CLIの`--version`が`uv-packsize, version 0.1.2`を表示することを、別プロセスとテスト専用の`.dist-info`を使って検証した。これにより、既存環境のstale metadataとClick callbackのversion cacheへ依存しない。

検証:

```bash
uv run --frozen pytest tests/test_uv_packsize.py -q
make ci-check
make test
git diff --check
```

結果:

- 対象テストは12件すべて成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全12テストが成功した。
- whitespace errorはなかった。

既知の未完了事項:

- `uv.lock`はP1-03の範囲であるため、このタスクでは同期していない。
- P1-02完了時点では、`uv lock --check`はstale lockにより失敗していた。P1-03で同期とローカル実行の厳格化を完了した。

### 2026-07-19: P1-01 ベースライン調査

状態: `done`

確認結果:

- `main`は`origin/main`より1コミット先行している。
- working treeには調査開始時点で未コミット変更がなかった。
- `pyproject.toml`のversionは`0.1.1`。
- `uv.lock`内のproject versionは`0.1.0a1`。
- `make ci-check`は成功した。
- `make test`は11件すべて成功した。
- ローカルのテスト実行環境はPython 3.14だった。
- `uv lock --check`は、lockfileの更新が必要として失敗した。
- `uv run --frozen`が古いlockを許容していることを確認した。
- 無効な`--python 0.0`指定では`subprocess.CalledProcessError`のtracebackが表示された。
- `requests==2.32.5 --bin`の実行は成功し、package total約2.26 MiB相当を表示した。

実行した主なコマンド:

```bash
make ci-check
make test
uv lock --check
uv run --frozen uv-packsize requests==2.32.5 --bin
uv run --frozen uv-packsize six --python 0.0
```

### 2026-07-19: 進捗管理基盤

状態: `done`

変更:

- `docs/roadmap.md`を作成した。
- `docs/implementation-plan.md`を作成した。
- ルート`AGENTS.md`にエージェント向け作業規則を作成した。
- 実装進捗はGitHub Issueではなく、本ファイルを単一の管理先とした。

検証:

```bash
git diff --check
```

結果: 成功。

## 発見事項・後続候補

新しい問題を発見した場合は、既存タスクへ無断で混ぜず、ここへ一時記録してから適切なPhaseへ割り当てる。

| ID | 発見事項 | 割り当て | 状態 |
|---|---|---|---|
| F-001 | `RECORD`のsite-packages外パスを除外しており、scripts/data/headersを完全には測定できない | Phase 2 | `todo` |
| F-002 | `--bin`がWindowsの`Scripts`を分析しない | Phase 2 | `todo` |
| F-003 | 1024基準の値を`KB/MB`と表示している | Phase 2 | `todo` |
| F-004 | 通常テストがPyPIとresolverの文言に依存している | Phase 2 | `todo` |
| F-005 | sdist build backendを暗黙に実行する可能性がある | Phase 1/2 | `todo` |
| F-006 | publish workflowのtest matrixがPython 3.9〜3.13のままで、projectの対応範囲と一致しない | P1-08 | `todo` |
