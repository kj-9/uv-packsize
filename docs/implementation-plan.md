# uv-packsize 実装計画・進捗

最終更新: 2026-08-12

この文書は、[`roadmap.md`](./roadmap.md)を実行可能なタスクへ分解し、現在の作業位置、完了条件、検証結果を一か所で追跡するための単一の管理表である。エージェントの作業規則は[`AGENTS.md`](../AGENTS.md)を参照する。

## 現在の状態

| 項目 | 状態 |
|---|---|
| 現在のPhase | Follow-up: Node 24 Actions update（local `done`） |
| `in_progress` | なし |
| 次のタスク | push後にCIとPagesの実run、Node 20 annotation消滅を確認する |
| Phase 1進捗 | 9 / 9 完了（Phase 1 `done`） |
| Phase 2進捗 | 12 / 12タスク完了（Phase 2 `done`） |
| Blocker | なし。P5-03cは公開`uv sync`経路をlocal-wheelで固定して進める。local root packageの測定は初期対象外。 |
| Phase 6進捗 | 3 / 3 完了（Phase 6 `done`） |
| 次の成果物 | 上流Issue草案（ローカルのみ。投稿には明示承認が必要） |
| 安定版リリース準備 | `0.2.0`へversion/classifierを更新済み。MkDocs移行とPages deployの確認後に公開する。 |

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
| Phase 1 | リリース品質の回復 | `done` |
| Phase 2 | 信頼できる測定エンジン | `done` |
| Phase 3 | サイズの理由を説明する | `done` |
| Phase 4 | CIでの継続管理 | `done` |
| Phase 5 | project/lockと比較分析 | `done` |
| Phase 6 | エコシステム連携 | `done` |

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
| P1-08 | distribution artifactを検証する | `done` | P1-07 | wheel/sdistがbuildでき、version、metadata、CLI entry pointが正しい |
| P1-09 | Phase 1総合検証と引き継ぎを行う | `done` | P1-08 | 全検証が成功し、Phase 2の最初のタスクが具体化されている |

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

### P1-08 実施内容

完了したタスク。

変更:

- `uv build --no-sources`でwheelとsdistをbuildする。
- archiveを展開せずmetadata、critical files、entry point、安全なsdist構造を検証するstdlib scriptを追加する。
- buildとartifact検証を再実行可能な`make verify-build`へまとめる。
- publish対象inventoryに期待するwheelとsdist以外があれば、自動削除せず明示的に失敗する。
- built wheelをworkspace外の一時directoryからisolated実行し、console entry pointのversionを検証する。
- publish workflowのPython matrix、uv pinをCIと揃え、artifact検証後だけpublish stepへ進む構成にする。

### P1-09 実施内容

完了したタスク。

変更:

- P1-01〜P1-08の完了条件と成果物を総合監査する。
- lock、CI checks、全テスト、artifact、CLI version、実error pathを再検証する。
- Phase 1の既知制約をPhase 2へ引き継ぎ、P2-01を実行可能な単位へ具体化する。

## Phase 2以降の入口タスク

Phase 1完了時に詳細分解する。現時点の入口は以下とする。

| ID | Phase | 入口タスク | 状態 |
|---|---|---|---|
| P2-01 | Phase 2 | `AnalysisResult`とfile inventoryのデータモデルを設計する | `done` |
| P2-02a | Phase 2 | RECORD path resolverとsingle-distribution collectorを実装する | `done` |
| P2-02b | Phase 2 | 全distribution scanと明示的なsupplemental discoveryを実装する | `done` |
| P2-03 | Phase 2 | installed environmentの測定contextとinventoryを`AnalysisResult`へ接続する | `done` |
| P2-04a | Phase 2 | temporary venvから測定contextとinventory layoutを検出するadapterを実装する | `done` |
| P2-04b1 | Phase 2 | `AnalysisResult`のpure text rendererを実装する | `done` |
| P2-04b2 | Phase 2 | CLIを新測定engineとrendererへ接続し、公開text契約を移行する | `done` |
| P2-05a | Phase 2 | versioned JSON schemaとpure deterministic JSON serializerを実装する | `done` |
| P2-05b | Phase 2 | CLI JSON出力、README契約、error/exit behaviorを接続する | `done` |
| P2-06a | Phase 2 | local wheelによる実install integrationを追加する | `done` |
| P2-06b | Phase 2 | Linux、macOS、Windowsのcross-platform layout golden coverageを追加する | `done` |
| P2-07 | Phase 2 | wheel-onlyをデフォルトにし、build許可を明示opt-inにする | `done` |
| P3-01a | Phase 3 | installed metadata dependency graphのpure coreを実装する | `done` |
| P3-01b | Phase 3 | installed Core Metadata adapterをgraph coreへ接続する | `done` |
| P3-02a | Phase 3 | dependency path/explanationのpure immutable resultを実装する | `done` |
| P3-02b1 | Phase 3 | `--explain` のpure text presentationを実装する | `done` |
| P3-02b2 | Phase 3 | `--explain` CLI/README契約を接続する | `done` |
| P3-03a | Phase 3 | global dedupeを保つpure footprint aggregationを実装する | `done` |
| P3-03b | Phase 3 | footprint resultのpure text presentationを実装する | `done` |
| P3-03c | Phase 3 | footprint presentationをCLI/README契約へ接続する | `done` |
| P3-04a1 | Phase 3 | existing-prefix context modelと既存schema v1互換境界を実装する | `done` |
| P3-04a2 | Phase 3 | existing-prefix用JSON schema v2を設計・実装する | `done` |
| P3-04b | Phase 3 | existing prefixのlayout/context discovery adapterを実装する | `done` |
| P3-04c1 | Phase 3 | prefix CLI core/unit契約を接続する | `done` |
| P3-04c2 | Phase 3 | prefix README契約とlocal end-to-end検証を接続する | `done` |
| P3-05a | Phase 3 | root set単位の純粋なnon-split byte aggregateを実装する | `done` |
| P3-05b | Phase 3 | root contribution resultのpure text presentationを実装する | `done` |
| P3-05c | Phase 3 | root contributionをCLI/README/local integrationへ接続する | `done` |
| P4-01a | Phase 4 | baseline JSON/diff policyの契約とmodelを設計する | `done` |
| P4-01b | Phase 4 | baseline間のpure diff modelを実装する | `done` |
| P4-02a | Phase 4 | diff text rendererをCLI未接続で実装する | `done` |
| P4-02b1 | Phase 4 | current `AnalysisResult`からsafe baseline comparison projectionを実装する | `done` |
| P4-02b2 | Phase 4 | compare CLI/read boundaryを実装する | `done` |
| P4-03 | Phase 4 | diff JSON/baseline write contractを分離して設計する | `done` |
| P4-03a | Phase 4 | pure `comparison-result-v1` JSON schema/rendererを実装する | `done` |
| P4-03b | Phase 4 | `--comparison-json` CLI/public contractを接続する | `done` |
| P4-03c | Phase 4 | fresh baselineのpure render/atomic writerを実装する | `done` |
| P4-03d | Phase 4 | `--write-baseline` CLI/README/local E2Eを接続する | `done` |
| P4-04a | Phase 4 | budget policyのpure domain modelを設計・実装する | `done` |
| P4-04b | Phase 4 | budget text/result presentation contractをpureに設計・実装する | `done` |
| P4-04c | Phase 4 | budget policy inputのpure parser/normalizer contractを設計・実装する | `done` |
| P4-04d | Phase 4 | pyproject policy source resolution/file I/O contractを設計・実装する | `done` |
| P4-04e | Phase 4 | CLI policy input/precedence contractを設計する | `done` |
| P4-04f | Phase 4 | CLI policy input/precedence contractを実装する | `done` |
| P5-01 | Phase 5 | `uv workspace metadata`の対応schemaを調査・固定する | `done` |
| P5-02 | Phase 5 | project/lock analysis input/context contractを設計する | `done` |
| P5-03a | Phase 5 | project/lock context、schema、baseline/comparison projectionをpureに実装する | `done` |
| P5-03b | Phase 5 | allowlistしたexplicit project/lock readerを実装する | `done` |
| P5-03c1 | Phase 5 | validated project/lock snapshotをtemporary stagingと`uv sync`へ接続するinstaller bridgeを実装する | `done` |
| P5-03c2 | Phase 5 | project/lock CLI option、exit/stdout boundary、baseline/comparison/budget接続を実装する | `done` |
| P5-03c3 | Phase 5 | local-wheel E2E、README、全体回帰でproject/lock公開契約を完了する | `done` |
| P6-01 | Phase 6 | 上流連携の費用対効果を再評価する | `done` |
| P6-02 | Phase 6 | 既存CLIを使う最小GitHub Actions workflow契約を公開する | `done` |
| P6-03 | Phase 6 | provenance要件を上流issue草案として整理する | `done` |

### P2-01: AnalysisResultとfile inventoryのデータモデル設計

目的:

- installer、inventory収集、集計、rendererを分離するため、測定結果の内部表現と集計不変条件をコードとunit testsで確立する。

責務:

- `ResolutionContext`: 入力requirements、Python、platform、extras、index identity、resolver条件、明示的な`BuildPolicy`、bytecode条件など、結果比較に必要な解決contextを保持する。subprocess実行は担当しない。
- `FileEntry`: 測定prefixを基準とする表示用path、global dedupe用`canonical_identity`、logical bytes、file category、`FileOrigin`、symlink targetを保持する。sizeは非負とし、所有distribution fieldは持たない。`FileOrigin`は`RECORD`そのもの、RECORD entryから生成されたfile、authoritative metadata欠落時のfallback、明示的な補助scanによるdiscoveryを区別する。
- `DistributionResult`: distributionの正規化nameとresolved version、所有する`FileEntry`、distribution単位のtyped warning/completenessを保持する。FileEntry ownershipの唯一のsource of truthはこのcontainer関係とし、distribution totalはfile inventoryから導出して独立した可変値として二重管理しない。
- `AnalysisResult`: `ResolutionContext`、全distribution、globalのtyped warning/completenessを保持する。global totalは含有対象の一意なfile inventoryから導出し、重複所有はimmutableな`DuplicateOwnership` relationでも説明する。
- warningはfree textではなく、`WarningCode`等のenum/codeと対象identityを持つstructured valueで表す。completenessもboolではなく`complete`/`incomplete`等のenumとし、warning collectionは重複を除いたdeterministicなtuple/orderで保持する。

不変条件:

- 各distribution totalは、そのdistributionに含まれる`FileEntry.logical_bytes`の合計と一致する。
- `FileEntry.path`と`canonical_identity`は、実際に数えるfileについてcollectorが生成する測定prefix相対のlexical installed pathとする。`/`へseparatorを統一し、absolute path、空component、`.`、`..`、backslash、NULを許可しない。`canonical_identity`には対象platformのcase ruleも適用する。同じidentityはglobal totalで同じfileとして扱い、symlink解決先はidentityへ混ぜず別の`symlink_target` fieldに保持する。
- global totalは`canonical_identity`で一意化した含有inventoryから導出し、複数root packageや重複所有で黙って二重計上しない。
- distribution totalsの合計とglobal totalが異なり得る場合は、shared/duplicate ownershipとしてモデル上説明でき、warningまたは明示的な関係を保持する。
- 異なるdistributionが同じ`canonical_identity`を所有する場合、logical bytes、category、symlink targetが一致しなければ矛盾したinventoryとして拒否する。
- missing `RECORD`、存在しないfile、重複所有などの不完全性を正常値へ潰さず、completenessとwarningで表現できる。
- interpreter、venv基礎file、uv cacheは暗黙にinventoryへ追加しない。

スコープ境界:

- P2-01ではmodel moduleとnetwork不要unit testsを追加する。既存CLIの集計処理への接続、実filesystem inventory収集、prefix外path対応は行わない。
- prefix-relative lexical path化、platformごとのcase/path normalization、symlink targetの読取と`canonical_identity`生成はinventory collectorの責務とする。P2-01のmodelはcollectorから供給された値を検証・比較するだけで、filesystemへ問い合わせない。
- JSON schema、JSON/text renderer、公開CLI optionはP2-01では実装しない。model fieldは将来deterministic serializationできる値に限定し、renderer接続は後続taskとして分解する。
- wheel-only installer、local wheel integration fixture、`KiB`/`MiB`表示変更も後続taskとする。

完了条件:

- 4つのmodelの責務とfieldが型として実装され、可変な集計値を重複保持しない。
- distribution total、global total、shared/duplicate ownership、不完全resultの関係をunit testsで説明できる。
- 異なるdistributionに同じ`canonical_identity`を持つFileEntryを置くpure fixtureで、distribution totalsには各ownership分が現れ、global totalでは一度だけ数えることを検証する。
- negative sizeや不正なidentityなど、モデル単体で防げるinvalid stateを拒否する。
- warning code、対象identity、completenessがtyped valueで表現され、warning tupleのdedupeとorderが入力順に依存せずdeterministicであることをunit testsで検証する。
- modelはfrozen、slots、keyword-onlyとし、collectionをtupleへ防御的に変換して深いimmutabilityとhashabilityを保つ。file、distribution、warningの入力順が結果の等価性へ影響しない。
- testsは一時的なPython objectだけで構築し、uv、resolver、network、実package installを必要としない。
- 既存CLIの出力と公開契約を変更せず、`make ci-check`、`make test`、`uv lock --check`が成功する。

Phase 1からの引き継ぎ:

- release metadataはversion `0.1.2`、Python 3.10〜3.14、uv `0.11.3`で固定・検証されている。
- subprocess errorはClick errorへ正規化され、READMEは現行測定契約とsdist実行リスクを明記している。
- wheel/sdist metadata、archive安全性、installed entry pointは`make verify-build`とpublish gateで検証される。
- F-001〜F-003はinventoryと表示、F-004はlocal fixture、F-005はwheel-only installerの後続設計へ引き継ぐ。
- GitHub Actions上のworkflow実走、release、tag、PyPI publishは未実施である。

### P2-02: RECORDを基準とするfilesystem inventory collector

目的:

- temporary environmentのinstalled metadataとfilesystemを読み、P2-01のmodel不変条件を満たす`DistributionResult`群へ変換する。

分割:

- P2-02aはhost非依存のRECORD path resolver、strict CSV parse、single-distribution収集を完了単位とする。
- P2-02bは全distribution scan、複数site-packages、明示的なsupplemental scanによる`DISCOVERED` originを扱う。

責務と境界:

- 測定prefix、site-packages location、対象platformのpath/case ruleを明示的な入力として受け取り、既存Python環境やuv cacheへ触れない。
- `.dist-info/RECORD`をCSVとして読み、relative/absolute RECORD pathを安全に測定prefix内のlexical installed pathへ変換する。prefix外pathや不正pathを黙って含めない。
- site-packages外でもprefix内に所有されるscripts、data、headersをdistributionへ帰属させ、Windows `Scripts` layoutもfixtureで扱う。
- fileのlogical bytes、category、`FileOrigin`、symlink targetを収集する。symlinkはfinal pathをfollowせず`lstat().st_size`でlink entry自身のlogical bytesを数え、`readlink`のraw target textを別fieldへ保持する。intermediate symlinkがprefix外へ出るpathは収集しない。hardlinkはinodeでdedupeせずlexical installed pathごとに数える。
- missing RECORD、missing file、同一RECORD内のduplicate entryをtyped warningへ変換する。duplicate RECORD entryは`WarningCode.DUPLICATE_RECORD_ENTRY`を使用し、collector内で一意化してmodelのintra-distribution identity制約を守る。
- origin優先順位は`RECORD` > `GENERATED` > `FALLBACK` > `DISCOVERED`とする。明示的なRECORD entryはgenerated判定より優先し、RECORDがない場合だけ当該dist-info subtreeのregular file/final symlinkを`FALLBACK`とする。`DISCOVERED`はP2-02bの明示的な補助scanだけで使用する。
- `AnalysisResult`へのcontext接続、既存CLI/rendererの置換、JSON、dependency graph、installer policy変更は行わない。

完了条件:

- network不要のtemporary filesystem fixturesだけで、POSIX/Windowsの代表layout、prefix内のsite-packages外file、missing RECORD/file、duplicate RECORD entry、generated bytecode、fallback、symlinkを検証する。
- path escape、absolute/relative RECORD path、separator/case normalizationの境界がテストされ、collector出力がP2-01 modelへ追加補正なしで渡せる。
- distribution totalが収集したinventoryと一致し、warning/completenessが欠損やmetadata異常を保持する。
- 実filesystemやplatform依存部分を小さいadapter境界へ閉じ込め、platform layoutの大半をpure fixtureで検証できる。
- 既存CLIの出力と公開契約を変更せず、対象テスト、`make ci-check`、`make test`、`uv lock --check`が成功する。

P2-02aで固定した契約:

- physical filesystem pathとtarget logical pathを`InventoryLayout`で分離し、`PathFlavor`と`CaseRule`を明示する。POSIX、Windows drive、UNCをhostのpath semanticsへ依存せず解釈する。
- relative RECORD pathは検証済み`dist_info_dir.parent`を基準にnormalizeし、component単位でlogical prefix containmentを検証する。Windowsのrooted/drive-relative path、ADS、reserved device name、invalid character、末尾dot/spaceはinvalidとする。
- RECORDはstrict UTF-8 CSV、exact 3 columns、非空path、hashの`algorithm=urlsafe-base64-nopad`形、sizeの空または非負ASCII base-10整数を要求する。
- invalid RECORD/path、prefix外path、missing file、duplicate entry、unsupported file type、filesystem/layout errorをtyped warningとして保持する。distribution-target warningは同一codeごとにdedupeされるため、現段階では複数のinvalid/outside raw path詳細を保持しない。
- `RECORD` entryを最優先し、未記載の対応bytecodeだけ`GENERATED`、RECORD欠落時のdist-info subtreeだけ`FALLBACK`とする。real directoryはfallback ownershipに含めず、その配下fileを収集する。

P2-02bで固定した契約:

- compatibleな複数site-packagesのdirect-child `.dist-info`を、layout入力順とfilesystem列挙順に依存せず走査する。resolved physical siteのalias、logical siteの重複、incompatibleなprefix/flavor/case rule、正規化後のdistribution name/version衝突はtyped scan errorとして拒否する。
- supplemental ownershipは正規化したdistribution nameとexact versionをowner keyとし、測定prefix相対の明示的なexact file pathだけを`DISCOVERED`へ追加する。directoryの再帰scanや暗黙の隣接file追加は行わない。同一指定とcase aliasはset semanticsで一意化し、入力順に依存しない。
- ownership優先順位は`RECORD` > `GENERATED` > `FALLBACK` > `DISCOVERED`とし、RECORDが主張したmissing/unsupported/filesystem-error pathもsupplementalで再解釈しない。異なるownerによる同じcanonical identityはfile signatureが一致する場合だけ許可する。
- supplementalのinvalid raw pathは結果やerror targetへ転記せず、解決後のmissing/special/filesystem errorだけcanonical identityで報告する。final symlinkはprefix外targetでもfollowせずlink自身を収集し、intermediate symlink escapeは拒否する。
- valid METADATAをdistribution identityの第一情報源とする。missing/invalid METADATAでdirname fallbackできる場合はtyped incomplete warningを保持し、fallback不能ならinvalid dist-infoとして拒否する。空RECORDはinvalid、RECORD self-entry欠落はtyped incomplete warningとする。

P2-03へ送る事項:

- installer/resolverが確定したrequirements、Python、platform、architecture、uv version、build policy、bytecode条件から`ResolutionContext`を構築し、`collect_distributions`の結果と合わせて`AnalysisResult`を返すorchestration boundaryを追加する。
- P2-03では既存text renderer/CLIの置換を混ぜず、network不要のinstalled-environment fixtureでcontextとinventoryの接続、global dedupe、warning/completeness伝播を検証する。

P2-03で固定した契約:

- `analyze_installed_environment`はcallerが確定済みの`ResolutionContext`、1件以上の`InventoryLayout`、任意の`SupplementalOwnership`を受け、`collect_distributions`を1回だけ呼び、その戻り値から`AnalysisResult`を構築するthin orchestration boundaryとする。
- target path semanticsは比較可能性とcanonical identity/global dedupeへ影響するため、`PathFlavor`と`CaseRule`を`ResolutionContext`の必須typed fieldとする。全layoutとの不一致はfilesystem scan前にsanitized targetを持つtyped `AnalysisContextError`として拒否する。free-formなplatform/architecture/Python文字列からpath/case ruleを推測しない。
- `ResolutionContext`はコピーや補正をせず結果へ同一objectとして保持する。resolved distribution version、file inventory、distribution warning/completenessはcollector/modelから導出し、totalやwarningをorchestration層で二重管理しない。
- `compile_bytecode`等のcontext fieldはcallerがinstalled environmentを正確に記述する責任を持つ。実在filesystem inventoryをcontextでfilterせず、`compile_bytecode=False`でも実在するgenerated fileは観測結果として保持する。
- inventory scan、supplemental、file signature conflictのtyped errorはcatch/変換せず、そのtype/code/targetを上位へ伝播する。CLI、installer、subprocess、renderer、JSON、networkは接続しない。

P2-04へ送る事項:

- 既存temporary venv作成/install flowから、実際のPython、platform、architecture、uv version、build/bytecode条件、path flavor/case ruleを含む`ResolutionContext`と`InventoryLayout`を構築し、新しいanalysis boundaryへ接続する。
- 現行text出力の公開互換性を維持しながら集計sourceを`AnalysisResult`へ切り替え、subprocess failureの既存Click error契約を保持する。CLI接続に必要なlocal installed fixtureとrenderer境界はP2-04で具体化する。

### P2-04a: temporary venv environment discovery adapter

目的:

- temporary venv の実際の interpreter と sysconfig から、inventory に渡せる immutable な`ResolutionContext`と`InventoryLayout`群を構築する。

固定した契約:

- venv Pythonを一度だけ`-I`で実行し、`sys.prefix`、`sys.executable`、`major.minor.micro`形式の完全な数値Python version、sysconfig platform、machine、`os.name`、purelib、platlibをJSONとして取得する。callerが渡すrequirements、uv version、build policy、bytecode、extras、index identity、resolution strategyは推測・置換しない。
- prefix/base prefix/executableを照合してtemporary venv identityを検証する。purelib/platlibはprefix内であることを確認してから、それぞれのsite-packages directoryでcase sensitivityを明示probeする。
- reported/invoked interpreterは各prefix下のlexical containmentを先に確認し、その後`samefile`で同一実体か照合する。venv内hardlink aliasは許容するが、venv外からのaliasは拒否する。probe stdoutはstrict UTF-8でdecodeし、破損byte列はtyped invalid-probe errorにする。
- physical pathとtarget logical pathを分離して`InventoryLayout`を構築し、同一のcompatible layoutはdedupeする。payload builderをfilesystem/subprocessから分離し、POSIX host上でもWindows logical layoutをunit testできる。
- discovery failureはraw path、requirements、subprocess stdout/stderrを含まないtyped/sanitized errorで返す。CLI、uv command/version query、inventory analysis、rendererへの接続はP2-04bの責務とする。

### P2-04b1: `AnalysisResult` pure text renderer

目的:

- immutableな`AnalysisResult`だけを入力に、filesystem、subprocess、network、Click出力へ依存しないdeterministicな完全text reportを生成する。

固定した契約:

- distribution rowは`DistributionResult.files`の`FileEntry` inventoryから導出し、defaultでは全categoryを含める。rowはlogical bytesの降順、同値はnormalized distribution nameの昇順で並べる。
- reportの最終`Total size`はdistribution rowのsumではなく、`AnalysisResult.total_logical_bytes`を表示する。重複所有のためrow sumとglobal totalが異なる場合は、その理由を安全でdeterministicなsummaryとして説明する。
- size unitは1024基準で`0 B`、`KiB`、`MiB`、`GiB`を使用する。
- `show_scripts=True`ではpackage table/subtotalから`FileCategory.SCRIPT`を除外し、canonical identityでglobal dedupeしたscript filesだけを`Binaries in .venv/bin` tableへ出す。path labelはmeasurement prefix相対pathを使い、同名scriptの衝突を避ける。最終global totalを二重計上しない。
- incomplete resultはraw pathやunsafe diagnosticsを出さず、typed warning codeごとの件数をdeterministicに要約する。empty resultもtable/footer/totalを含む安定したreportを返す。
- CLI接続、progress lifecycle、uv execution、environment discovery、公開README契約の変更はP2-04b2の責務とする。

### P2-05: versioned JSON schemaとdeterministic JSON出力

目的:

- `AnalysisResult`からschema versionを含む機械可読なJSONを生成し、同一の入力・環境では明示的な可変項目を除いて安定した結果を返す。

完了条件:

- context、resolved distributions、file inventory、warnings/completeness、global totalをversioned schemaで表現する。
- JSON rendererと公開CLI出力を同じresult modelに接続し、key/order/optional fieldのdeterminismをgolden testで検証する。
- schema contract、JSON error/exit behavior、比較に必要なmeasurement contextをREADMEへ記載する。
- requirementはcredential-bearing URLをrawのまま公開JSONへ出さないrepresentationを定義し、serialization testで非漏えいを検証する。

分割:

- P2-05aは`AnalysisResult`だけを受けるpure serializer、committed schema v1、golden test、安全なrequirement/index representationを完了単位とする。CLI、README、exit behaviorは変更しない。
- P2-05bはCLIのJSON option、stdout/error/exit behavior、READMEの公開契約を接続する。P2-05aのschema v1を変更せず利用する。

P2-05aで固定するschema v1契約:

- top-level fieldは`schema_version`、`measurement`、`context`、`distributions`、`warnings`、`duplicate_ownerships`、`completeness`、`totals`の順で必ず存在する。v1のmajor versionは互換性境界であり、破壊的変更はschema versionを上げる。
- requirementはraw text、specifier、marker、URL、credential、digestを含めず、入力順を表す安全なprojectionだけを出力する。index identityはASCII symbolic aliasだけをmodelで許可する。
- file inventoryはpath/canonical identity、logical bytes、category、origin、symlink有無だけを出力し、raw symlink targetは出力しない。

### P2-06: local wheel integration fixtureとcross-platform golden coverage

目的:

- 通常の成功系testをpackage indexから分離し、local wheel installationとtarget layoutのgolden fixtureでPhase 2の測定契約を継続検証する。

分割:

- P2-06aはstdlibだけで生成するdeterministicなlocal universal wheelを用い、実際の`uv` resolver/installからtext/JSON reportまでをnetworkなしで検証する。
- P2-06bはP2-06aのwheel fixtureを再利用し、Linux、macOS、Windowsのscripts/data/headersを含むtarget layout golden testを追加する。host platformに依存するinstall実行はP2-06aだけの責務とする。

P2-06aの完了条件:

- test-owned wheelとlocal `--find-links`を用い、resolver/installからJSON/text reportまでnetworkなしで検証する。
- shared dependencyを持つ複数root package、entry point script、wheel `.data` のscripts/data/headersを実install結果で検証する。
- F-004の通常testにおけるPyPI/package index依存を、実成功経路について解消する。

P2-06bの完了条件:

- Linux、macOS、Windowsのscripts/data/headersを含むlayout golden testを追加し、PyPI smoke testは通常test suiteから分離する。

### P2-07: wheel-only installer safety

目的:

- package-size analysisが第三者sdist build backendを暗黙に実行しないよう、wheel-onlyを既定にし、build許可を明示opt-inとして結果contextへ残す。

完了条件:

- installerはwheel-onlyを既定とし、sdistのみの候補を安全な利用者向けエラーとして扱う。
- buildを許可するoptionは明示的で、JSON contextのbuild policyとREADMEの安全性契約が一致する。
- local wheel integrationとsdist拒否の回帰testがnetworkなしで成功する。

### P3-01a: installed metadata dependency graphのpure core

目的:

- installed file inventoryの測定値を変更せず、PEP 508 Core Metadataから依存関係とroot attributionを再現可能に組み立てる純粋な基盤を確立する。

変更:

- `packaging.Requirement`を使用し、root requirementと`Requires-Dist`をparseする。PEP 508 markerを標準ライブラリで正しくparse/evaluateできないため、runtime dependencyに`packaging`を追加する。
- `AnalysisResult`、明示的な完全な`MarkerEnvironment`、adapterが供給する`InstalledDistributionMetadata`から、filesystem・subprocess・host environmentへアクセスせずgraphを構築する。
- rootはsafe parsed nameで照合し、`recognized`、`inactive`、`version-mismatch`、`unmatched`、`unidentifiable`を区別する。marker評価不能なrootは名前を保持せず、root inputを対象とするtyped warningでincompleteとする。named direct referenceはinstalled nameが一致すればversionを検証せずrootとして認識し、specifierのpre-release判定はPackaging既定policyに従う。
- edgeはactive markerかつinstalled targetの場合だけ生成する。markerは常に`extra=""`と選択された全extraで評価し、root入力に明示されたextrasだけを伝播の初期値とする。edgeはrequested extrasを保持し、同じsource/targetのactive requirementはextrasの和へcoalesceする。selected extrasはdependency requirementからtargetへ伝播し、markerのactive edgeが増えなくなるまで固定点で評価する。
- nodeはrootごとのBFS reachabilityにより`root`、`direct`、`transitive`、`unattributed`へ分類する。2つ以上のrecognized rootから到達できるnodeをsharedとし、cycleを安全に扱う。
- graph warning/completenessはsize analysisの`AnalysisWarning`と別のimmutable typed modelにする。warningにはnormalized distribution nameまたはroot input indexだけを保持し、raw requirement、URL、marker、parser diagnosticは保持・表示しない。

完了条件:

- input順序に依存しないimmutable graph、edge、root status、warningがunit testで確認できる。
- explicit target marker environment、extras propagation、cycle、missing metadata/target、不正metadata、root status、安全なsecret非漏洩をnetwork不要のtestで確認できる。
- `AnalysisResult`とschema v1 serializerの既存byte列を変更しない。

スコープ境界・既知の制約:

- P3-01aはCore Metadataを読むadapter、CLI、text/JSON renderer、schema v1へのgraph追加を実装しない。次のP3-01bでinstalled environmentからmetadataを安全に供給する境界を決める。
- callerはhostの値を推測せず、全standard marker variableを持つtarget `MarkerEnvironment`を明示して渡す。metadataにないinstalled distribution、version不一致、active missing target、不正requirementはgraphを`incomplete`にする。
- graphはsize totalを持たない。self/transitive byte attribution、表示、既存prefix mode、shared contributionの説明は後続P3 taskで扱う。

### P3-01b: installed Core Metadata adapterをgraph coreへ接続する

目的:

- 実際に測定したinstalled environmentのCore Metadataだけを安全に読み、P3-01aのpure graphへ渡す境界を確立する。

変更:

- environment discoveryは、対象venvを1回だけprobeして完全な`MarkerEnvironment`を取得する。`implementation_*`、platform、Python versionを含むmarker値とpre-release semanticsは、実行中hostから推測せずtarget interpreterの値を使用する。
- `InstalledEnvironment`はresolution context、inventory layout、target marker environmentを束ね、adapterはこのenvironmentにboundする。analysis contextとの不一致は、context値やpathを露出しないtyped errorとして拒否する。
- adapterはvalidated inventory layoutのsite-packages直下にある非symlinkの`.dist-info` directoryだけを読む。`METADATA`も非symlink regular fileとして読み、Core Metadata version `1.0`、`1.1`、`1.2`、`2.1`〜`2.5`だけを受理する。
- metadata欠損・不正・重複・name/version mismatchは、raw metadata、path、parser diagnosticを保持しないtyped metadata stateへ変換し、graphのsafe warning/completenessへ反映する。

スコープ境界・既知の制約:

- graphは内部modelのままとし、既存text出力、JSON schema v1、公開CLI契約は変更しない。Core Metadata graphはinstalled metadataによる説明情報であり、resolver provenanceを主張するものではない。
- dependency pathとdirect/transitive/shared attributionの表示可能なresultへの接続はP3-02で扱う。

### P3-02a: dependency path/explanationのpure immutable result

目的:

- 既存のmeasurementおよびdependency graphを変更せず、recognized root inputごとの到達性と依存経路を再現可能な説明モデルへ合成する。

変更:

- `DependencyPath`、`DistributionAttribution`、`ExplainedAnalysisResult`と`explain_dependency_paths()`をpure moduleとして追加する。
- recognized root inputは同名の重複入力もinput index単位で保持する。一方、既存graph nodeの`is_shared`は引き続き異なるroot distribution名の数だけで決まる。
- 各rootからlexical orderのoutgoing edgeをBFSし、cycle-safeなsimple shortest pathを得る。canonical pathは`(edge_count, root_input_index, path_node_names)`で選び、root自身のzero-hop pathを優先する。
- analysisとgraphのdistribution name/version集合、root input index、recognized root名、edge/reachabilityから再計算したnode kind/root names/sharedを検証し、手作りまたは不整合なgraph/pathを安全な`ValueError`で拒否する。
- inventoryとgraphのcompletenessを別々に公開し、overall completenessは両方を合成する。byte totals、root別byte attribution、text/JSON renderer、CLIは変更しない。

完了条件:

- cycle、lexical tie、multi-root shared、同名root inputの重複、rootかつdependency、unattributed node、component completeness、mismatch/malformed graph/path、permutation/immutabilityをnetworkなしのunit testで確認する。
- schema v1 serializerの出力bytesが変わらず、build artifactに新moduleが含まれる。

### P3-02b: `--explain` text表示をpure resultへ接続する

目的:

- P3-02aの説明モデルを既存CLIのopt-in text presentationへ安全に接続する。

スコープ境界:

- public text契約、CLI option、rendererの設計とテストはこのtaskで扱う。schema v1 JSONは互換境界として変更しない。

分割:

- P3-02b1では、`ExplainedAnalysisResult`だけを入力に、通常のtext reportをbyte-identical prefixとして保ったpure explanation rendererを実装する。root inputごとのpathを表示できるよう、説明モデルにはroot inputごとのshortest path集合を保持する。CLI、README、JSON schemaは変更しない。
- P3-02b2では、installed environmentからmetadata graph、説明result、CLI error mappingまでのadapter境界と`--explain` public contractを接続する。`--json --explain`のv1 JSON互換性とend-to-end local wheel coverageはこのtaskで検証する。

### 2026-07-31: P3-02b1 pure explanation presentation

状態: `done`

実装:

- `DistributionAttribution`は、canonical pathに加えてroot inputごとのdeterministic shortest path集合をimmutableに保持し、root input indexes、終端node、canonical pathとの整合を検証するようにした。同名のroot inputも別pathとして残る。
- `uv_packsize/explanation.py`に、既存`render_analysis_report()`の結果をbyte-identical prefixにし、Requested Roots、Dependency Attribution、Dependency Pathsを後置するpure rendererを追加した。path sectionはroot自身のzero-hop pathを表示せず、recognized root inputと到達nodeごとに1本だけをdeterministicに表示する。
- dependency graphがincompleteの場合は、warning targetやraw metadata/requirement/diagnosticを出さず、warning codeと件数だけをsanitized summaryとして表示する。inventoryのincomplete warningは既存prefixの意味を維持し、graph completenessとは混同しない。
- renderer、path model、cycle/shared/duplicate root/unattributed/sanitized warning/prefix不変のunit testを追加し、artifact verifierは新renderer moduleのwheel/sdist含有を確認する。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_dependency_paths.py tests/test_explanation.py tests/test_render.py` — 成功（33 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（374 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make verify-build` — explanation rendererを含むwheel/sdist、artifact metadata、installed entry pointを検証して成功。

引き継ぎ:

- 次のタスクはP3-02b2とする。`build_installed_dependency_graph()`と`explain_dependency_paths()`のcomposition、CLI error mapping、`--explain` text-only option、README、`--json --explain`のv1 JSON不変、local wheel end-to-end coverageを扱う。

### 2026-07-31: P3-02b2 `--explain` public CLI/README contract

状態: `done`

実装:

- `--explain`をtext-only opt-inとしてCLIへ接続した。text modeだけで、測定済みの`InstalledEnvironment`からinstalled Core Metadata graphを構築し、dependency path explanationを既存reportの後ろへ表示する。`--bin --explain`も既存script presentationを維持する。
- `--json --explain`はmetadata adapter、graph、explanation rendererを呼ばず、`--json`単独とstdout、stderr、exit behaviorがbyte-identicalになるよう固定した。schema v1には説明データを追加していない。
- adapter境界とexplanation validationの既知の`ValueError`は固定されたsanitized Click errorへ変換する。`TypeError`などのprogrammer errorは握りつぶさない。metadata graphがincompleteでもsize reportはexit 0で、rendererはsafe warning codeと件数だけを表示する。
- local wheelhouseの2 rootとshared dependencyを実installして、rootごとのpath、shared label、offline JSON `--explain` equalityを検証した。READMEにはinstalled Core Metadata由来でresolver provenanceではないこと、partial warning、JSON v1不変、root別byte attribution未実装を記載した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_uv_packsize.py tests/test_local_wheel_integration.py` — 成功（49 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（382 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make verify-build` — explanationを含むwheel/sdist、artifact metadata、installed entry pointを検証して成功。

引き継ぎ:

- 次のタスクはP3-03とする。self/transitive totalとfile category別内訳のpolicyを、root別byte attributionとは分けて設計・実装する。

### P3-03: global footprint policyとpresentation

目的:

- `AnalysisResult`のcanonical file inventoryを唯一のbyte sourceとして、global dedupeを崩さずfile categoryとdependency roleの内訳を説明可能にする。

分割:

- P3-03aは`ExplainedAnalysisResult`だけを入力に、全`FileCategory`（zero rowを含む）のglobal totalと、graph complete時だけ利用できるdependency role totalをpure immutable resultとして導出する。roleは`self`、`direct`、`transitive`、`unattributed`、複数owner roleが衝突した`mixed-ownership`とする。root別byte配賦は行わない。
- P3-03bはP3-03a resultのpure text presentationを実装する。既存report/JSON schema v1/CLI契約は変更しない。
- P3-03cはtext opt-in public contract、README、end-to-end coverageを接続する。JSON schema v1は互換境界として変更しない。

不変条件:

- `canonical_identity`ごとにlogical bytesは一度だけ数える。shared dependency、同名root input、duplicate ownershipはglobal totalを増やさない。
- graphがincompleteならcategory totalは利用可能なままにし、role totalはavailabilityを明示して提供しない。inventoryとgraphのcompletenessは別々に保持する。
- role/categoryの各subtotalおよびglobal totalはfile inventoryから再計算して検証し、外部から供給された不整合なaggregateは拒否する。
- rootでもあるdistributionは`self`であり、root別の容量寄与はP3-05まで主張しない。

### P3-04: existing virtual environment / prefix input mode

目的:

- 既存のvirtual environmentまたはprefixを実行・変更せずにinventoryとして分析し、解決時の条件が不明な場合もその不確実性を捏造せずに結果へ表現する。

分割:

- P3-04a1はpure modelに`ExistingPrefixContext`を追加する。これはtargetのpath/case semanticsと安全に観測できたPython/platform/architectureだけを保持し、requirements、resolver、index、build、bytecodeの由来は表現しない。optional observationはpath-likeな値を拒否する。既存JSON schema v1は`ResolutionContext`専用の互換境界として明示的に拒否する。
- P3-04a2は既存prefix contextを表現できるversioned JSON schema v2をpure serializerとして実装する。v1のbytesは変更しない。
- P3-04bはprefix layoutと安全な観測contextをfilesystemから収集するread-only adapterを実装する。既存Pythonを実行せず、unknownは`None`として残す。
- P3-04cはpublic CLI、README、local prefix integrationとerror contractを接続する。graph/explanationがrequirements由来の主張を必要とする場合のavailabilityは明示する。

不変条件:

- prefix inputはuser/CIの既存環境へinstall、uninstall、Python実行、metadata書換えを行わない。
- observed contextはabsolute raw path、credential、requirements、index URLなどを結果modelまたはJSONへ保持しない。
- `path_flavor`と`case_rule`はinventory layoutと常に一致し、不一致は収集前にtyped errorになる。
- JSON schema v1と既存のresolution-based text/JSON出力はbyte-compatibleに維持する。existing prefix結果はv2以降の明示的schemaでだけ機械可読に表現する。

### 2026-07-31: P3-04c1 existing-prefix CLI core/unit

完了したタスク。

変更:

- `--prefix PATH`、repeatableな`--site-packages REL`、`--case-rule sensitive|insensitive`を追加し、既存install modeと明確に排他的にした。`PATH`はClickの存在検証を使わず、adapterがread-onlyに検証する。
- prefix modeはuvの存在確認、venv作成、install、interpreter実行、subprocessを一切行わず、host nativeの`PathFlavor`とcaller指定の`CaseRule`で`discover_existing_prefix()`からinventory分析へ接続する。
- prefix JSONはschema v2を使い、`--json`併用時の`--bin`、`--explain`、`--breakdown`を完全に無視する。textの`--explain`/`--breakdown`はrequirements由来の主張をできないためusage errorで拒否する。
- `--bin`のprefix表示は固定の`Binaries in prefix`見出しを使用し、既存install textの`Binaries in .venv/bin`およびbytesを変えない。render titleは固定許可値だけを受け入れる。
- discovery、analysis、inventoryの公開エラーはraw prefix/path/metadata/causeを含まない固定診断へ正規化した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_render.py tests/test_uv_packsize.py -q` — 成功（78 passed）。
- full CI/lock/build検証はP3-04c2のlocal integration/READMEと合わせて実施する。

次のタスクはP3-04c2とする。READMEのpublic contractとlocal prefix end-to-end/error検証を追加し、P3-04cを完了する。

### 2026-07-31: P3-04c2 existing-prefix README/local integration

完了したタスク。

変更:

- READMEに`--prefix`、repeatableな`--site-packages`、明示的`--case-rule`の入力契約を追加した。relative prefixのcanonical physical directory化、native host path formのみの受理、trustedなcase declaration、read-only操作範囲、TOCTOUのbest-effort制約を明記した。
- fresh installのJSON schema v1とexisting-prefix JSON schema v2の境界、v2 contextのunknown `null`/empty値とraw local path非出力、prefix textでgraph由来の`--explain`/`--breakdown`を利用できない理由、JSON時のpresentation flag無視、prefix用`--bin`見出し、POSIX shebangによるscript logical sizeのpath依存を公開契約として記録した。
- local wheel end-to-endを追加し、fresh resultからtarget `case_rule`を取得してprefix CLIへ渡す。両modeでdistribution名/version、warnings、completeness、duplicate ownership、non-script file objectを厳密比較し、scriptは`logical_bytes`以外のprojectionを比較する。global non-script unique bytesは一致し、global totalの差がunique script bytesだけで説明できることを確認する。
- v2 contextのcase rule、unknown `null`/empty fields、raw local path非出力、prefix textの`--bin` total不変、`--json`とtext presentation flagの7組合せのbyte一致、scan前後のfull prefix hash snapshot不変をlocal wheelで検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make readme`、`make ci-check`、`make test` — 成功（509 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointを検証した。

P3-04は完了。次のタスクはP3-05とし、複数rootへのbyte寄与とshared dependencyの非二重計上を表示・検証する。

### P3-05: multiple-root contribution policyとpresentation

目的:

- canonical file inventoryを唯一のbyte sourceとして、複数rootへ到達する依存物を分割も二重計上もせずに説明可能にする。

分割:

- P3-05aは`ExplainedAnalysisResult`を入力に、exact root-set bucketとrootごとのclosure/exclusive/sharedをpure immutable resultとして導出する。
- P3-05bはP3-05a resultのpure text presentationを実装する。CLI、README、JSON schemaは変更しない。
- P3-05cはtext-only public CLI option、README、local wheel integrationを接続する。既存JSON schemaは互換境界として変更しない。

不変条件:

- canonical identityごとにlogical bytes、category、file countは一度だけ数える。各fileのroot setは、そのfileを所有する全distribution nodeの`root_names` unionで決める。
- empty root set（unattributed bucket）は常に存在し、recognized root名ごとのsingleton bucketは観測fileがなくても存在する。observed shared root setも保持する。
- graphがincompleteならroot set totalとroot contributionは利用不能を明示して提供しない。ただしfootprintのinventory-derived category totalと測定済みのpartial bytesは保持する。
- duplicate root inputはroot input indexを保持するがbyte bucketを増やさない。rootでもあるdependency、cycle、duplicate file ownershipはdistribution nodeのroot-name unionを用いる。

### 2026-07-31: P3-05a pure root contribution aggregation

状態: `done`

実装:

- [`uv_packsize/root_contributions.py`](../uv_packsize/root_contributions.py)に、全6 categoryを固定順で持つ`RootSetTotal`と`RootScopedTotal`、rootごとの`closure`/`exclusive`/`shared`を持つ`RootContribution`、およびsource `ExplainedAnalysisResult`と同一sourceの`FootprintResult`を保持する`RootContributionResult`を追加した。
- exact root-setはcanonical identityごとに一度だけ集計し、そのidentityを所有する全distributionのgraph `root_names`をunionする。shared bytesはroot間に割り振らず、各rootのclosureでは参照するだけにする。
- graph incomplete時はroot-set/root contributionを`None`にし、footprint category totalとinventory completenessを維持する。aggregate constructorはsourceから再計算し、順序、欠損、改ざん済み値を拒否する。
- [`tests/test_root_contributions.py`](../tests/test_root_contributions.py)でempty/zero category、2 root shared、duplicate root input、rootかつdependency/cycle、duplicate ownership union/unattributed、graph/inventory incomplete、determinism/immutability/forged aggregateをnetwork不要で検証した。artifact verifierに新moduleを追加した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_root_contributions.py -q` — 成功（9 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（518 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointを検証した。

引き継ぎ:

- 次のタスクはP3-05bとする。P3-05a resultをpure text presentationへ接続し、既存report、CLI、README、JSON schemaを変更しない。

### 2026-07-31: P3-05b root contribution pure text presentation

状態: `done`

実装:

- [`uv_packsize/root_contribution_render.py`](../uv_packsize/root_contribution_render.py)に、既存の通常reportをbyte-identical prefixとして再利用する`render_root_contribution_report()`と、将来のexplain/breakdown合成向けの`render_root_contribution_sections()`を追加した。後者はgraph warning code/count summaryの重複を抑止できる。
- complete graphでは、1-based input indices、exclusive/shared/closureを持つroot table、exact shared root-set table、exclusive/shared/unattributed/global totalのreconciliationを表示する。closureのroot間非加算とreconciliationの加算式を明示し、全bytesは既存`format_size()`で表示する。
- incomplete graphではcontribution sectionの数値およびraw target/pathを出さず、availabilityと安全なwarning code/countだけを表示する。inventory incompleteでは測定済みpartial値を維持し、安全なnoteを追加する。terminal control文字は表示ラベルから置換する。
- [`tests/test_root_contribution_render.py`](../tests/test_root_contribution_render.py)で既存prefix、`--bin`相当のpresentation不変性、duplicate input index、shared/zero/rootなし、KiB/MiB/GiB境界と複数size列のalignment、graph/inventory incomplete、terminal sanitization、型検証、warning重複抑止をnetwork不要で検証した。artifact verifierに新renderer moduleを追加した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_root_contribution_render.py -q` — 成功（11 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（528 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run python scripts/verify_build.py`、`git diff --check` — 成功。wheel/sdistとinstalled entry pointを検証した。

引き継ぎ:

- 次のタスクはP3-05cとする。root contributionのtext-only public CLI option、README、local wheel integrationを接続し、既存JSON schemaを変更しない。

### 2026-07-31: P3-05c root contribution public CLI/README/local integration

状態: `done`

実装:

- `--contributions`をtext-only opt-inとしてCLIへ接続した。通常reportを一度だけbyte-identical prefixとして描画し、`--explain`、`--breakdown`、contribution sectionsをその順で合成する。いずれかのgraph-derived text optionが必要な場合もinstalled Core Metadata graphは一度だけ構築する。
- explanation rendererへsection-only APIを追加し、合成経路でsafe graph-warning code/count summaryを一度だけ出す。graph incomplete時もfootprint category totalsは保持し、contribution sectionsは数値を出さずunavailableを明示する。
- JSON schema v1/v2は変更していない。`--json`では`--contributions`を含む全text optionを無視し、metadata graph、footprint、root contribution aggregateを呼ばず、stdout/stderr bytesを保持する。prefix textでは`--contributions`をusage errorとし、prefix JSONでは無視する。
- READMEにCore Metadata reachability、root closureの非加算、exact shared root-setの一度だけの計上、observed graph（resolver counterfactualではない）、duplicate input index、incomplete graphの公開契約を追記した。local wheelhouseのoffline E2Eで2 rootとshared dependencyのexclusive/shared/closure、exact shared root-set、global reconciliation、section order、JSON option byte equalityを検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_uv_packsize.py tests/test_local_wheel_integration.py tests/test_explanation.py -q` — 成功（81 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check`、`make test` — 成功（534 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。wheel/sdistとinstalled entry pointを検証した。

引き継ぎ:

- Phase 3は完了。次のタスク候補はP4-01aとし、baseline JSONとdiff policyの互換契約、入力model、schema version境界を先に固定してからP4-01の比較・budget policyへ進む。

### 2026-07-31: P4-01a baseline JSON contract/model

状態: `done`

実装:

- `uv_packsize/baseline.py`に、既存の公開JSON schema v1/v2だけを受理するpure decoderと、比較用のfrozen projection modelを追加した。CLI、既存serializer、schema、READMEの公開契約は変更していない。
- projectionはschema version/input kind、固定measurement contract、`totals.global_logical_bytes`、normalized distribution name/version/logical bytes、completeness/warning code count、duplicate ownershipの有無/件数、v1の安全なresolution comparison contextを保持する。raw requirement、file path、symlink target、baseline file path、credentialはmodelに保持しない。v2は`existing-prefix`を明示し、resolver provenanceの空/nullを補完しない。
- decoderはschema version/context family、全objectのclosed shape、measurement constants、nonnegative non-bool bytes、path/name/type、v1 requirement projection、v2 empty/null field、normalized distribution collisionを検査する。distribution/file/global totals、duplicate ownership relation、warning由来のcompletenessもcanonical inventoryと照合する。distribution totalsの合計とglobal totalの一致は要求せず、duplicate ownershipによる差を許容する。
- `parse_baseline_json()`はstr/bytes/bytearrayのpure境界、`load_baseline(Path)`はread-only file境界として分離した。I/O/parse diagnosticsは固定code/fieldだけで、raw content/path/OS causeを反射しない。load前8 MiB、decoded JSONの64 nesting、100,000 item、1,000,000 char string、signed 64-bit nonnegative integerの上限を設け、比較入力として過度なresource消費を避ける。
- レビュー後、JSON parserの全object階層でduplicate keyを固定診断により拒否し、bytesはBOMなしUTF-8だけを受理するよう明確化した。`load_baseline()`はsymlink/special fileを拒否し、同一nonblocking descriptorの`fstat`確認後に最大8 MiB+1 byteだけを読んでTOCTOU/無制限read/FIFO blockingを避ける。`O_NOFOLLOW`が利用可能なplatformでは併用する。
- canonical identityが複数distributionに現れる場合はlogical bytes、category、symlink flagを一致検証し、duplicate ownership relationとroot-level `duplicate-ownership` warningを対象identityまで相互導出する。distribution-levelの同warningは拒否する。v1 requirement projectionとbuild policyも既存serializerが生成可能な組合せだけを比較modelへ残す。
- v1 comparison contextのfree-form Python/platform/architecture/uv version/resolution strategyは、validation後にfield名をdomain-separatedしたSHA-256 fingerprintだけへ投影する。比較modelのdataclass/reprには元文字列を残さず、1文字差もcomparison equalityへ反映する。requirements、enum、bool、extras、index aliasのsafe structured fieldは保持する。URL/credential専用field、raw requirement、raw path、symlink targetは引き続き保持しない。
- v2 existing-prefixのnullable Python/platform/architectureも同様に扱い、`None`はそのまま保持し、schemaのsafe observationを通過した非`None`値だけをdomain-separated fingerprintへ投影する。したがってprivate tokenや表示制御文字を含む観測値もcomparison modelのfield/reprには残さない。
- v1/v2 golden acceptance、順序不変/frozen model、closed-shape/type/context mismatch、duplicate JSON key、UTF-8/BOM、孤立surrogate、5000桁integer、total/ownership/file signature/warning target semantic mismatch、free-form context fingerprint、sanitized diagnostics、symlink/FIFO/open後inode変更を含むfile I/O境界をnetwork不要で検証した。artifact verifierにも新moduleを追加した。

検証:

- `uv run --locked pytest tests/test_baseline.py tests/test_json_render.py -q` — 成功（84 passed）。
- `make ci-check` — 成功。
- `make test` — 成功（569 passed, 2 skipped）。
- `uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。

引き継ぎ:

- 次のタスクはP4-01bとする。baseline projectionを入力に、比較可否判定とdistribution/global diffをpure immutable modelとして実装する。CLI、budget policy、baseline書込みはまだ接続しない。

### 2026-07-31: P4-01b baseline pure diff model

状態: `done`

実装:

- `uv_packsize/diff.py`に、frozen/slots/kw-onlyの`DistributionDelta`、`AnalysisDiff`、typed change/incompatibility enumと`compare_baselines()`を追加した。distributionはnormalized nameでname昇順full outer joinし、added/removed/version-changed/unchangedをprojectionから検証する。bytesは左右projectionから導出し、欠側を0として符号付きdeltaを保持する。
- 比較はschema v1 fresh-install同士だけを許可し、measurement全fieldとresolution comparison context全field（input order、fingerprint、enum/bool、extras、index aliasを含む）の一致を要求する。schema v2を含む比較はresolver provenanceがないため`unsupported-existing-prefix`で拒否する。未知schema、measurement/context mismatchにはtyped reasonを返し、診断はraw baseline値を反射しない。
- global deltaは常に左右のglobal totalから導出し、distribution aggregateとは別に保持する。duplicate ownershipでは両者が一致しないことを許容する。不完全baselineはrejectせずpartial deltaと左右/aggregate completenessへ投影し、budget policyの判断は後続taskへ残す。
- forged modelのbool/negative total、非canonical/重複distribution、wrong delta kind/total/completeness、unsupported contextを拒否するvalidationを追加した。既存JSON serializer、CLI、README、baseline parserは変更していない。artifact verifierは`diff.py`を必須moduleとして確認する。
- レビュー後、direct forged baselineにもdecoderと同等のwarning code/件数順序/complete判定、duplicate ownership summary、measurement constants、schema/context family、v1 requirement projection、fingerprint形式、path/case/build policy、bytes上限を再検証する境界を追加した。`AnalysisDiff`と`DistributionDelta`のreprはnested baselineやdistribution projectionを表示せず、count、status、aggregate bytesだけを表示する。
- 最終レビュー後、`AnalysisDiff`のglobal/distribution signed deltaをboolではない`int`かつ`-MAX_BASELINE_INTEGER..MAX_BASELINE_INTEGER`へ制限し、左右およびaggregate completenessもplain stringを許さないexactな`Completeness` enumとして、導出値との照合前に検証するよう明確化した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_diff.py tests/test_baseline.py -q` — 成功（58 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（592 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。

引き継ぎ:

- 次のタスクはP4-02aとする。`AnalysisDiff`のpure text rendererを追加し、CLI、JSON schema、baseline file I/O、budget policyには接続しない。

### 2026-07-31: P4-02a pure diff text renderer

状態: `done`

実装:

- `uv_packsize/diff_render.py`に、I/O、比較可否判定、CLIを持たない`AnalysisDiff`専用の`render_diff_report()`とsection APIを追加した。global logical sizeを先頭のcanonical metricとしてbaseline/current/signed changeで表示し、distribution-owned aggregateは別metricとして明示する。
- `format_signed_size()`はboolを拒否するbounded signed integer専用formatとし、absolute valueには既存`format_size()`を再利用する。zeroは`0 B`、非zeroは`+`/`-`を付け、既存size formatterの契約は変更していない。
- distributionはcanonical name順でadded、removed、changedに分ける。version changeに加えてkindがunchangedでもbytes deltaを持つrowをchangedとし、完全不変rowは出力しない。Changed tableは表示上の意味を明確にする`Change type`列を持ち、size-only、version-only、両方を`size`、`version`、`version+size`として出す。変化がない場合は固定の`No distribution changes.` sectionを出す。
- incomplete comparisonではbaselineからcurrentの固定順でwarning code/countだけを表示し、partial deltaであることを明記する。global deltaとdistribution aggregate deltaが異なる場合だけ、duplicate-owned filesがdistribution totalsでは重複し得る一方globalはcanonical identityを一度だけ数えるため非reconciliationとなる安全なnoteを表示する。
- distribution name/versionはUnicode C categoryを`?`へ置換し、それ以外のnon-ASCIIは固定幅ASCII Unicode escapeへ正規化する。これによりテーブルの`len`幅と端末表示幅を一致させる。baseline repr、fingerprint、target/path/requirementはrendererから参照しない。artifact verifierに新rendererをcritical moduleとして追加した。

テスト:

- `tests/test_diff_render.py`でsigned sizeのzero、正負、unit境界、最大値、bool/range rejection、empty/add/remove/version-only/size-only/both changeと3種のexact change type、canonical ordering、aggregate nonreconciliation、incomplete warning code/count順序、zero-distribution baseline、private context fingerprint/repr非表示、ASCII escape化した全角/combining/emoji/bidi/control、安全なtable alignment、wrong type、section/report等価性を検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_diff_render.py -q` — 成功（33 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（625 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。

引き継ぎ:

- P4-02bは、current resultのpure projection（P4-02b1）とbaseline read/compare CLI boundary（P4-02b2）へ分割する。JSON schema、budget policy、baseline書込みは別taskとして扱う。

### 2026-07-31: P4-02b1 current AnalysisResult baseline projection

状態: `done`

実装:

- `analysis_result_to_baseline()`を追加し、exactな`AnalysisResult`かつfresh `ResolutionContext`だけをschema v1の比較用`Baseline`へ直接縮約する。既存prefix contextはtypedに拒否し、JSON serializer/decoderを経由しない。
- requirementは既存JSONと同じnon-reversible projection、free-form contextは同じdomain-separated fingerprintへ縮約する。raw requirement、index credential、path、symlink target、free-form contextはcomparison modelへ保持しない。
- global/distribution totalsとduplicate ownershipはvalidated `AnalysisResult` propertiesから導出し、distribution totalsの重複所有とglobal deduplicationの差を保持する。
- `BaselineWarningSummary.warning_code_counts`はroot warningとdistribution warningのcanonical aggregateへ統一した。これによりdistribution-only incomplete warningを含むpublic baselineもparse後にself comparisonできる。公開JSON schema/bytesは不変である。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_baseline.py tests/test_diff.py -q` — 成功（63 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（630 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。

引き継ぎ:

- 次のタスクはP4-02b2とする。baseline read/compare error boundaryとCLI表示を接続する。

### 2026-07-31: P4-02b2 compare CLI/read boundary

状態: `done`

実装:

- 既存single commandへ`--baseline PATH`を追加した。比較と排他となる`--prefix`、`--json`、`--bin`、`--explain`、`--breakdown`、`--contributions`はbaseline load、`uv`検出、temporary environment作成より先に固定順でusage errorへ正規化する。`--python`、`--allow-build`、package inputはcurrent測定として許可した。
- guard通過後はbaselineを一度だけread-onlyでloadし、baseline load/parse/semantic failureをsafeな`code`/`field`だけのexit 3へ変換する。比較不能はpure policyのreasonをそのままsafe identifierとしてexit 4へ変換する。既存のoperational failureはexit 1、usage errorはexit 2のままである。
- current `AnalysisResult`はserialize/parseせず`analysis_result_to_baseline()`、`compare_baselines()`、`render_diff_report()`へ直接渡す。比較成功時のstdoutはdiff reportだけで、全progressはstderrへ出す。incompleteでも比較可能ならpartial warning付きexit 0とする。baseline fileは書き換えない。
- READMEにread-only使用例、schema v1/context requirement、v2 existing-prefix未対応、global canonical totalとdistribution aggregateの差、incomplete partial、compare JSON未提供、exit 0--4を追記した。既存JSON schema v1/v2の出力分岐は変更していない。

テスト:

- unitではhelp、direct projector（serializer未使用）、stdout/stderr、baseline不変、loader一度だけのread、baseline conflictとshared fresh usage guardがloader/uvより先であること、safeなexit 3、actual context mismatchと全incompatibility reasonのexit 4、current operational exit 1、incomplete comparable resultのpartial warning付きexit 0を検証した。network-free local wheel E2Eでは同CLIの`--json`で生成したbaselineとのcompare、stdout/stderr分離、baseline byte不変を検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_uv_packsize.py tests/test_local_wheel_integration.py -q` — 成功（96 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check`、`make test` — 成功（650 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。

引き継ぎ:

- 次のタスクはP4-03とする。budget policyの前に、baseline writeとversioned diff JSONの公開契約を小さく分離して設計する。DoDは、read-only compare text/既存analysis JSON v1/v2を不変にしたまま、書込みの明示opt-in・atomicity・overwrite方針、diff schema version/安全なfield、JSON成功/失敗stdout契約、unit testを固定すること。budget enforcement、config file、CI workflowは含めない。

### 2026-07-31: P4-03 diff JSON/baseline write contract

状態: `done`

設計判断:

- 比較JSONとbaseline書込みは、責務・失敗境界・公開schemaを分離する。既存のanalysis JSON schema v1/v2、`--baseline` text比較、`--json > baseline.json`による既存のbaseline作成経路は変更しない。budget enforcement、設定file、CI workflowはP4-03の対象外とし、P4-04aへ送る。
- diff JSONはclosedでdeterministicな`comparison-result-v1`とする。JSON Schemaはdraft 2020-12でtop/nested objectを`additionalProperties: false`、全field必須、`schema_version: 1`に固定する。serializerのtop-level insertion orderは`schema_version`、`measurement`、`context`、`baseline`、`current`、`changes`、`completeness`とする。nested shapeはliteralに、`context={input_kind,comparison_context_fingerprint}`、side=`{totals:{global_logical_bytes,distribution_logical_bytes},completeness,warning_code_counts:[{code,count}],duplicate_ownership:{present,count}}`、`changes={totals:{global_logical_bytes_delta,distribution_logical_bytes_delta},distributions:[{name,kind,baseline:{version,logical_bytes}|null,current:{version,logical_bytes}|null,logical_bytes_delta}],nonreconciliation:{present,distribution_minus_global_logical_bytes_delta,reason}}`と固定する。fingerprintはcanonicalなsafe `BaselineResolutionContext` projectionをUTF-8 canonical JSONへ縮約し、`uv-packsize/comparison-context/v1\0`をdomainとしてSHA-256する。`changes.distributions`はfull outer joinでunchangedを含む。`nonreconciliation.present=false`はdelta `0`かつreason `null`、`true`はnonzero deltaかつ固定reason `duplicate-owned-files-may-be-counted-per-distribution`を必須とする。raw requirement、path、symlink target、baseline path、credential、free-form contextの元値は出力しない。このfingerprintは比較結果の相関には使えるため、共有時の相関可能性をREADMEで明記する。
- `--comparison-json`は`--baseline`を必須とし、compare成功時にJSON+LFだけをstdoutへ出す。既存text比較のstdout bytesは不変とする。比較前のusage/loader/operational failure、比較不能、serializer failureを含む失敗時はstdoutを空にし、既存exit code 1--4とsanitized stderrを維持する。
- baseline writeはfresh-install schema v1の既存`render_analysis_json()` bytesを保存する。比較用に縮約した`Baseline` modelを新schemaとして書き出さない。pure render/validate境界でexactなfresh `AnalysisResult`、8 MiB上限、`parse_baseline_json(payload)`とのprojection parityを検証してからI/Oへ渡す。これにより書込み直後のfileは既存`load_baseline()`で読め、`--json --write-baseline`ではstdoutと保存fileが完全一致する。
- `--write-baseline PATH`はfresh analysisだけで許可し、`--prefix`および`--baseline`と排他とする。既定はno-clobber、既存targetの置換は`--overwrite-baseline`明示時だけ許可する。`--overwrite-baseline`単独はusage errorとする。text presentation optionは保存bytesを変えない。write modeのprogressはstderrに寄せ、analysis成功後かつreport/JSON stdoutの前に書込む。失敗時はstdoutを空、exit 3、固定codeだけの診断とする。
- writerは既存directoryのparentだけを許可し、parentのsymlink/non-directoryとopen後のdevice/inode identity raceを拒否する。既存targetはsymlink/special fileを拒否し、hardlink拒否はregular targetの`st_nlink != 1`にだけ適用する。同一directoryに0600のexclusive temp fileを作成し、write、file fsync、close、atomic publish、可能なplatformでdirectory fsync、cleanupを行う。tempの0600 modeを維持してpublishし、最終baseline fileも0600とする。POSIXではparent directory FDとrelative basename、`O_NOFOLLOW | O_DIRECTORY`、`lstat`/`fstat` identity照合、`dir_fd`付きlinkまたはreplaceを使用する。no-clobber publishはatomic linkで競合上書きを防ぎ、非対応filesystemは安全側で失敗する。overwriteはatomic replaceを使う。path、temp name、payload、OS診断をエラーへ反射せず`BaselineWriteError`を既存baseline failure境界（exit 3）へ正規化する。Windowsではatomic visibilityを保証対象とし、directory entry durabilityはplatform依存としてREADMEに明記する。

分割:

| ID | 状態 | 依存 | 対象files | 完了条件 |
|---|---|---|---|---|
| P4-03a | `todo` | P4-03 | `uv_packsize/comparison_json_render.py`（新規）、`schemas/comparison-result-v1.schema.json`（新規）、`tests/test_comparison_json_render.py`（新規）、必要なら`tests/test_diff.py` | exactな`AnalysisDiff`だけを受ける`comparison_diff_to_json_object()`/`render_comparison_json()`とclosed `comparison-result-v1` JSON Schemaを実装する。top-levelの固定順、`input_kind`+canonical safe context fingerprint、side summary、signed totals、全distribution full outer joinのnullable sides/delta、warning code/count、`false => 0/null`・`true => nonzero/fixed reason`のnonreconciliation、int/enum/orderingをnetwork/I/Oなしのgolden/unit testで固定する。analysis JSON v1/v2とCLIを変更しない。 |
| P4-03b | `todo` | P4-03a, P4-02b2 | `uv_packsize/cli.py`、`README.md`、`tests/test_uv_packsize.py`、`tests/test_local_wheel_integration.py` | `--comparison-json`を`--baseline`必須の比較表示modeとして接続する。JSON+LF-only stdout、text比較byte不変、failure時empty stdout、usage/load/operational/incompatibleの既存exit 1--4、sanitized diagnostics、loader/uvより先のoption guardをunit/local-wheel testで固定する。baseline書込み、analysis JSON schema変更、budgetは含めない。 |
| P4-03c | `done` | P4-03 | `uv_packsize/baseline_write.py`、`tests/test_baseline_write.py`、`scripts/verify_build.py` | fresh v1 JSONのpure render/validate APIとPOSIX atomic writerをCLIなしで実装した。descriptor-relative platform featureのうち事前検査可能なAPIをI/O前に確認し、macOS等で`supports_dir_fd`へ載らない`replace`は実call failureをtypedに正規化する。Windows/dir-FD platformにはunsafe fallbackを使わずtyped unsupportedとする。non-writable parentはforeign traversal anchorとして許可し、writable parentだけはsame-effective-userかつstickyを要求する。target/temp identity、no-clobber競合、explicit overwrite、0600、file/directory fsync、cleanup、race/I/O失敗のsanitized typed errorをnetwork不要testで固定した。P4-03dでこのplatform制約をREADMEへ公開する。 |
| P4-03d | `done` | P4-03c, P4-02b2 | `uv_packsize/cli.py`、`README.md`、`tests/test_uv_packsize.py`、`tests/test_local_wheel_integration.py` | `--write-baseline PATH`/`--overwrite-baseline`をpublic contractへ接続する。初回progressからstderr、fresh-only/排他usage guard、write-before-report/JSON stdout、failure時exit 3/empty stdout、`--json` stdout=file exact bytes、text flags非影響、no-clobber/overwrite、offline local-wheel write→compare roundtripと既存redirect経路を検証する。comparison JSON、budget、config/CIは含めない。 |
| P4-04a | `done` | P4-03a, P4-03d | `uv_packsize/budget.py`（新規）、`tests/test_budget.py`（新規）、`scripts/verify_build.py` | `AnalysisDiff`とbaseline write/readの契約を前提に、budget policyのpure domain model、incomplete/nonreconciliationの判断、typed violationをCLI/config/CIなしで実装した。 |
| P4-04b | `done` | P4-04a | `uv_packsize/budget_render.py`（新規）、`tests/test_budget_render.py`（新規）、`scripts/verify_build.py` | exactな`BudgetEvaluation`だけを再検証して受けるsafeかつdeterministicなtext presentationを実装した。canonical global authority、configured metric、no-op、completeness policy、fixed violation orderをpureに表示し、CLI/config/JSON schema/exit codeは変更しない。 |
| P4-04c | `done` | P4-04b | `uv_packsize/budget_config.py`（新規）、`tests/test_budget_config.py`（新規）、`scripts/verify_build.py`、`docs/implementation-plan.md` | exact built-in `dict`だけをtrusted policy mappingとして受ける`parse_budget_policy()`を実装した。closed snake_case keys、missing field/default no-op、exact nonbool integer range、exact incomplete-policy string、unknown/type/range/incomplete-policy/internal-inputのfixed taxonomyとpriority、safe enum field/path付きsanitized typed errorをunit testで固定した。CLI、`pyproject.toml` I/O、exit code、CIは未接続。 |
| P4-04d | `done` | P4-04c | `uv_packsize/budget_config_source.py`、`tests/test_budget_config_source.py`、`tests/test_verify_build.py`、`pyproject.toml`、`uv.lock`、`scripts/verify_build.py`、`docs/implementation-plan.md` | explicit native `Path`だけを受ける`load_budget_policy()`を実装した。`[tool.uv-packsize.budget]`不在は`None`、明示空tableはno-op policyとし、nonblocking bounded regular-file read、open前後identity照合、TOML/section/source errorのsanitized typed taxonomyを固定した。Python 3.10ではconditional runtime `tomli`、3.11+ではstdlib `tomllib`を使い、artifact metadataのmarkerを厳密に検証する。CLI option、budget exit code、README、CI workflowは未接続。 |
| P4-04e | `done` | P4-04d | `docs/implementation-plan.md`、`docs/roadmap.md` | 公開する`--budget-config PATH`、`--max-total BYTES`、`--max-increase BYTES`、`--incomplete-policy`、明示sourceのみ・field単位のCLI優先、no-source/no-op/incomplete/比較/失敗のexit・stdout・stderr、fresh/write/JSON/prefixとの境界を実装可能な契約として固定した。 |
| P4-04f | `done` | P4-04e | `uv_packsize/cli.py`、`README.md`、`tests/test_uv_packsize.py`、`tests/test_local_wheel_integration.py`、必要ならbudget CLI専用test | P4-04eの契約どおりpolicy source/CLI override/evaluation/render/exit 5を接続する。source/CLI precedence、sourceなし・明示no-op、incomplete fail/allow-partial、increaseのbaseline requirement、text/JSON/comparison JSON/write/prefix/errorのstdout/stderr不変性をnetwork-free unit/local-wheel testで固定し、READMEの公開契約とCI利用例を追加する。 |

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `git diff --check` — 成功。

最初の次タスク:

- P5-02とする。project/lock analysis input/context contractを設計する。`uv workspace metadata`はP5-01で固定した非対応境界を越えない。

## 作業記録

### 2026-08-12: F-011 Node 24 Actions major update

状態: local `done` / deployment verification pending

変更:

- 全GitHub workflowの`astral-sh/setup-uv@v6`をNode 24対応の`@v7`へ更新した。Pages workflowは`actions/configure-pages@v5`を`@v6`、`actions/upload-pages-artifact@v4`を`@v5`、`actions/deploy-pages@v4`を`@v5`へ更新した。
- workflowのtrigger、path filter、job構造、permissions、release/tag検証、test matrix、publish gate、pinned uv versionは変更していない。release、tag、publish、pushは実施していない。
- READMEとCI guideのGitHub Actions例、そのexact fixtureを`setup-uv@v7`へ同期した。fixtureのREADME/Docs逐語一致とleast-privilege/read-only契約を維持した。
- CI、publish、update、Pagesのaction参照majorをexact testで固定し、旧Node 20 majorが各workflowに残らないことを検証した。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f011-cache uv run --locked python -c 'import pathlib,yaml; files=sorted(pathlib.Path(".github/workflows").glob("*.yml")); [yaml.safe_load(p.read_text()) for p in files]; print(f"parsed {len(files)} workflows")'
UV_CACHE_DIR=/private/tmp/uv-packsize-f011-cache uv run --locked pytest tests/test_ci_workflow_example.py tests/test_pages_docs.py tests/test_uv_packsize.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f011-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f011-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f011-cache uv lock --check
git diff --check
```

結果:

- 4 workflowのYAML parseが成功。focused testsは177 passed、全体は1005 passed / 2 skipped。format、lint、typecheck、README Cog整合性、MkDocs strict buildも成功した。
- local DoDは完了した。remote完了条件として、push後に通常CIとPagesの実runが成功し、Node.js 20 deprecation annotationが消滅することの確認が残る。

次のタスク:

- 変更をpushした後、CIとPages deploymentを確認し、Node 20 annotationが再発しないことを記録する。明示依頼なしにrelease/tag/publishは行わない。

### 2026-08-12: F-009 budget config source observable rewrite hardening

状態: `done`

変更:

- explicit `pyproject.toml` budget sourceのpre-open snapshotをdevice、inode、mode、size、mtime_ns、ctime_nsの固定tupleへ拡張し、open直後のdescriptorが同じregular file snapshotであることを検証するようにした。
- bounded read後・close前にdescriptorの`fstat`とfollow後pathの`stat`を再取得し、両方がpre-open snapshotと全一致する場合だけcloseとparseへ進む。post-readのpath消失、非regular化、別inode置換、同一inode・同一lengthの観測可能なrewriteを`changed-file/file`として拒否する。
- post-read再照合中のその他の`OSError`/`ValueError`は`read-failed/file`へsanitizationする。body errorはclose errorより優先し、body成功後のclose failureではparseせず`read-failed/file`とする既存lifecycleを維持した。
- symlink-follow、`O_NOFOLLOW`を使わない方針、親directory policy、bounded read、normal policy parsingは変更していない。この契約はmetadataで観測可能なrewriteの拒否であり、filesystem-levelのimmutable snapshotは保証しない。
- CLIで実際のpost-read mismatchを通し、exit 3、stdout empty、baseline loader/uv未実行、raw config path/content/baseline path/traceback非表示を検証した。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f009-cache uv run --locked pytest tests/test_budget_config_source.py tests/test_uv_packsize.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f009-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f009-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f009-cache uv lock --check
git diff --check
```

結果:

- focused testsは192 passed、全体は1004 passed / 2 skipped。format、lint、typecheck、README Cog整合性、MkDocs strict buildも成功した。
- pre/open/post snapshot、同一inode・同一length rewrite、post path消失/非regular/置換、read/close error優先、parse禁止、CLI error境界をdeterministicに回帰固定した。

次のタスク:

- 残るF-011はupstream actionの正式なNode 24対応major待ちであり、現時点では実装せずreleaseを監視する。

### 2026-08-12: F-008 baseline read descriptor-close hardening

状態: `done`

変更:

- `load_baseline()`でread body成功後の`os.close()`が`OSError`になった場合、path、OS detail、raw causeを保持しない`BaselineLoadError(code=read-failed, field=file)`へ変換するようにした。
- body成功・close失敗時はJSON parseへ進まない。body側でvalidation errorまたはread `OSError`が発生済みの場合はclose失敗を抑止してbody errorを優先し、open失敗時はcloseを呼ばないdescriptor lifecycleを固定した。
- 既存のbounded read、regular-file/symlink検証、device/inode TOCTOU検出、`O_NOFOLLOW` fallback、hardlink/read validationとbaseline writerは変更していない。
- 実際のclose失敗をCLI境界まで通し、exit 3、stdout empty、uv未実行、path/OS detail/traceback非表示を検証した。CLI実装とREADMEの公開契約は変更していない。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f008-cache uv run --locked pytest tests/test_baseline.py tests/test_uv_packsize.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f008-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f008-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f008-cache uv lock --check
git diff --check
```

結果:

- focused testsは207 passed、全体は995 passed / 2 skipped。format、lint、typecheck、README Cog整合性、MkDocs strict buildも成功した。
- close failureのsanitization、body error優先、parse禁止、open failure時closeなし、CLI exit/channel/uv未実行を回帰固定した。

次のタスク:

- 未完了のF-009について、config sourceを同一inodeのin-place更新からimmutable snapshotとして守る必要性と実装境界を再評価する。

### 2026-08-12: F-010 第4段 opt-in TTY color

状態: `done`

変更:

- `--color [auto|always|never]`を公開し、既存text bytesを維持する`never`を表示defaultにした。`auto`はstdout reportがTTY、`TERM != dumb`、`NO_COLOR`未設定の全条件を満たす場合だけ有効になり、`always`はこれらを明示的に無視する。
- terminal-safeなplain reportの生成後に適用するpure color policy/decoratorを追加した。固定構造のheading、warning、completeness、budget PASS/FAILだけを装飾し、ANSIを除けばsemantic textと改行はplain reportに完全一致する。
- fresh install、project/lock、existing prefixのstandard/rich primary、追加graph/binary section、analysis/comparison、text budget reportを単一のhuman-report出力境界へ接続した。強制colorはglobal Click contextを変更せず、対象echoだけ`color=True`にする。
- progress、completion message、sanitized error、Click usage、JSON budget failure stderrは常にplainとした。analysis/comparison JSONは全color値を受理して完全に無視し、stdout/stderr bytes、exit code、TTY検査の有無を既存契約どおり維持する。
- READMEの生成helpと公開契約、MkDocsのpackage測定guideとmeasurement contractへdefault、auto判定、always override、JSON無視の境界を追加した。real local-wheel E2Eでもrich primary、追加section、budget、comparison、JSON無視を検証した。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-color-cache uv run --locked pytest tests/test_color_render.py tests/test_uv_packsize.py tests/test_project_lock_cli.py tests/test_local_wheel_integration.py tests/test_project_lock_e2e.py tests/test_pages_docs.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-color-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-color-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-color-cache uv lock --check
git diff --check
```

結果:

- focused testsは239 passed、全体は991 passed / 2 skipped。format、lint、typecheck、README Cog整合性、MkDocs strict buildも成功した。
- default/明示neverの既存bytes、autoのTTY/TERM/NO_COLOR条件、alwaysの非TTY強制、ANSI除去後のsemantic equivalence、plain diagnostic境界、全JSON modeの完全無視を検証した。

次のタスク:

- F-010 CLI text polishは完了。未完了のF-008 baseline read hardeningへ進む。

### 2026-08-12: F-010 第3段 `--quiet` progress suppression

状態: `done`

変更:

- 全入力mode共通のprivate progress helperを追加し、`--quiet`では一時的な進捗と完了messageだけを抑止するようにした。既定値はfalseであり、option未指定時の既存stdout/stderr、exit code、text/JSON bytesは変更しない。
- fresh install、project/lock、existing prefixのstandard/rich report、analysis/comparison JSON、baseline comparison/write、budget、dependency graph説明へquiet契約を接続した。final report、JSON、budget section、sanitized operational error、Click usage errorはprogress helperで包まず、quietでも維持する。
- JSONとcomparison JSONはquiet有無でstdout bytesが一致し、baseline write先も同一bytesになることを固定した。失敗時は既存exit statusとstdout-empty規則を維持する。
- READMEの生成helpと公開契約、MkDocsのpackage測定guideとmeasurement contractへquietの適用範囲を追加した。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-quiet-cache uv run --locked pytest tests/test_uv_packsize.py tests/test_project_lock_cli.py tests/test_pages_docs.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-quiet-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-quiet-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-quiet-cache uv lock --check
git diff --check
```

結果:

- focused testsは167 passed、全体は943 passed / 2 skipped。format、lint、typecheck、README Cog整合性、MkDocs strict build、lock整合性、diff checkも成功した。
- quietはprogressだけを抑止し、final text/JSON/budget/error/usageと既存channel/exit規則を保持することを全入力modeで検証した。

次のタスク:

- F-010 第4段として、非TTY、明示的なcolor無効化、既存ASCII bytesを守るTTY color契約を設計する。

### 2026-08-12: F-010 第2段 slice 3 rich summary公開契約

状態: `done`

変更:

- hiddenだった`--report [standard|rich]`を公開helpへ出し、default `standard`、richのredacted top-five summary、JSON/comparison JSONでは無視される境界を明記した。READMEのCog生成helpを同期し、standard byte互換とrich analysis/comparisonの公開契約を追加した。
- 利用者Docsへfresh/project-lockのrich利用方法、固定renderer由来の実出力例、top 5、canonical global total、distribution-owned aggregate、completeness、build policy、JSON byte不変、raw requirement/path/version/lock identity/context fingerprint非表示を記載した。
- redaction契約はrich primary summaryだけを対象とする。後置する既存sectionは対象外であり、`--bin`はscript path、`--explain`はresolved versionとdependency informationを含むinstalled metadataを表示し得ることをREADME、Docs、helpで明記した。
- real local wheel E2Eでfresh richと`--bin`、`--explain`、`--breakdown`、`--contributions`、budget、baseline writeの合成、rich comparison、analysis/comparison JSONのrich無視を検証した。real locked project E2Eでrich analysis/comparison、lock changed表示、version/lock identity非表示を検証した。
- Docsのrich例はfixed `AnalysisResult`からpublic projection/rendererで生成し、fixtureとMarkdown code blockの逐語一致を自動テストで固定した。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache uv run --locked pytest tests/test_pages_docs.py tests/test_local_wheel_integration.py tests/test_project_lock_e2e.py tests/test_uv_packsize.py tests/test_project_lock_cli.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache uv lock --check
git diff --check
```

結果:

- focused testsは172 passed、全体は924 passed / 2 skipped。format、lint、typecheck、README Cog整合性、MkDocs strict build、lock整合性、diff checkも成功した。
- default/明示standardの既存契約を変更せず、rich summaryをhuman textだけのopt-inとして公開した。

次のタスク:

- F-010 第3段として、quietとstdout/stderr channelの一貫性を既存machine-readable output契約を保ったまま設計する。

### 2026-08-12: F-010 第2段 slice 2 opt-in rich summary CLI接続

状態: `done`

変更:

- Clickの`--report [standard|rich]`を追加し、defaultの`standard`と明示`--report standard`は既存text bytes、channel、exit codeを維持した。`rich`はpure rich analysis/comparison viewをprimary text reportとして表示する。
- fresh installのrich reportは`--explain`、`--breakdown`、`--contributions`を既存順で続け、graph buildは一度だけ行う。`--bin`はstandard package tableを再表示せず、既存の安全なbinary sectionだけをrich primaryの後へ追加する。
- project-lock、existing-prefix、baseline comparison、budget sectionとexit 5へrich primaryを接続した。project/prefixの既存option guardsは維持した。
- `--json`と`--comparison-json`では`--report rich`を受理して無視し、stdout/stderr bytesとgraph callsを既存JSON契約どおりに維持する。rich projection/render failureはraw exceptionを出さず固定のClick errorへ正規化する。README/Docs/help公開契約は次sliceまで変更していない。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache uv run --locked pytest tests/test_rich_report.py tests/test_uv_packsize.py tests/test_project_lock_cli.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache uv lock --check
git diff --check
```

結果:

- focused testsは152 passed、全体は920 passed / 2 skipped。format、lint、typecheck、README整合性、docs build、lock整合性、diff checkも成功した。
- standard bytes不変、fresh/project/prefix rich report、rich+bin、rich+graph sectionsの単回build、rich+budget、JSON/comparison JSONのrich無視、project lockの`lock_changed`、sanitized rich renderer failureを回帰テストで固定した。

次のタスク:

- F-010 第2段 slice 3として、`--report`のhelp、README、Docs、local-wheel E2Eを公開契約として完成させる。

### 2026-08-12: F-010 第2段 slice 1 pure rich summary view/renderer

状態: `done`

変更:

- `rich_report.py`に、fresh-install、project-lock、existing-prefixを閉じたenumで表す`RichAnalysisView`と、比較専用の`RichComparisonView`を追加した。viewはinput kind、build policy（prefixはunknown）、completeness、warning code/count、distribution count、canonical global bytes、distribution-owned aggregate、最大5件のnormalized distribution name/owned bytesだけを保持する。
- comparison viewはversionを持たないtop changesと件数を保持し、project-lockだけ`lock_changed` boolを表す。raw requirements、path、resolved version、lock identity、context fingerprintはviewにもrendererにも渡さない。
- rendererは共通terminal-safe table primitivesでASCII summaryを生成し、`Showing N of M`、top 5、canonical totalとdistribution-owned aggregate、aggregateとcanonicalの差（duplicate ownershipによる非一致）を明示する。CLI、README、Docs、JSON schema、既存text出力は変更していない。
- source modelを再構成/再検証し、改ざんされたsource/result viewや不整合なviewをrenderer境界で拒否する。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache uv run --locked pytest tests/test_rich_report.py tests/test_text_render.py tests/test_render.py tests/test_diff_render.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-rich-cache uv lock --check
git diff --check
```

結果:

- focused testsは71 passed、全体は908 passed / 2 skipped。format、lint、typecheck、README整合性、docs build、lock整合性、diff checkも成功した。
- fresh/project/prefix input kind、prefix build policy unknown、warning/completeness、aggregate非一致、top five、comparison top changes、project `lock_changed`、raw version/path/requirement/lock identityの非保持、forged view拒否に加え、top rowsとowned aggregate、top changesとaggregate changeの再集計不変条件をnetwork不要のunit testで固定した。

次のタスク:

- F-010 第2段 slice 2として、既存text/JSON契約を保ったopt-in CLI接続を設計・実装する。

### 2026-08-12: F-010 第1段 terminal-safe CLI text primitives

状態: `done`

変更:

- `safe_display()`を追加し、printable ASCIIはbytesを維持したまま、Unicode category `C`の制御文字を`?`へ、その他の非ASCIIを固定の`\\u`/`\\U` ASCII escapeへ正規化した。terminal、locale、`COLUMNS`は参照しない。
- 形状検証、空表、右寄せを共通化したtable primitivesを追加し、通常analysis、diff、footprint、root contributionのhuman text tableへ適用した。
- `--bin`のscript pathとdependency explanation内のroot/name/version/pathを共通display経由にし、ANSI escape、改行、wide Unicodeがhuman text reportの制御や列幅を壊さないようにした。JSON rendererとCLI channel/color/layoutの契約は変更していない。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-cache uv run --locked pytest tests/test_text_render.py tests/test_render.py tests/test_diff_render.py tests/test_footprint_render.py tests/test_root_contribution_render.py tests/test_explanation.py tests/test_budget_render.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-f010-cache uv lock --check
git diff --check
```

結果:

- focused renderer testsは102 passed、全体は900 passed / 2 skipped。format、lint、typecheck、README整合性、docs build、lock整合性、diff checkも成功した。
- malicious script pathとinstalled metadata version、control/ANSI、wide Unicode、empty table、right alignment、`COLUMNS`/`TERM`/`LC_ALL`非依存を回帰テストで固定した。

次のタスク:

- F-010 第2段として、既存textとJSONを不変に保つopt-in rich summary reportを設計する。

### 2026-08-12: 利用者向けDocs Homeの実用化

状態: `done`

変更:

- Homeを装飾中心のランディングページから、最短の実行コマンド、実際のCLI report、用途別の導線を先頭に置く実用ページへ簡潔化した。
- 実出力例は、fixed `AnalysisResult`から現行rendererが生成するreportをfixtureとして固定し、Homeのコードブロックと逐語一致することをテストした。実行環境により変わるpackage名・解決結果・sizeを固定値であるかのように示さない。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-docs-cache uv run --locked pytest tests/test_pages_docs.py -q` — 5 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-docs-cache make docs-check` — 成功（MkDocs strict build。MaterialのMkDocs 2.0に関するupstream noticeはstderrのみで、exit status 0）。
- `git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-mkdocs-cache uv run --locked pytest tests/test_pages_docs.py tests/test_ci_workflow_example.py -q` — 10 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-mkdocs-cache make ci-check`、`uv lock --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-mkdocs-cache make test` — 887 passed, 2 skipped。
- GitHub Pages run `31586566899` — strict buildとdeployが成功。`configure-pages@v5`、`upload-pages-artifact@v4`、`deploy-pages@v4`、`setup-uv@v6`のNode.js 20廃止予告は、現時点ではGitHubによりNode 24で実行され、deploy挙動は維持された。

### 2026-08-12: 利用者向けDocsのMkDocs移行

状態: `done`

変更:

- 既存の単一静的ページを、`docs/user-guide/`配下のMkDocs向け利用者ガイドへ分割した。
- Home、Getting started、package measurement、locked project analysis、baseline/budget、CI、measurement contract、安全性と制約を、READMEの既存公開CLI契約に基づいて記述した。
- READMEの導入から重複していた`uv tool install`コードブロックを除去し、Pages Docsへの導線を維持した。
- MkDocs Materialの検索、light/dark切替、コードコピー、セクションnavigationを有効化し、既存Pagesのnavy/teal/warm配色を引き継いだHome、価値カード、最短導線を追加した。
- Pages workflowをstrict buildとdeployへ分離し、build jobは`contents: read`、deploy jobだけが`pages: write`と`id-token: write`を持つ構成にした。通常`make ci-check`にも一時出力先へのstrict Docs buildを接続した。

検証:

- `make docs-check` — 成功（MkDocs strict build）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-docs-cache uv run --locked cog --check --diff README.md`、`git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-docs-cache uv run --locked pytest tests/test_ci_workflow_example.py -q` — 5 passed。安定版のCI例を`uvx uv-packsize`へ統一し、READMEと利用者ガイドが同一の検証fixtureを逐語で埋め込むことを確認した。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-mkdocs-cache uv run --locked pytest tests/test_pages_docs.py tests/test_ci_workflow_example.py -q` — 9 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-mkdocs-cache make ci-check`、`uv lock --check`、`git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-mkdocs-cache make test` — 886 passed, 2 skipped。
- Desktopと390×844 viewportでHomeを表示し、navigation、CTA、カード、code copy、dark theme、mobile reflowを確認した。Material iconが文字列表示されないようemoji extensionを追加した。
- GitHub Pages run `31585790543` — strict buildとdeployが成功し、`https://kj-9.github.io/uv-packsize/`で検索、navigation、CTA、locked-project導線を確認した。
- 通常CI run `31585790594` — lock、lint、Python 3.10〜3.14の全jobが成功した。

### 2026-08-12: `0.2.0` 安定版リリース準備

状態: `in_progress`（通常CIとrelease workflowの外部実行待ち）

変更:

- `0.2.0a5`の公開後検証を踏まえ、version、lock root package、artifact verifier、version固定テストをPEP 440安定版`0.2.0`へ同期した。
- PyPI classifierを`Development Status :: 5 - Production/Stable`へ更新し、READMEとGitHub Pagesからα限定の`--prerelease=allow`案内を除去した。以後は`uvx uv-packsize requests`が安定版をそのまま選択する。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-stable-cache uv run --locked pytest tests/test_pages_docs.py tests/test_uv_packsize.py tests/test_verify_build.py -q` — 119 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-stable-cache make ci-check`、`uv lock --check`、`git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-stable-cache make test` — 883 passed, 2 skipped。
- 一意なtemporary output directoryで`uv build --no-sources --out-dir <temporary-directory>`と`uv run --locked python scripts/verify_build.py <temporary-directory>` — `0.2.0` wheel/sdistを検証。

### 2026-08-09: `0.2.0a5` αリリースとGitHub Pages Docs準備

状態: `done`

変更:

- `v0.2.0a4`は既存tagのため上書きせず、baseline writer修正と利用者向けDocsを含む次のPEP 440 pre-releaseを`0.2.0a5`とした。
- `docs/site/`に静的な利用者向けDocsを追加した。最短の`uvx uv-packsize requests`、反復利用向け`uv tool install`、JSON、locked project analysis、CI budgetと安全境界を案内する。
- `pages.yml`は`docs/site`だけをartifactにし、`contents: read`、`pages: write`、`id-token: write`の最小権限でGitHub Pagesへdeployする。PRではdeployせず、`main`へのDocs/workflow変更と手動実行だけを対象にする。
- READMEの導入も`uvx uv-packsize requests`を先頭にし、Pages Docsへリンクした。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-pages-cache uv run --locked pytest tests/test_pages_docs.py tests/test_uv_packsize.py tests/test_verify_build.py -q` — 119 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-pages-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-pages-cache make test` — 883 passed, 2 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-pages-cache uv lock --check` — 成功。
- 一意なtemporary output directoryで`uv build --no-sources --out-dir <temporary-directory>`と`uv run --locked python scripts/verify_build.py <temporary-directory>` — `0.2.0a5` wheel/sdistを検証。
- Ruby YAML parseと`git diff --check` — 成功。
- main通常CI run `31288646137` — lock、lint、Python 3.10〜3.14の全jobが成功。
- Pages deploy run `31288646146` — `https://kj-9.github.io/uv-packsize/`へ成功。repositoryのPages sourceをGitHub Actionsへ有効化した。
- GitHub pre-release [`v0.2.0a5`](https://github.com/kj-9/uv-packsize/releases/tag/v0.2.0a5)を検証済みcommit `e8983cd`から作成した。publish run `31288688885`はtag/SHA/version、品質、Python 3.10〜3.14、artifact build/verify、PyPI trusted publishingをすべて成功した。
- PyPIの`0.2.0a5`を`uvx --prerelease=allow uv-packsize --version`で実行し、version表示を確認した。通常の`uvx uv-packsize`はpre-releaseを既定で選ばないため、DocsとREADMEに明示opt-inを記載した。

### 2026-08-09: αリリース blocker — absolute temporary parent trust traversal

状態: `done`（外部公開操作を除く）

原因と判断:

- GitHub ActionsのPython 3.12でabsolute temporary targetを開く際、`/tmp`のようなforeign sticky intermediate directoryを最終parentと同じstrict trust policyで判定していた。そのため、symlink拒否とdescriptor identity照合が成功しても`changed-parent`へ誤って正規化されていた。
- 全ancestorで`lstat`、`O_NOFOLLOW`、device/inode照合を維持しつつ、中間componentだけは従来trustedなdirectoryに加えてsticky directoryを通過可能とした。実際に書き込む最終parentは従来どおりstrict policyを要求する。identity/type failureは`changed-parent`、trust failureは`unsafe-parent`として分離した。

テスト:

- foreign sticky intermediate traversalの成功、foreign writable non-sticky directoryの拒否、strictでない最終parentの`unsafe-parent`、absolute temporary targetの成功をunit testで固定した。
- Python 3.12でbaseline writer unit testを実行し、GitHub Actionsの対象versionと同じ経路を確認した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked --python 3.12 pytest tests/test_baseline_write.py -q` — 18 passed。
- `docker run --rm -v <repository>:/work -w /work ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --locked --python 3.12 pytest tests/test_baseline_write.py -q` — 18 passed（Linux `/tmp` sticky ancestor）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 881 passed, 2 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check` — 成功。

### 2026-08-09: `0.2.0a4` αリリース再準備

状態: `done`（外部公開操作を除く）

変更:

- `0.2.0a3`のGitHub pre-releaseはPython 3.12のbaseline writer `changed-parent` failureによりCIで停止し、PyPI publishは実行されなかった。既存tagを付け替えず欠番として残す。
- 修正版を`0.2.0a4`として再公開する方針に従い、project metadata、lock root package、artifact verifier、およびversionを固定する回帰テストを同期した。

検証:

```bash
uv lock --check
make ci-check
make test
uv build --no-sources --out-dir <temporary-directory>
uv run --locked python scripts/verify_build.py <temporary-directory>
git diff --check
```

結果:

- lock check、format/lint/typecheck、README生成整合性、whitespace checkは成功した。
- 全880テストが成功し、2件は既存skipだった。
- temporary out directoryのwheelとsdistはName `uv-packsize`、Version `0.2.0a4`、metadata、archive構造、entry pointを検証した。

### 2026-08-09: `0.2.0a3` αリリース再準備

状態: `superseded`（Python 3.12 baseline writer `changed-parent` failureによりpublish前に停止）

変更:

- `0.2.0a2`のGitHub pre-releaseはLinuxのbaseline writer failureによりCIで停止し、PyPI publishは実行されなかった。既存tagを付け替えず欠番として残す。
- 修正版を`0.2.0a3`として再公開する方針に従い、project metadata、lock root package、artifact verifier、およびversionを固定する回帰テストを同期した。

検証:

```bash
uv lock --check
make ci-check
make test
uv build --no-sources --out-dir <temporary-directory>
uv run --locked python scripts/verify_build.py <temporary-directory>
git diff --check
```

結果:

- lock check、format/lint/typecheck、README生成整合性、whitespace checkは成功した。
- 全880テストが成功し、2件は既存skipだった。
- temporary out directoryのwheelとsdistはName `uv-packsize`、Version `0.2.0a3`、metadata、archive構造、entry pointを検証した。

### 2026-08-09: αリリース blocker — Linux baseline atomic writer feature 検出

状態: `done`

- 一部のLinux CPythonでは`os.lstat`が`os.supports_dir_fd`へ載らず、実際に安全に使えるdescriptor-relative write経路まで`unsupported-platform`で停止していた。
- no-follow metadata取得を、Python APIが個別にcapabilityを示す`os.stat(..., dir_fd=..., follow_symlinks=False)`へ統一した。事前検査は`stat`の`dir_fd`と`follow_symlinks=False`双方を必須にし、parent/target/tempのsymlink拒否、descriptor identity照合、atomic publish/recoveryの契約を維持した。
- `lstat`の`dir_fd` capabilityが広告されないplatformをmonkeypatchして書込み成功を確認し、no-follow capabilityがなければopen前に安全側で拒否する回帰を追加した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-baseline-linux-fix-cache uv run --locked pytest tests/test_baseline_write.py -q` — 17 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-baseline-linux-fix-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-baseline-linux-fix-cache make test` — 880 passed, 2 skipped。
- `git diff --check` — 成功。

### 2026-08-09: αリリース blocker — CPython 3.12 parent identity regression

状態: `done`（外部公開操作を除く）

原因と判断:

- `v0.2.0a3`のGitHub Actions（Ubuntu `/usr/bin/python3.12`、CPython 3.12.3）では、absolute `/tmp/.../baseline.json` のwriteで`_open_parent()`が`changed-parent`となった。fresh baseline、project-lock baseline、CLI doubleを含む6件が同じatomic writer failureで失敗した。
- Linux CPython 3.11/3.12では、`os.lstat(path, dir_fd=fd)`が実際に動作する一方、`os.lstat`は`os.supports_dir_fd`に含まれない。`supports_dir_fd`だけをこのno-follow primitiveの可否根拠にせず、native `lstat`を使う必要がある。
- a3で導入した`os.stat(..., dir_fd=fd, follow_symlinks=False)`への置換は、同じno-follow目的でも上記runnerでparent identity照合を通さなかった。atomicity/TOCTOU保証を弱めるfallbackは採用せず、`lstat`へ戻して`open`/`link`/`unlink`だけをadvertised `dir_fd` operationとしてopen前に検査する最小修正とした。parent/target/tempのsymlink拒否、device/inode identity照合、atomic publish、failure recoveryは維持する。

テスト:

- `lstat`が`supports_dir_fd`に広告されないLinux CPython 3.12相当でも、writerが`lstat(..., dir_fd=...)`を使って成功する回帰を追加した。core `dir_fd` operationが未広告ならopen前に拒否する回帰も維持した。
- Linux Docker CPython 3.11.15、3.12.3、3.13.14、3.14.7で、`tests/test_baseline_write.py`、fresh local-wheel baseline write、project-lock baseline writeを実行し、各19 passed。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-a3-baseline-cache UV_PROJECT_ENVIRONMENT=/private/tmp/uv-packsize-a3-baseline-venv make test` — 880 passed, 2 skipped。
- 同じisolated environmentで`make ci-check`、`uv lock --check`、`git diff --check` — 成功。

### 2026-08-09: `0.2.0a2` αリリース再準備

状態: `superseded`（Linux baseline writer failureによりpublish前に停止）

変更:

- `0.2.0a1`のGitHub pre-releaseはCIで失敗し、PyPI publish前に停止した。既存tagを付け替えず欠番として残す。
- 修正版を`0.2.0a2`として再公開する方針に従い、project metadata、lock root package、artifact verifier、およびversionを固定する回帰テストを同期した。

検証:

```bash
uv lock --check
make ci-check
make test
uv build --no-sources --out-dir <temporary-directory>
uv run --locked python scripts/verify_build.py <temporary-directory>
git diff --check
```

結果:

- lock check、format/lint/typecheck、README生成整合性、whitespace checkは成功した。
- 全878テストが成功し、2件は既存skipだった。
- temporary out directoryのwheelとsdistはName `uv-packsize`、Version `0.2.0a2`、metadata、archive構造、entry pointを検証した。

### 2026-08-09: `0.2.0a1` αリリース初回準備

状態: `superseded`（CI失敗によりpublish前に停止）

変更:

- PyPIの最新公開版`0.1.1`と、source/lockの未公開`0.1.2`を確認した。Phase 2〜6の大きな機能追加を最初に公開する先行版は、PEP 440の`0.2.0a1`とした。
- `pyproject.toml`、`uv.lock`、artifact verifierとその回帰テストを`0.2.0a1`へ同期し、`Development Status :: 3 - Alpha` classifierを追加した。
- publish workflowはrelease tagを明示checkoutする。`v<project version>`とのtag一致、および解決したtag commitと`GITHUB_SHA`の一致を確認してから、`uv lock --check`と`make ci-check`を実行する。対応Python matrixのtestとartifact verifierも通過した場合だけtrusted publishingへ進む。
- release、tag、push、GitHub Actionsの実行、PyPI publishは実施していない。既存`dist/`に`0.1.2` artifactが残るため、verifierが想定どおりrejectした。既存artifactは削除せず、一意なtemporary out directoryでrelease candidate artifactを検証した。

検証:

```bash
uv lock --check
make ci-check
make test
uv build --no-sources --out-dir <temporary-directory>
uv run --locked python scripts/verify_build.py <temporary-directory>
ruby -e 'require "yaml"; YAML.safe_load(File.read(".github/workflows/publish.yml"), permitted_classes: [], permitted_symbols: [], aliases: true)'
git diff --check
```

結果:

- lock check、Ruff format/lint、ty、README生成整合性、YAML parse、whitespace checkは成功した。
- 全878テストが成功し、2件は既存skipだった。
- temporary out directoryのwheelとsdistはName `uv-packsize`、Version `0.2.0a1`、metadata、archive構造、entry pointを検証した。

### 2026-08-09: αリリースCIのpre-release policy同期

状態: `done`

変更:

- CIの`uv lock --check`は、lockの`prerelease-mode = "disallow"`とuvの既定値`if-necessary-or-explicit`が異なるため、lockの再解決を試みて失敗した。
- projectの`[tool.uv]`に`prerelease = "disallow"`を明示し、lockの解決policyをproject設定として固定した。lock root metadata testでprojectとlock双方の値を検証する。

検証:

```bash
uv lock --check
make ci-check
make test
git diff --check
```

結果:

- lock check、format/lint/typecheck、README生成整合性、whitespace checkは成功した。
- 全878テストが成功し、2件は既存skipだった。

### 2026-08-02: P5-01 `uv workspace metadata` schema investigation and compatibility boundary

状態: `done`

調査根拠:

- ローカルの`uv 0.11.3 (45da18ac3 2026-04-01 aarch64-apple-darwin)`に対し、既存のfreshな`uv.lock`を使って`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv workspace metadata --locked --offline --no-progress --preview-features workspace-metadata`を実行した。network accessもprojectへの書込みも行わず、stdoutはJSONだけ、stderrはresolution progressだけだった。preview feature flagを省略した場合は、experimental warningがstderrへ追加されたがstdout bytesは同一だった。
- CLI helpはこのcommandの出力を「not yet stable」と明記する。JSONのtop-levelは`schema`、`workspace_root`、`requires_python`、`conflicts`、`members`、`resolution`であり、`schema.version`はnumeric versionではなく`"preview"`だった。`members`のentryは`name`、`path`、`id`、`resolution`はopaque IDからnodeへのmapである。通常package nodeには`name`、`version`、`source`、`kind: "package"`、`dependencies`、`dependency_groups`、artifact fieldsがあり、group nodeは`kind: {"group": NAME}`を持つ。dependency edgeは`id`と任意の`marker`を持つ。
- このprojectではroot package nodeが`dependency_groups`からgroup nodeへ参照し、group nodeがgroup dependencyへ参照した。したがって、command outputはlock graphの候補ではあるが、selected groups/extrasを表す安定したpublic analysis inputとして扱うこともできない。workspace/member path、source、node IDにはabsolute local path、index URL、潜在的なcredentialが混入し得る。

設計判断:

- 採用可能なstable machine-readable schemaは現時点で存在しない。`schema.version == "preview"`はschema compatibility boundaryではないため、`uv-packsize`の通常CLI、baseline、comparison JSON、budget/CIにこのcommandのJSONを入力しない。P5-01は「preview schemaを非対応として固定する」調査設計タスクであり、code/fixtureは追加しない。
- 将来のproduction adapterは、上流がnumericで安定と宣言するschema versionを返す場合だけ、その値をallowlistで受ける。未知のversion、欠損/非numeric version、unknown required semantic、stdout JSON以外、nonzero exitはsafe typed failureとして扱い、推測やpartial graphへのfallbackをしない。adapterは`--locked`でlock freshnessを検査し、version確認とJSON parse/shape validationをsubprocess boundaryへ閉じ込める。
- どうしてもpreviewを検証する開発専用opt-inを追加する場合は、`uv` executableを完全一致`0.11.3`に固定し、`--preview-features workspace-metadata`、`--locked`、`schema.version == "preview"`、required object/array/string shapeをすべて検査する。これは上流更新時に必ずrejectする短期compatibility pinであり、公開resultやbaselineにpreview-derived graphを保存しない。絶対path、source URL、opaque ID、uv diagnosticsを利用者向けoutputへ反射しない。
- 次の最小単位はP5-02のproject/lock analysis input/context contractである。root package、workspace member、dependency group、extras、Python/platform、lock identityをどうpublic resultへ安全に投影するかを、workspace-metadata adapterを実装せずに決める。stable schemaの提供後に、そのcontractへisolated adapter/parserとnetwork-free fixtureを接続する。

検証:

- `uv --version` — 成功（`uv 0.11.3`）。
- `uv help workspace metadata` — 成功。previewかつoutputがunstableであること、`--locked`/`--frozen`/`--dry-run`の存在を確認。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv workspace metadata --locked --offline --no-progress --preview-features workspace-metadata` — 成功（stdout JSON 47,568 bytes、stderr progressのみ）。
- `jq`による上記JSONのtop-level、member、package/group node、dependency edge shape inspection — 成功（network-free）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make test` — 成功（782 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv lock --check`、`git diff --check` — 成功。

次のタスク:

- P5-02: project/lock analysis input/context contractを設計する。stable versioned schemaが提供されるまで、`uv workspace metadata` adapterを実装しない。

### 2026-08-02: P5-02 project/lock analysis input/context contract

状態: `done`

設計判断:

- project/lock analysisは、既存のpositional requirementsによる`fresh-install`、観測専用の`existing-prefix`とは別のinput familyである。将来公開するanalysis JSONは新しい`analysis-result-v3`だけで`context.input_kind: "project-lock"`を表し、v1/v2のfield、意味、bytesを変更しない。v3のcontextは少なくとも`root_package`（PEP 503 normalized name）、`workspace_member`（選択されなければ`null`）、`dependency_group_selection`（`none` / `explicit` / `all`）、実効`dependency_groups`、実効`extras`、解決済み`python_version`、`platform`、`architecture`、`path_flavor`、`case_rule`、`uv_version`、`build_policy`、`compile_bytecode`、`resolution_strategy`、`lock_identity`を持つ。`workspace_member`を選ぶ場合は`root_package == workspace_member`とする。root projectを選ぶ場合は`workspace_member: null`とする。group/extrasは名前をPEP 503正規化してset semanticsで昇順にし、group modeだけではなく実際に有効だったgroup集合も保存する。これにより`--all-groups`の後日のworkspace変化を同じ入力と誤認しない。
- `lock_identity`は、読み取ったlock bytesの`sha256`を`uv-packsize/project-lock/v1\\0lock\\0`でdomain separationした64桁hex fingerprintとする。mtime、size、absolute/relative path、workspace root、lock node ID、source URLはidentityに含めず、公開しない。fingerprintは内容を復元しないが、同一lockの相関は可能であるため比較JSONと同じく共有時に相関情報になることをREADMEで明記する。manifest/lockのraw bytes、TOML値、source/index URL、credential、environment variable、uv diagnostic、member path、opaque node IDをanalysis result、baseline、comparison JSON、text report、error messageへ出力しない。
- project modeのpublic contextは、resolverが何を選んだかではなく、選択と測定条件を記録する。`root_package`、member、group mode/effective groups、extras、Python/platform/path semantics、uv version、build/bytecode policy、resolution strategyはcomparison compatibilityの対象とする。一方、`lock_identity`とresolved distributionsは比較対象の変化そのものであり、互換性fingerprintから除外する。したがって、同じproject selection/target条件でlock更新により依存versionやsizeが変わったbaselineは比較でき、lock fingerprintの相違は将来のcomparison JSON v2で値を出さない`lock_changed: bool`としてだけ示す。resolver source条件を安全に比較できるstableなsymbolic aliasが上流schemaまたは明示CLIから得られるまでは、project modeは未知のsource semanticsを受理しない。将来追加するaliasは既存`index_identifiers`と同じASCII symbolic alias制約を持ち、compatibility対象へ加える。
- project/lock modeのCLI入力はambient current directoryや`UV_PROJECT`等から推測しない。将来の成功経路は`--project PYPROJECT --lockfile UV_LOCK`をともに必須とし、任意の`--workspace-member NAME`、repeatable `--group NAME`または`--all-groups`、repeatable `--extra NAME`、既存の明示`--python`、明示target platform optionを受ける。`--group`と`--all-groups`は排他であり、どちらもない場合の実効groupsは空集合で`dependency_group_selection: "none"`とする。`--workspace-member`、group、extraはsafe identifierの構文を先に検証し、project上の存在/有効性はallowlistした直接`uv.lock` readerで検証する。memberはpathで指定しない。`--locked`相当はproject modeの必須内部policyであり、lock更新・解決の暗黙fallbackを設けない。
- project modeはpositional requirementsと`--prefix`に排他とする。fresh analysisと同じ測定policyを使うため`--allow-build`、`--python`、target platform、text analysis optionsはその意味を維持する。baseline read/write、comparison JSON、budgetはproject-lock schemaと互換なbaselineに限り許可する。requirements v1 baseline、existing-prefix v2 baseline、project-lock v3 baselineのcross-kind比較はしない。`--comparison-json`はproject-lock比較用の新しいclosed schema v2のみを使い、既存`comparison-result-v1`はbyte不変とする。
- direct readerは明示pathをregular fileとして安全に一度読む。symlink、special file、open前後identity race、size/encoding/TOML/lock format errorは、raw pathやcontentを含めないtyped `project-input-*` failureへ正規化する。allowlist外の`uv.lock` `version`/`revision`、required fieldの欠損・型不正、unknown required semantic、曖昧なpackage/selectionは、partial graph、member-path推測、raw TOML/lock fallbackを使わず`unsupported-project-lock`として失敗する。readerは`uv workspace metadata`を起動も入力もせず、P5-01の`schema.version: "preview"`は常に試行対象外である。

exit / stdout contract:

- optionの不足・構文不正・排他違反はfilesystem/uvを呼ばずexit 2、stdout空とする。対象は`--project`/`--lockfile`の片方だけ、project modeとpositional requirements/`--prefix`の組合せ、`--group`と`--all-groups`、unsafe member/group/extra/platform selector、comparison/write optionの既存排他である。
- 明示project/lock inputの安全読込、parse、選択検証、allowlist外または未知semanticなlock schemaの失敗はexit 3、stdout空、固定code/fieldだけをstderrへ出す。存在しないmember/group/extra、unknown required source semanticもこの区分に含める。`uv workspace metadata`は実行しない。`uv --locked`の実行、target environment作成、wheel install、inventoryの失敗は既存どおりexit 1で、diagnosticをsanitizeする。stale lockは`--locked`実行失敗としてexit 1にする。
- project-lock baselineのinput-kindまたはcomparison compatibility coreが異なる場合はexit 4、stdout空、既存同様の安全なreason identifierだけをstderrへ出す。lock identityだけの差はexit 4にせず、完了比較（incompleteならpartial）としてexit 0にする。budget violationは既存exit 5を維持する。成功時だけtext report、analysis JSON v3、comparison JSON v2のいずれか一つをstdoutへ出し、progressはstderrへ出す。

実装順序と前提:

| ID | 状態 | 依存 | 最小対象 | 完了条件 |
|---|---|---|---|---|
| P5-03a | `done` | P5-02 | `models.py`、pure JSON renderer、schema v3、baseline parser/projection、diff/comparison JSON v2、unit/golden tests | adapter/CLIなしで`ProjectLockContext`、safe label/fingerprint validation、effective selection、v3 closed schema、v3 baseline read/write、compatibility coreと`lock_changed`をpureに固定した。v1/v2 analysisとcomparison v1はbyte不変。 |
| P5-03b | `done` | P5-03a | isolated explicit project/lock reader、network-free fixtures | `uv workspace metadata`を使わず、explicit native `--project`/`--lockfile`を安全に一度だけ読み、`uv.lock` `version = 1`かつ`revision = 3`と閉じたrequired field subsetだけをparseした。project root/member/group/extra selection、domain-separated lock identity、unknown schema/semantic・曖昧なselectionのsafe rejectionを実装した。 |
| P5-03c1 | `done` | P5-03b | validated snapshot handoff、temporary staging、`uv sync` adapter、adapter unit tests | readerで検証済みのproject/lock bytesだけをprivateなsnapshotとして標準名`pyproject.toml`/`uv.lock`へstagingし、`UV_PROJECT_ENVIRONMENT=<unique absolute temporary prefix>`、`uv sync --project <staging directory> --locked --no-install-project --no-default-groups`とselection由来の明示group/extra flagsだけで同期する。入力を再読・変更せず、`--lockfile`/`--frozen`/workspace metadataを使わない。wheel-only/allow-build policyを保持し、成功・失敗を問わずstagingとtargetをfinallyで削除する。CLI/README/real networkは含めない。 |
| P5-03c2 | `done` | P5-03c1 | CLI option/guard、analysis v3、baseline/comparison v2、budget/write boundary、CLI unit tests | explicit `--project`/`--lockfile`とselectionをCLIへ接続する。input/selection failureはexit 2/3、`uv sync`・inventory failure（stale lockを含む）はexit 1、comparison incompatibilityは4、budget violationは5に保ち、成功時だけ一つのtext/analysis JSON v3/comparison JSON v2をstdoutへ出す。raw path/content/source URL/credential、staging/target path、`uv` diagnosticを出力しない。v1/v2 analysisとcomparison v1のbytes、cross-kind rejection、baseline writeの既存atomicityを維持する。 |
| P5-03c3 | `done` | P5-03c2 | local-wheel E2E、README、全体回帰 | offline local wheelsと`--find-links`だけでlocked project selection、read-only original inputs、default-group非選択、explicit group/extra、temporary prefix inventory、stale lock cleanup、redaction、JSON/stdout/exit 0--5、lock-only diffの`lock_changed`、baseline/write/budgetを検証する。READMEへ実装済みのv3/v2 public contractとlocal root未測定の制約を記載し、full checkを記録する。 |

P5-03b/P5-03cのschema・fixture方針:

- P5-03bのproduction readerは、`uv.lock` `version = 1`かつ`revision = 3`と、テストで固定した閉じたfield subsetだけを受ける。新しいversion/revision、unknown fieldが意味に必要なsource/marker/dependency表現、duplicateまたは曖昧なpackage/selectionは、互換と推測せずexit 3のsafe typed failureへ正規化する。対応を広げる変更は、fixture・parser・公開compatibility判断を同じ変更単位で追加する。
- fixtureはnetwork不要の最小`pyproject.toml`/`uv.lock`組をrepository内に保持し、accepted v1/revision3、unknown version/revision、required field欠損・型不正、unknown semantic、duplicate/ambiguous selection、unsafe file/read race、raw値のredactionをunitで固定する。P5-03cのE2Eはlocal wheelsと`--find-links`だけを使い、明示project/lockのread-only性、locked input failure、stale-lock後を含むtemporary directory cleanup、schema v1/v2/comparison v1 byte不変、v3/v2のproject-lock contractを検証する。
- `uv workspace metadata`はP5-03b/P5-03cで起動・parse・fixture化しない。P5-01で拒否した`schema.version: "preview"`は、上流が将来stable schemaを提供してもこの直接readerの互換範囲を自動的に変えない。

P5-03cの実行契約と初期スコープ:

- 公開`uv`経路は、unique absolute temporary directory内のstaging directory（標準名`pyproject.toml`と隣接する`uv.lock`を含む）を`--project`へ渡し、`UV_PROJECT_ENVIRONMENT`を別のunique absolute temporary prefixに設定して実行する`uv sync --project <staging directory> --locked --no-install-project --no-default-groups`である。`--group`/`--all-groups`と`--extra`はreaderが検証したselectionからだけ明示追加する。`--lockfile` optionは使わず、stagingでlock filenameを固定する。`--frozen`はfreshnessを検査しないため使わない。
- readerからinstallerへのhandoffは、成功した安全読込時のvalidated project/lock bytesだけをprivate snapshotとして行う。original inputを再読しないため、検証したselectionと異なる後続内容を同期しない。snapshot、staging path、temporary prefix、command argument、raw TOML/source URL/credential/opaque IDはresult、baseline、diagnostic、test assertion failureに公開しない。original project/lockとその親directoryは作成・更新・削除しない。
- `uv sync`はstale lock失敗時にも`UV_PROJECT_ENVIRONMENT`下にtarget骨組みを残し得る。staging directoryとtarget prefixは、success、`uv` failure、inventory failure、例外のすべてでfinally cleanupする。cleanup失敗もsanitized operational failureとして扱い、先行する`uv` failureをraw diagnosticで覆い隠さない。user指定inputや既存prefixをcleanup対象にしない。
- staged rootはlock上の`source = { editable = "." }`であっても、`--no-install-project`によりinstallしない。local root packageはlock bytesだけから安全・再現可能に測定できず、root build codeの実行も避けるため、P5-03c初期対象ではない。結果はroot自身を測定済みと主張せず、root sizeを含めない。local path/VCS/workspace member sourceを含むrootまたはdependencyはreaderのsupported subset外としてexit 3で拒否する。
- default wheel-only policyではsource buildを許可せず、`--allow-build`だけが`uv sync`へbuild許可を伝える。adapterはambient project discovery、ambient `UV_PROJECT*` selection、workspace metadata、network fixtureへfallbackしない。local E2Eではoffline local wheel indexを明示する。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make test` — 成功（782 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv lock --check`、`git diff --check` — 成功。

次のタスク:

- P5-03a: project/lock context、schema、baseline/comparison projectionをpureに実装する。上流stable schemaが未提供でも実行できるが、公開CLI optionとmetadata adapterは追加しない。

### 2026-08-02: P5-03a project/lock pure context and projection

状態: `done`

実装:

- `ProjectLockContext`と`DependencyGroupSelection`を追加した。root/member/group/extraはPEP 503正規化した安全なlabelとして保持し、`none`はempty groups、`explicit`はnon-empty groups、`all`はempty effective groupsも許可する。workspace memberを選ぶ場合はroot packageと同一であることを不変条件とした。lock identityは64桁のdomain-separated SHA-256 fingerprintだけを受け、path、lock bytes、mtime、source URL、opaque node IDをmodelへ持ち込まない。
- Python/platform/architecture/uv/resolution strategyはURL、path、credential separator、whitespaceを含められないASCII symbolic tokenに制限し、v3 baseline decoderも同じ制約をfingerprint前に適用する。v3/v2 schemaは外部schema registryを必要としないself-containedな定義として、v1のclosed distribution/warning/side/change/nonreconciliation constraintsを複製し、v3 contextのselection modeとeffective group数の整合もschemaで固定する。
- v1/v2 serializerには変更を加えず、schema v3専用のpure rendererとclosed analysis schemaを追加した。v3 baseline parser/projectionはproject contextを安全なcomparison modelへ縮約して読書きし、既存v1/v2 baseline parserの入力・出力を維持する。
- project-lock baseline同士はselection/target/policy/resolution strategyが一致すれば比較可能とし、lock identityは互換性coreから除外した。comparison result v2専用rendererはidentity差をraw fingerprintなしの`lock_changed` boolでのみ表す。comparison v1 rendererは変更していない。
- project model/selection、v3 round-trip、lock-only changeとcontext mismatchを固定するunit testを追加し、build verifierに新pure renderer modulesを含めた。metadata adapter、project/lock file I/O、atomic writer、CLI/READMEは実装していない。

検証:

- `uv run --locked pytest tests/test_project_lock_projection.py tests/test_models.py tests/test_json_render.py tests/test_baseline.py tests/test_diff.py tests/test_comparison_json_render.py -q` — 成功（217 passed）。
- `uv run --locked ruff format --check ...`、`uv run --locked ruff check ...` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make ci-check`、`make test`、`uv lock --check`、`make verify-build`、`git diff --check` — 成功（796 passed, 2 skipped）。

次のタスク:

- P5-03b: explicit `--project`/`--lockfile`だけを読む、`uv.lock` v1/revision3限定の直接readerを実装する。P5-01で拒否した`uv workspace metadata`のpreview outputは使わず、未知`uv.lock` schemaは安全側で拒否する。

### 2026-08-02: P5 direct `uv.lock` readerへの再計画

状態: `done`

設計判断:

- P5-03bの上流stable metadata schema待ちは解除し、P5-02で固定したexplicit `--project`/`--lockfile` input contractに限定した直接`uv.lock` readerへ置き換える。P5-03aの`ProjectLockContext`、analysis JSON v3、baseline/comparison JSON v2、compatibility coreと`lock_changed`のpure contractは変更しない。
- readerは`uv.lock` format全体の汎用実装ではない。`version = 1`かつ`revision = 3`と、root/member/group/extra selectionに必要なfield subsetだけを明示allowlistし、未知schema、未知の必須semantic、曖昧なselectionを受理しない。未対応入力を新しい互換入力と見なしたり、raw TOMLから補完したりしない。
- P5-03bは明示inputのread-only readerまでを扱う`todo`とする。installer/CLI接続のP5-03cは、既存projectを変更せずtemporary installationへlockを適用する`uv`の公開・検証可能な経路が未確立なため`blocked`を維持する。どちらも`uv workspace metadata`を起動・parse・fixture化しない。

### 2026-08-02: P5-03b explicit project/lock direct reader

状態: `done`

実装:

- `uv_packsize/project_lock_reader.py`に、明示されたnative `Path`の`pyproject.toml`と`uv.lock`をそれぞれ一度だけread-onlyで読むadapterを追加した。symlink/special fileを拒否し、open前`lstat`とopen後`fstat`のdevice/inode照合、nonblocking bounded read、UTF-8/TOML失敗のtyped safe failureを固定した。raw path、TOML、OS diagnosticはerror/resultに保持しない。
- readerは`uv.lock`の`version = 1`と`revision = 3`だけを受理し、必要なproject root package、package source、dependency group、optional extraのsubsetを検証する。project/lock top-level、project/package table、root dependency entryはclosed key allowlistであり、root entryは`source = { editable = "." }`、non-root entryはsingle known keyのnon-empty string `registry` sourceだけを受ける。未知・欠損field、未知source、重複package、project/lockのgroup/extra不一致、未知/重複selectionを推測せず拒否する。
- 読み込み時はleafだけでなく全parent componentのsymlinkを拒否し、open前`lstat`、open後`fstat`、read後の`fstat`/`lstat`でdevice/inode/mode/size/mtime/ctimeを照合する。これにより観測可能な同一inode in-place rewriteも拒否するが、同一descriptorのimmutable snapshotを作るものではない。最終照合後の変更やmetadataを保持した攻撃的な並行書換えまでは防げないため、stableなtrusted directoryの明示inputだけを対象にする。
- 成功結果はPEP 503正規化済みのroot/member/group/extra selectionと、`uv-packsize/project-lock/v1\\0lock\\0`でdomain-separateしたlock bytesのSHA-256 fingerprintだけを返す。workspace metadata、CLI、`uv`実行、network、installer接続は追加していない。analysis JSON v1/v2とcomparison JSON v1は変更していない。
- network-freeの最小project/lock fixtureとunit testsを追加し、acceptance、all-groups effective set、root/member/group/extra validation、unknown/incomplete top-level/package/root-dependency schema、root editable path、non-root source、secret-like raw TOMLのredaction、leaf/parent symlink・special file、open前後のfile replacementとread後に観測できるsame-inode rewriteを固定した。build verifierは新reader moduleのwheel/sdist含有を要求する。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked pytest tests/test_project_lock_reader.py tests/test_project_lock_projection.py tests/test_verify_build.py -q` — 成功（38 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make test` — 成功（818 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py dist`、`git diff --check` — 成功。

次のタスク:

- 当時はP5-03cをblockedとした。後続の2026-08-08再調査で公開`uv sync`経路を確認し、この判断は同日のP5-03c再計画で更新した。

### 2026-08-08: P5-03b input hardening

状態: `done`

変更:

- readerのsupported subsetを実装でもclosedにした。`pyproject.toml`/`uv.lock` top-level、project/package table、root lock dependency entryのunknown fieldを拒否し、必要なfield欠損も拒否する。rootはexactな`source = { editable = "." }`だけ、non-rootはsingle-keyかつnon-empty exact stringの`registry` sourceだけを受理する。
- project/lockのpathはleafだけでなく全parent componentのsymlinkを拒否する。read前の`lstat`、open後とread後の`fstat`、read後の`lstat`でdevice/inode/mode/size/mtime/ctimeを照合し、観測可能なsame-inode in-place rewriteを`changed-file`として拒否する。
- descriptor上のimmutable snapshotは作らない。最終metadata照合後の変更やmetadataを意図的に保持する並行書換えは防げない残余制約として、roadmapとともに明記した。explicit inputはstableなtrusted directoryに置く。

テスト:

- unknown/incomplete project・lock top-level/package/root-dependency schema、root editable value、non-root source key、secret-like raw input非反射、parent symlink、read後same-inode rewriteをnetwork-free regression testで固定した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked pytest tests/test_project_lock_reader.py tests/test_project_lock_projection.py tests/test_verify_build.py -q`、`uv run --locked ty check` — 成功（49 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache make test` — 成功（829 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py dist`、`git diff --check` — 成功。buildはsandbox外cacheではなくtask-local `UV_CACHE_DIR`を指定した。

### 2026-08-08: P5-03b 実project input互換性の修正

状態: `done`

変更:

- readerのclosed allowlistを、実際のPEP 621 project shapeに広げた。root name、optional dependency group、dependency groupだけを読み、既知の非selection project metadata、standardな`[build-system]`、`[tool]` tableはtable shapeを検証して無視する。`dynamic = ["optional-dependencies"]`はselectable extraをfileから確定できないため拒否する。
- `uv.lock` `version = 1` / `revision = 3`の既知top-level context（`requires-python`、`options.prerelease-mode`）、non-root package dependency/artifact record、root package metadataを明示allowlistした。URL、hash、artifact metadataはresultへ保持せず、unknown keyは拒否する。root metadataが`requires-dev`または`provides-extras`を持つ場合はroot dependency group/extraと一致することを確認する。
- root editable `.`、non-root registry source、selection validation、raw input non-reflection、symlinkおよびTOCTOU hardeningは変更していない。公開CLIはまだ存在しないためREADMEの公開CLI契約は変更していない。

テスト:

- network-free minimal fixtureをv1/revision 3 context込みのshapeへ更新した。repository自身の`pyproject.toml`/`uv.lock`をexplicit pathで読むacceptanceを追加し、`all_groups`が`dev`を返すことを固定した。
- dynamic extras、unknown build-system key、unknown lock option、root metadataとroot groupの不一致をsafe typed failureとして固定した。

検証:

- `uv run --locked pytest tests/test_project_lock_reader.py -q` — 成功（38 passed）。
- `uv run --locked ruff format --check uv_packsize/project_lock_reader.py tests/test_project_lock_reader.py`、`uv run --locked ruff check uv_packsize/project_lock_reader.py tests/test_project_lock_reader.py`、`uv run --locked ty check uv_packsize/project_lock_reader.py tests/test_project_lock_reader.py` — 成功。

### 2026-08-08: P5-03b default dependency group selection guard

状態: `done`

変更:

- `[tool.uv]`の`default-groups`は、`uv run`/`uv sync`時の暗黙dependency group選択を変える。explicit readerのselection APIはcallerが指定した`none`/explicit/`all`だけを表すため、値を解釈・補完せず、存在自体を`invalid-project`/`dependency-group`のtyped safe failureとして拒否する。
- `default-groups = ["..."]`と`default-groups = "all"`の両方を拒否する。`tool.uv.dev-dependencies`はdev groupのrequirements内容を補うlegacy設定であり、groupを選択する設定ではないため、この修正だけを理由に拒否対象へ広げない。`tool.uv.dependency-groups`もgroupのPython制約であってselectionではない。
- `tool.uv`全体をclosed allowlistにはしない。readerがselectionへ影響しない一般設定（`managed`など）を読むだけで拒否しない一方、tool/uv tableのshape不正は従来どおりsafe failureとする。

テスト:

- network-free regressionで`default-groups`のlist/`"all"`入力が`ProjectLockInputError`になること、secret-like raw TOMLがerror textへ反射しないこと、無関係な`tool.uv.managed`がaccepted subsetを壊さないことを固定した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked pytest tests/test_project_lock_reader.py -q` — 成功（41 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked ruff format --check uv_packsize/project_lock_reader.py tests/test_project_lock_reader.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked ruff check uv_packsize/project_lock_reader.py tests/test_project_lock_reader.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked ty check uv_packsize/project_lock_reader.py tests/test_project_lock_reader.py` — 成功。

### 2026-08-08: P5-03c temporary project/lock install path replan

状態: `in_progress`（P5-03c1のみ）

調査で確定した実行経路:

- explicit project/lockをtemporary installへ適用する公開経路は、validated project/lock bytesをunique temporary staging directoryの標準名`pyproject.toml`/`uv.lock`へ配置し、そのstaging directoryを`--project`へ渡す`UV_PROJECT_ENVIRONMENT=<unique absolute temporary prefix>`と`uv sync --project <staging directory> --locked --no-install-project --no-default-groups`を用いる方法である。group/extraはreaderで検証済みのselectionから対応する明示flagだけを追加する。`--lockfile` optionは使わず、staging内の標準名`uv.lock`を用いる。`--frozen`はlock freshnessを検査しないため不可とする。
- original project/lockは読み直さない。P5-03c1はsuccessful reader snapshotのbytesをinternal-onlyでhandoffし、そのsame bytesをstageして実行する。これにより、検証後のinput変更を別内容のinstallとして扱わない。input、親directory、ambient project/workspace stateは作成・更新・削除しない。raw bytes、path、source URL、credential、opaque ID、staging/target path、command、`uv` diagnosticsをpublic result/baseline/stdout/stderrへ含めない。
- stale lockを含む`uv sync`失敗でもtarget prefixの骨組みが残り得る。stagingとtemporary prefixをsuccess、sync failure、inventory failure、unexpected exceptionのすべてでfinally cleanupする。cleanup failureはsanitized operational failureとして記録し、先行するfailureのraw diagnosticを出さない。user inputまたはexisting prefixをcleanup対象にしない。
- root entryの`source = { editable = "." }`はstaged projectに残るが、`--no-install-project`によりrootをinstallしない。local root sizeはlock bytesだけでは再現できず、local build codeを実行し得るため初期P5-03cでは測定対象外である。local path/VCS/workspace dependency sourceはsupported subset外としてsafe rejectする。wheel-onlyを既定として維持し、source buildは`--allow-build`の明示opt-inだけにする。

分割した実装順序:

| ID | 状態 | 範囲 | 完了条件 |
|---|---|---|---|
| P5-03c1 | `done` | snapshot handoff、staging writer、temporary `uv sync` installer adapter、adapter unit tests | validated bytesだけを標準名でstageし、selection/policyを安全なargvへ投影する。freshnessは`--locked`で確認し、`--frozen`/`--lockfile`/workspace metadataを使わない。cleanup、input immutability、sanitized adapter failure、local root非installをnetwork不要のtest doubleで固定する。CLI、README、real `uv` E2Eは含めない。 |
| P5-03c2 | `in_progress` | CLI/public boundaryと既存analysis/baseline/comparison/budget/writeとの接続 | option guardをexternal I/O前に実行し、exit 0--5、stdout one-document/text、redaction、cross-kind baseline rejection、v1/v2 analysisとcomparison v1 byte不変をCLI unit testで固定する。 |
| P5-03c3 | `todo` | offline local-wheel E2E、README、full verification | `--find-links`のみでreal `uv sync`のselection、temporary inventory、stale-lock cleanup、input immutability、write/budget/diff/lock_changedを確認し、実装済みpublic contractとlocal root未測定をREADMEへ反映する。 |

P5-03c全体のDefinition of Done:

- project/lock schema v3とcomparison v2だけがproject-lock resultを表し、v1/v2 analysisとcomparison v1のschema/bytesを変更しない。
- usageはexit 2、safe reader/input failureは3、`uv sync`/inventory/cleanupを含むoperational failureは1、incompatible baselineは4、budget violationは5、成功は0とし、失敗時stdoutは空にする。
- local-wheel E2Eはnetworkを使わず、staging/temporary prefix cleanupとoriginal inputのbyte不変を成功と失敗の両方で検証する。stale lockがtargetを残す挙動をcleanup testで明示的に扱う。
- READMEはP5-03c3で実装済みのCLIだけを記載する。今回の再計画では未実装optionを先行公開しない。

次のタスク:

- P5-03c1: validated snapshotを唯一のstaging sourceとするtemporary installer bridgeを実装する。

### 2026-08-08: P5-03c1 temporary installer bridge

状態: `done`

実装:

- `project_lock_reader`の公開`ProjectLockSelection`は変更せず、同一の安全読込で検証済みのproject/lock bytesだけを保持する非公開snapshotを追加した。公開readerはsnapshotからsafe selectionだけを返すため、raw bytes、input path、source URL、credentialをpublic resultへ追加していない。
- `project_lock_installer`に、非公開snapshotだけを受け取るtemporary bridgeを追加した。unique temporary root内の`stage/pyproject.toml`と`stage/uv.lock`へsnapshot bytesを配置し、`stage` directoryを`--project`へ渡して、別のabsolute temporary targetを`UV_PROJECT_ENVIRONMENT`へ設定する`uv sync --project <staging directory> --locked --no-install-project --no-default-groups`を起動する。review P1修正として、子processのenvironmentはambient `os.environ`を複製せず、PATH（Windowsではprocess起動に必要な最小OS変数も）、temporary root内のprivate `UV_CACHE_DIR`だけから構築し、`UV_PROJECT_ENVIRONMENT`と`UV_NO_CONFIG=1`を明示する。private cacheもtemporary rootと一緒にcleanupする。従ってambient `UV_*`、`VIRTUAL_ENV`、index/source/build controls、外部configはselectionまたはbuild policyを上書きできず、staged `[tool.uv]`の一般設定もこのadapterのselection/build contractに影響しない。
- argvは検証済みselection由来の`--group`/`--all-groups`/`--extra`とbuild policy由来のwheel-only `--no-build`だけを追加する。`--lockfile`、`--frozen`、workspace metadata、original inputの再読は行わず、isolated stageをcwdにする。root projectは`--no-install-project`により未install・未測定のままとする。
- success、`uv sync` failure、inventory failure、unexpected exception、cleanup failureのすべてでtemporary rootをcleanupする。typed bridge errorにはreasonだけを保持し、raw path、command、`uv` diagnostics、credential-like exception textを反射しない。user inputとambient/existing prefixはcleanup対象にしない。

テスト:

- network-free test doubleで、same-read snapshot bytesのstandard-name staging、`uv`の`--project` directory contract、explicit/all groupとextra/build policy argv、`--locked`、`--no-install-project`、`--no-default-groups`、`--no-build`、`--lockfile`/`--frozen`非使用、isolated cwd、temporary cleanup、input/ambient prefix不変、sanitized failureを固定した。review P1の回帰として、`UV_PROJECT`、`UV_WORKING_DIR`、`UV_CONFIG_FILE`、`UV_NO_CONFIG=0`、index/source/build variables、active virtual environment、Pip/Python controls、および未知の`UV_*`を毒入れしても、子environmentはallowlist、temporary root内のprivate cache、強制した`UV_NO_CONFIG=1`だけであり、wheel-only/allow-build argvが明示policyのままになることを確認する。
- artifact verifierの必須module集合に`project_lock_installer.py`を追加し、wheel/sdistのいずれにもbridge実装が含まれないbuildを拒否する回帰テストを追加した。
- real `uv` E2E、CLI、READMEはP5-03c2/P5-03c3の範囲として未変更である。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_project_lock_reader.py tests/test_project_lock_installer.py -q` — 成功（51 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked ruff format --check uv_packsize/project_lock_reader.py uv_packsize/project_lock_installer.py tests/test_project_lock_reader.py tests/test_project_lock_installer.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked ruff check uv_packsize/project_lock_reader.py uv_packsize/project_lock_installer.py tests/test_project_lock_reader.py tests/test_project_lock_installer.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-cache uv run --locked ty check uv_packsize/project_lock_reader.py uv_packsize/project_lock_installer.py tests/test_project_lock_reader.py tests/test_project_lock_installer.py` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-03c1-fix-cache uv run --locked pytest tests/test_project_lock_installer.py -q`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-03c1-fix-cache uv run --locked ruff format --check uv_packsize/project_lock_installer.py tests/test_project_lock_installer.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-03c1-fix-cache uv run --locked ruff check uv_packsize/project_lock_installer.py tests/test_project_lock_installer.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-03c1-fix-cache uv run --locked ty check uv_packsize/project_lock_installer.py tests/test_project_lock_installer.py` — 成功（10 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-artifact-cache uv run --locked pytest tests/test_verify_build.py -q`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-artifact-cache uv run --locked ruff format --check scripts/verify_build.py tests/test_verify_build.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-artifact-cache uv run --locked ruff check scripts/verify_build.py tests/test_verify_build.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-artifact-cache uv run --locked ty check scripts/verify_build.py tests/test_verify_build.py`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-artifact-cache make verify-build` — 成功（3 passed。wheel/sdistに`project_lock_installer.py`を含むことを確認）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5-final-ci-cache make ci-check`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-final-test-cache make test`、`UV_CACHE_DIR=/private/tmp/uv-packsize-p5-final-lock-cache uv lock --check` — 成功（全体: 845 passed, 2 skipped）。
- `git diff --check` — 成功。

次のタスク:

- P5-03c2: CLI/public boundaryと既存analysis/baseline/comparison/budget/writeへinstaller bridgeを接続する。

### 2026-08-08: P5-03c2 project/lock CLI and public-boundary connection

状態: `done`

実装:

- `--project`と`--lockfile`を同時必須の明示inputとして追加し、positional requirements、`--prefix`、`--site-packages`/`--case-rule`、`--group`と`--all-groups`、selection optionだけの単独指定を、reader・baseline/config read・`uv`起動より前にusage errorへ固定した。review P1修正として、`--workspace-member`、repeatable `--group`/`--extra`はCLI境界でPEP 503のsafe package-name構文だけを受理し、path、URL、whitespaceなどのunsafe値をexit 2・stdout空としてreader/installerより先に拒否する。project/lock内容に依存する存在・重複・実効selectionの検証と正規化は既存のallowlist readerがexit 3で担う。
- readerのprivate same-read snapshotをinstaller bridgeへ渡し、temporary prefixのinventoryを`ProjectLockContext`へ投影してschema v3分析JSONを描画する。`--python`はbridgeの明示`uv sync --python`引数として渡し、root packageをrequirementsとして公開resultへ混ぜない。analysis v1/v2 rendererは変更していない。
- project-lock baselineはv3 JSONを既存のatomic writerへ渡せるようにし、comparisonはschema v2 renderer、budgetはv3 baselineを受理する既存domain policyを使う。v1 fresh baseline、v2 existing-prefix、comparison v1の解析・出力・比較経路は分岐したまま維持する。cross-kind baselineは既存compatibility checkでexit 4になる。
- project input failureはpath/TOMLを反射しないexit 3、bridge/`uv sync` failureはexit 1、usage guardはexit 2、incompatible baselineはexit 4、budget violationはexit 5へ正規化した。project JSON/comparison JSONでは成功時だけstdoutへ一つのJSON documentを出し、progressとsafe diagnosticはstderrへ送る。

テスト:

- network-free CLI doublesで、schema v3 one-document stdout、input path非反射、v3 baseline write、v2 comparison、v3 budget violation、usage guardのI/O先行防止、unsafe workspace-member/group/extra syntaxのexit 2・stdout空とreader/installer未呼出、reader exit 3、bridge exit 1を追加した。
- real `uv sync`/local wheel E2E、README公開契約、全体回帰はP5-03c3へ残す。root packageが`--no-install-project`により未測定である制約を含むE2E確認は、このunit-only taskでは行わない。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5c2-cache uv run --locked pytest tests/test_json_render.py tests/test_diff.py tests/test_diff_render.py tests/test_project_lock_cli.py tests/test_project_lock_installer.py tests/test_project_lock_reader.py tests/test_project_lock_projection.py tests/test_baseline.py tests/test_comparison_json_render.py tests/test_budget.py tests/test_baseline_write.py tests/test_uv_packsize.py -q` — 成功（383 passed）。
- `uv run --locked ruff format --check uv_packsize/cli.py uv_packsize/baseline_write.py uv_packsize/budget.py uv_packsize/project_lock_installer.py tests/test_project_lock_cli.py`、`uv run --locked ruff check ...`、`uv run --locked ty check ...` — 成功。
- `git diff --check` — 成功。
- review P1 selector guard: `UV_CACHE_DIR=/private/tmp/uv-packsize-p5c2-selector-cache uv run --locked pytest tests/test_project_lock_cli.py -q` — 成功（14 passed）。`uv run --locked ruff format --check uv_packsize/cli.py tests/test_project_lock_cli.py`、`uv run --locked ruff check uv_packsize/cli.py tests/test_project_lock_cli.py`、`uv run --locked ty check uv_packsize/cli.py tests/test_project_lock_cli.py`、`git diff --check` — 成功。

次のタスク:

- P5-03c3でoffline local-wheel E2E、README、全体検証を実施して公開契約を完了する。

### 2026-08-08: P6-02 最小GitHub Actions workflow契約

状態: `done`

実装:

- READMEに、既存CLIのproject/lock modeだけを使うコピー可能なGitHub Actions workflowを追加した。workflowは`contents: read`だけを要求し、`--project pyproject.toml --lockfile uv.lock`、review済みbaseline、`--budget-config pyproject.toml`、`--comparison-json`を明示する。
- comparison JSONは`mktemp -d`で作るprivate temporary directoryだけへ出力し、job exit時にcleanupする。`GITHUB_STEP_SUMMARY`へはinput kind、lock changed、global baseline/current/delta bytesという固定schema fieldだけを出力し、JSON全体、path、requirements、lock contentsを公開しない。
- custom Action、PR comment、secret、write permission、baseline自動作成/更新は採用しない。fork pull requestを含む通常のpush/PR eventでread-onlyに実行でき、baseline refreshは別のreview済み変更として行う。
- workflow fixtureとREADMEがbyte-for-byteで一致すること、least privilege、明示input、private comparison JSON、固定summary field、baseline write/comment integrationの不在をnetwork不要のtestで固定した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p6-02-cache uv run --locked pytest tests/test_ci_workflow_example.py -q` — 成功（4 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p6-02-cache make ci-check` — 成功（Ruff format/lint、ty、README cog整合性）。
- `git diff --check` — 成功。

次のタスク:

- P6-03でprovenance要件を上流issue草案として整理する。issue作成はユーザーの明示承認を得るまで行わない。

### 2026-08-08: P6-03 provenance要件の上流Issue草案

状態: `done`

実装:

- [`uv-provenance-upstream-issue-draft.md`](./uv-provenance-upstream-issue-draft.md)に、上流へ提出するための日本語の論点整理と英語本文draftを追加した。GitHub上のIssue検索、作成、更新、投稿は実施していない。
- 草案は、preview / unstableな`uv workspace metadata`を通常CLI・baseline・CI比較の入力にしない現行境界と、diagnostic・cache・filesystem副作用からbuild実績を推測しない方針を記録した。numeric stable schema、公開JSON Schema/versioning、root/member/group/extra selection、marker/conflict guidance、selected artifactとcandidateの分離、per-run build outcome/provenance、redacted machine-readable diagnostics、stable locked semanticsを上流要件として明確化した。
- path、source URL、opaque ID、credential、任意のuntrusted metadataを公開identityまたはdiagnosticへ反射しない要件を明記し、`uv tree --show-sizes`のinstalled-size化、custom Action、`pydistcheck` API integrationを非目標として分離した。
- 調査根拠として、公式の[workspace metadata internals](https://docs.astral.sh/uv/reference/internals/metadata/)と[lockfile versioning](https://docs.astral.sh/uv/concepts/resolution/#lockfile-versioning)を草案にリンクした。stable featureが上流で提供・対応versionが確定するまで、F-007は未解決とする。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p6-03-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `git diff --check` — 成功。

次のタスク:

- なし。Phase 6は3 / 3を完了した。Phase 7はロードマップに未定義であり、次の実装範囲は再計画で決定する。上流Issueの作成・更新・投稿はユーザーの明示承認後にだけ行う。

### 2026-08-08: P5-03c3 offline project/lock E2E, documentation, and verification

状態: `done`

実装:

- `tests/test_project_lock_e2e.py`で、repository内で生成するlocal wheelhouseだけを使って、real `uv lock --offline`と公開CLIのstaged `uv sync`を実行するE2Eを追加した。defaultのgroup未選択、明示`--group test`、明示`--extra feature`が選択するdistributionとschema v3 contextを確認し、root project自身がinventoryに含まれないこともdistribution集合で固定した。
- 同testは入力project/lock bytesの成功時不変性、temporary staging/prefix cleanup、v3 baseline writeのstdout bytes一致、comparison JSON v2、同じlockの`lock_changed: false`、whitespaceのみを変えたlockの`lock_changed: true`、budget violation exit 5を確認する。stale lockはexit 1・stdout空で、path、raw input、`uv` diagnosticを反射せずcleanupする。usage 2、reader failure 3、cross-kind baseline incompatibility 4も実行し、exit 0--5の公開境界をnetworkなしで固定した。
- fully isolated child `uv sync`がユーザーの既定cacheへfallbackしないよう、installerはtemporary root内のprivate `UV_CACHE_DIR`を明示する。このcacheはstaging/targetと同じfinally cleanup対象であり、ambient `UV_CACHE_DIR`は継承しない。
- READMEのcog生成helpを更新し、explicit project/lock input、group/extra selection、reader/staging/locked-sync boundary、wheel-only/build opt-in、schema v3/comparison v2、baseline/budget利用、lock fingerprintの相関性、local root未測定を公開contractとして記載した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5c3-cache uv run --locked pytest tests/test_project_lock_installer.py tests/test_project_lock_e2e.py -q` — 成功（14 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5c3-cache make ci-check` — 成功（Ruff format/lint、ty、README cog整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5c3-cache make test` — 成功（869 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-p5c3-cache uv lock --check`、`git diff --check` — 成功。

次のタスク:

- P6-01: 上流連携の費用対効果を再評価する。

### 2026-08-02: P4-04f CLI policy input/precedence implementation

状態: `done`

実装:

- `--budget-config PATH`、`--max-total BYTES`、`--max-increase BYTES`、`--incomplete-policy {fail,allow-partial}`を接続した。sourceは明示pathだけを読み、configのpolicyをbaseとしてCLIで明示したfieldだけを上書きする。source table不在はpolicyなし、明示empty tableとCLI incomplete policy単独はevaluation/renderされるno-opとして保持する。
- policy入力はprefix modeでexternal I/O前にusage errorとし、source failureをpath/TOML/valueを含まないexit 3へ正規化した。effective increase limitのbaseline必須判定はsource読込後・baseline読込/uv起動前に行う。
- fresh resultをbaseline projectionへ変換してpolicyを評価し、comparison branchの既存early returnを維持した。textではprimary analysis/diff reportの後にbudget reportを一度だけ追加する。JSON/comparison JSONはpass時に既存bytesを保ち、violation時はstdoutを空、safe budget reportとsummaryをstderr、exit 5とした。policy violationではbaselineを書き込まない。
- READMEへsource/field precedence、no-op/incomplete、baseline requirement、JSON/write/prefix/exit contractとCI command exampleを追加した。CI workflow自体は次の統合作業として未変更である。

テスト:

- unit CLI coverageでhelp、全4種のprefix guard、source failure precedence、source+CLI field overrideとcross-field保持、no-op、incomplete fail/allow-partial、max increase comparison JSON failure、text report ordering/stderr summary、policy pass時のanalysis/comparison JSON bytes+stderr不変、write suppressionを追加した。
- local wheel E2Eでreal `uv` installのconfig total violation、JSON stdout empty、stderr report、baseline write suppressionを追加した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_budget.py tests/test_budget_config.py tests/test_budget_config_source.py tests/test_budget_render.py tests/test_uv_packsize.py tests/test_local_wheel_integration.py -q` — 成功（201 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（782 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check` — 成功。

次のタスク:

- P5-01で`uv workspace metadata`の対応schemaを調査・固定する。

### 2026-08-02: P4-04e CLI policy input/precedence contract

状態: `done`

設計判断:

- policyを有効にする入力は、明示的な`--budget-config PATH`、`--max-total BYTES`、`--max-increase BYTES`、`--incomplete-policy {fail,allow-partial}`の4種だけとする。`--budget-config`はP4-04dの`load_budget_policy()`へそのまま渡す`pyproject.toml` pathであり、cwdの既定`pyproject.toml`、親directory探索、環境変数、複数config file、profile、includeは導入しない。`--max-total`と`--max-increase`はcanonical global logical bytesの非負base-10整数で、`MAX_BASELINE_INTEGER`までを受理する。`--incomplete-policy`はdomain enumの2値だけを受理する。公開flagとconfig fieldは異なる名前でも、同じ`BudgetPolicy`の3 fieldを指定する。
- sourceは一つだけで、mergeはconfig policyへのCLI field overrideに限る。`--budget-config`のtableが存在する場合はその3 fieldをbaseとし、CLIで明示された同名fieldだけが置換する。CLIにないfieldはconfig値を維持し、config sourceがない場合の未指定fieldは`BudgetPolicy`のdefaultへ落とす。したがって`--max-total`とconfigの`max_increase_logical_bytes`は同時に有効になり得る一方、別file、cwd discovery、environment、既存baselineから値を補うことはない。config section不在はsource policyなし、明示空tableまたはlimitを持たないCLI指定はexplicit no-op policyであり、空tableを設定エラーや暗黙のdefault sourceと扱わない。
- policyはfresh-install analysisだけを対象にする。`--prefix`とpolicy入力の任意の組合せはusage errorとし、prefix inventory/JSON v2へbudgetを後付けしない。`--write-baseline`はfresh policyと併用できるが、policy evaluationがpassするまでbaselineをrender/publishしない。`--baseline`は従来どおり任意であり、effective policyが`max_increase_logical_bytes`を持つときだけ必須とする。baselineの自動発見、writeしたbaselineを同runでcomparison inputにすること、既存-prefix schema v2との比較は許可しない。total-only policyの`--baseline`比較は従来どおり可能だが、budget判断はcurrent canonical global totalだけを使い、baseline側のincompleteness/nonreconciliationを追加判断しない。
- `max_increase` policyでは、既存の互換性検査に成功したfresh v1 comparisonからcanonical global logical-size deltaだけを読む。distribution-owned aggregate delta、distribution別delta、nonreconciliationはbudget authorityにしない。comparisonなし・incompatible comparison・baseline read failureをpartialなbudget evaluationへすり替えない。comparisonなしはusage error、互換性なしは既存exit 4、baseline load failureは既存exit 3とする。
- effective policyが存在するときだけ`analysis_result_to_baseline()`後に`evaluate_budget()`を呼ぶ。limitを一つでも持つpolicyでは、defaultの`fail`がcurrent incompletenessを、increase policyではbaseline/currentを合わせたcomparison incompletenessをviolationにする。`allow-partial`はincomplete violationだけを抑止し、観測済みcanonical total/deltaの上限判定は続ける。policy非選択時は、既存のincomplete analysis/comparisonのexit 0と表示を完全に維持する。explicit no-op policyはevaluation/render対象だが、limitを持たないためcompletenessを評価せずpassする。
- option shapeのguard（`--prefix`排他、数値/choice、既存baseline/write/json排他）はconfig read、baseline read、`uv`検出、venv作成より先に固定順で実行する。次に`--budget-config`だけをreadし、P4-04d source errorまたはP4-04c field errorはraw path/TOML/valueを出さないexit 3へ正規化する。effective `max_increase`の`--baseline` requirementはsourceを解決してから、baseline readと外部processより前にexit 2で判定する。この順序により、invalid sourceを無視して別sourceやdefaultへfall backしない。
- policyなしでは全existing CLIのstdout、stderr、exit code、baseline write timing、JSON schema/bytesを変更しない。policyありのtext modeではprimary analysis reportまたはdiff reportの後にpure `render_budget_report()`を一度だけappendする。policy violationは測定/比較自体が完了した判断結果なので、text stdoutにはprimary resultと`Result: FAIL`/violation sectionsを残し、exit 5と固定のsanitized stderr summaryを返す。install/analysis/render/source/baseline failureとは区別し、raw config/baseline/package/pathを診断へ反射しない。
- `--json`と`--comparison-json`は既存のversioned documentだけをstdoutへ出すclosed contractのままとする。policy pass時のstdout bytesは対応するpolicyなしcommandと完全一致し、budget用JSONやtext sectionを追加しない。policy violation時はstdoutを空にし、exit 5とsafeなbudget report/summaryだけをstderrへ出す。`--write-baseline`併用時もviolationではtargetを作成・更新しない。これによりmachine-readable stdoutは成功時だけconsumeでき、analysis JSON v1/v2とcomparison JSON v1のschemaを変更しない。
- exit codeは、成功（policyなし、no-op、pass、allow-partialを含む）を0、既存operational failureを1、usageを2、baseline/config source/atomic write failureを3、incompatible comparisonを4、budget violationを5と固定する。source/CLI parse、incomplete、limit超過、no-op、text/JSON/comparison JSON/writeの組合せをP4-04fのnetwork-free unit/local-wheel testで固定する。READMEへのpublic option/CI exampleは実装完了時にだけ追加し、この設計taskでは未実装optionを公開しない。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_budget.py tests/test_budget_render.py tests/test_budget_config.py tests/test_budget_config_source.py -q` — 成功（後続CLI接続が依存するpure policy/source contractの回帰なし）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（769 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check` — 成功。

次のタスク:

- P4-04fでこの契約をCLI/README/testへ接続する。P4-04eは設計だけを更新し、未実装のpublic CLI help/READMEやJSON schemaを先行変更していない。

### 2026-07-31: P4-04d pyproject budget policy source

状態: `done`

実装:

- `uv_packsize/budget_config_source.py`に、explicit native `Path`だけを受ける`load_budget_policy()`を追加した。cwd/upward discovery、環境変数、複数sourceのmergeは行わない。`[tool.uv-packsize.budget]`不在は`None`、明示空tableはP4-04c parserへ渡すexplicit no-op policyとした。
- fileは1 MiBまでにbounded readする。通常のsymlink followを維持しつつ、`O_NONBLOCK`付きdescriptorを開いて`fstat`でregular fileを要求し、事前`stat`とのdevice/inode一致を確認してから`os.read`する。これによりregular fileからFIFO等への差し替えでblockせず、regular file同士の差し替えも`changed-file`として拒否する。missing/not-regular/changed/read/size/encoding/TOML/document/table/parser-unavailableを固定の`BudgetPolicySourceError` reasonとsafe sectionだけへ正規化し、path、TOML内容、parser/OS診断を反射しない。nested policy fieldの妥当性はP4-04cの`BudgetPolicyConfigError`をそのまま使う。
- `requires-python >=3.10`を維持するため、3.11+ではstdlib `tomllib`、3.10ではconditional runtime dependency `tomli`を使う。`pyproject.toml`と`uv.lock`へこのconditional dependencyを記録し、artifact verifierへnew moduleを追加した。verifierはruntime dependencyをPEP 508として正規化し、`tomli; python_version < "3.11"`を含むexact multisetをwheel/sdist両方で要求するため、marker欠落・誤り・重複・余分な依存をrejectする。
- 読み込み境界は同一inodeの内容をimmutable snapshotにはしない。identity照合後またはread中のin-place更新は防がない残余制約としてF-009へ記録した。CLI、budget exit code、README、CI workflowは変更していない。

テスト:

- configured/all-field、section不在、明示空table、non-table nesting、parserのunknown field、missing/directory/read/size、UTF-8/TOML failure、symlink target、FIFO/regular replacement race、exact Path、parser-unavailable、forged documentをnetwork-free `tmp_path` testで固定した。secret-like path/content/error textがtyped errorに出ないことを検証した。artifact verifierはnormalized markerの正常系と、marker欠落・誤り・重複・余分な依存の拒否をunit testで固定した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_budget_config.py tests/test_budget_config_source.py tests/test_verify_build.py -q` — 成功（38 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked ruff format --check uv_packsize/budget_config_source.py tests/test_budget_config_source.py scripts/verify_build.py tests/test_verify_build.py`、同filesへの`ruff check`、`uv run --locked ty check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（769 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py dist`、`git diff --check` — 成功。conditional runtime dependency、wheel/sdistへのnew module含有、artifact metadata、installed entry pointを検証した。

次のタスク:

- P4-04eでCLI policy input/precedence contractを設計する。P4-04dのexplicit source adapterを前提に、公開option、source precedence、exit/stdout/stderrを小さく固定してから実装へ接続する。

### 2026-07-31: P4-04c budget policy mapping normalization

状態: `done`

実装:

- `uv_packsize/budget_config.py`に、trusted sourceから得たexact built-in `dict`を受けるpureな`parse_budget_policy()`を追加した。mapping/custom mapping subclassを拒否し、closed snake_case keysだけを許可する。
- 空mappingとmissing fieldは`BudgetPolicy` defaultへ正規化し、明示valueはnonbool exact integerの`0..MAX_BASELINE_INTEGER`またはexact stringの`fail`/`allow-partial`だけを受ける。`None`、bool、integer/string subclass、`IncompleteBudgetPolicy` enum instanceはinput valueとして許可しない。
- `BudgetPolicyConfigError`はraw mapping/key/value/reprを保持せず、stable reasonとknown field enum（unknown/non-string keyは`None`）だけを公開する。mapping、unknown、type、limit range、不正incomplete-policy string、domain constructorの想定外input failureを別reasonへ正規化し、unknown keyをknown-field value validationより先に処理する固定priorityと、resultがsource mutationを保持しない境界を検証した。
- artifact verifierへ新moduleを追加した。config sourceのfile I/O、CLI、JSON schema、exit code、README、CI workflowは変更していない。

テスト:

- no-op/default、全known field、mapping/key/scalar exact-type boundary、unknown key、bool/type、limit range、不正incomplete-policy string、domain constructor fallback、unknown+bad value priority、secret-like key/value/内部例外の非露出、deterministic immutable outcomeをnetwork/I/Oなしで検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_budget.py tests/test_budget_render.py tests/test_budget_config.py -q` — 成功（52 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked ruff format --check uv_packsize/budget_config.py tests/test_budget_config.py`、`uv run --locked ruff check uv_packsize/budget_config.py tests/test_budget_config.py`、`uv run --locked ty check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（748 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py dist`、`git diff --check` — 成功。wheel/sdistへのnew module含有、artifact metadata、installed entry pointを検証した。

次のタスク:

- P4-04dで`pyproject.toml` policy source resolution/file I/O contractを小さく固定する。P4-04cのpure parserだけを接続し、CLI option、budget exit code、README、CI exampleはこの変更単位に含めない。

### 2026-07-31: P4-04b budget pure text presentation

状態: `done`

実装:

- `uv_packsize/budget_render.py`に、exactな`BudgetEvaluation`をimmutable modelの`__post_init__`で再検証してから受ける`render_budget_report()`とsection-onlyの`render_budget_sections()`を追加した。subclassまたはobject forgeryはraw inputを反射しない固定エラーで拒否する。
- reportはcanonical global logical bytesだけがauthorityでありdistribution-owned aggregateはbudget inputではないことを明記する。total/increaseともconfigured時だけ表示し、totalはnon-negative size、increaseのobservedはsigned size、remaining/excessはdeterministicなbinary unitで表示する。
- no-op policy、current/comparison completeness、`fail`/`allow-partial`、PASS/FAIL、canonical orderのviolation sectionを明示する。evaluationがbaseline/diff graphを保持しない境界を維持し、reportはterminal-safe fixed textとscalarだけで構成され、末尾LFを付加しない。
- artifact verifierへ`budget_render.py`を追加した。CLI/config/JSON schema/exit code/READMEは変更していない。

テスト:

- no-op、totalのremaining/excess、negative increaseのsigned/headroom、both limitのviolation order、incomplete FAIL/ALLOW、PASS時のviolation section非表示、section/report equivalence、wrong type/subclass/object forgery、byte determinismとbaseline detail非露出をnetwork/I/Oなしで検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_budget.py tests/test_budget_render.py -q` — 成功（35 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked ruff format --check uv_packsize/budget_render.py tests/test_budget_render.py`、`uv run --locked ruff check uv_packsize/budget_render.py tests/test_budget_render.py`、`uv run --locked ty check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功（Ruff format/lint、ty、README生成整合性）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（731 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py dist`、`git diff --check` — 成功。wheel/sdistへの新module含有、artifact metadata、installed entry pointを検証した。

次のタスク:

- P4-04cでpolicy inputのpure parser/normalizer契約を固定する。CLI/config file I/O、exit code、CI exampleはこの段階では接続しない。

### 2026-07-31: P4-04a budget pure domain model

状態: `done`

実装:

- `uv_packsize/budget.py`に、immutableな`BudgetPolicy`、incomplete policy/violation/error reason enum、sanitized `BudgetEvaluationError`、safeな`BudgetViolation`/`BudgetEvaluation`、pureな`evaluate_budget()`を追加した。空policyは有効なno-opとし、後続のCLI/config層がusageを判断する。
- totalはcurrent baselineのcanonical global logical bytesだけ、increaseは同じcurrent object identityを確認済み`AnalysisDiff`のcanonical global deltaだけで評価する。distribution aggregate/deltaやnonreconciliationはbudget判定に使わない。比較が必要なpolicyでmissing/mismatch/forged inputはraw baseline情報を含まないtyped errorへ正規化する。
- 空policyはcurrentがincompleteでも常にpassする真のno-opとする。少なくとも一つのlimitがある場合だけ、totalではcurrentのみ、increaseではbaseline/current aggregateのincompleteを対象にする。`FAIL`ではincomplete violationを先頭にしつつnumeric violationも保持し、`ALLOW_PARTIAL`ではcompleteness metadataを保持してnumeric判定を続行する。
- policy、violation、evaluationはexact enum、integer range、bool排除、canonical violation order、derived limit/observed/excess/result一致を`__post_init__`で検証し、baseline/diff自体をevaluationへ保持しない。artifact verifierへ新moduleを追加した。

テスト:

- no-op、total/increase/bothの境界、negative delta、missing/mismatch comparison、同値copyと`__eq__`偽装subclassを拒否するcurrent identity、current/baseline/both incompleteのFAIL/ALLOW、total-onlyのbaseline incomplete無視、nonreconciliation時のcanonical global authority、0/MAX境界、determinism/immutability/hash、forged inputとprivacyをnetwork/I/Oなしで検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_budget.py` — 成功（24 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（720 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py dist`、`git diff --check` — 成功。

次のタスク:

- P4-04bでpureなbudget presentation contractを固定する。その後、policy input（CLI/config）、exit code、CI exampleをそれぞれ独立した完了単位として接続する。

### 2026-07-31: P4-03c fresh baseline pure render/atomic writer

状態: `done`

実装:

- `uv_packsize/baseline_write.py`に、exactなfresh `AnalysisResult`/`ResolutionContext`だけを受ける`render_fresh_baseline()`を追加した。既存`render_analysis_json(..., schema_version=1)`のUTF-8 bytes（末尾LFを含む）をそのまま使用し、8 MiB上限と`parse_baseline_json()`/`analysis_result_to_baseline()` parityをI/Oなしで再検証する。serializer、encoding、projection失敗はraw値を反射しない`BaselineWriteError(code, field)`へ正規化する。
- `write_baseline()`はpayload validation後、POSIX、`O_DIRECTORY`、`O_NOFOLLOW`、事前検査可能なrequired `dir_fd` APIsをI/O前に検証する。macOS等で`supports_dir_fd`へ載らない`replace`は実call failureをtypedに正規化する。cwd/root anchorからparent componentを`lstat`、descriptor-relative open、`fstat` identity照合でwalkする。非group/world-writable parentは所有者を問わずtrusted traversal anchorとして許可し、writable parentだけはsticky bitかつeffective UID所有を要求する。既存parentのみを許可し、symlink/non-directory/identity変更、unsafe path component、symlink/special/hardlinked/untrusted targetを拒否する。
- 同一parentのexclusive random 0600 tempはFDをpublishまで保持する。create直後とpublish直前にdescriptorとdirectory entryのdev/inode、regular type、link countを照合し、交換を`changed-temp`として拒否する。partial/EINTR対応write、chmod、file fsync、close、atomic hard-link no-clobberまたはtarget identity再照合後のatomic replace、最終regular/0600検証、parent fsyncを行う。cleanup/close失敗は主失敗をmaskせず、commit後はrollbackせず`committed-cleanup-failed`へ正規化する。
- Windows/dir-FD非対応platformには同等のrace guaranteeを満たすstdlib fallbackを実装できないため、`unsupported-platform`で失敗する。当初設計のWindows atomic visibilityは安全側に縮小した実装上の発見であり、P4-03dのREADME/public contractで明記する。artifact verifierへ新moduleを追加した。

テスト:

- `tests/test_baseline_write.py`で既存JSONとのbyte一致、parse/projector parity、non-fresh/serializer privacy、invalid/oversize payload、roundtrip、no-clobber/overwrite、0600、target/parent symlink・directory拒否、I/O前feature gate、replace unsupported、partial/EINTR write、write failure cleanup/original保存、directory fsync failure後のpublished file保持、type boundaryをnetwork不要で検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_baseline.py tests/test_baseline_write.py` — 55 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 685 passed, 2 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py dist`、`git diff --check` — 成功。

次のタスク:

- P4-03dで`--write-baseline`/`--overwrite-baseline`のCLI、README、local E2Eを接続する。

### 2026-07-31: P4-03b `--comparison-json` CLI/public contract

状態: `done`

実装:

- `--comparison-json`を`--baseline PATH`必須のcomparison output selectorとしてCLIへ接続した。baseline未指定、baselineとの既存排他、shared fresh-input usageはbaseline read、uv検出、temporary environment作成より前にusage errorとなる。既存text comparisonとfresh/existing-prefix analysis JSONの出力経路は変更していない。
- comparison成功時は`AnalysisDiff`をanalysis JSONへのserialize/parseを経由させず、`render_comparison_json()`へ一度だけ直接渡し、JSON documentとrenderer由来の末尾LFだけをstdoutへ出す。progressはstderrのみとし、incomplete comparisonもJSONのcompleteness/warning summaryを保ったexit 0とする。
- comparison JSON renderer失敗はraw payloadやtracebackを反射せず、fixed diagnosticのexit 1/stdout空へ正規化した。baseline load/parseはexit 3、incompatible comparisonはexit 4、usageはexit 2の既存boundaryを維持した。
- READMEにschema v1 link、closed compatibility boundary、analysis-result JSONとの別契約、opaque context fingerprint、global/distribution aggregate・nonreconciliation・completeness、read-only baseline、success-only stdoutとexit 0--4を記載した。

テスト:

- unitでhelp、baseline必須guard、direct diff renderer一回、analysis JSON roundtrip非使用、progress/stdout分離、incomplete success、renderer TypeError/ValueErrorのsafe exit 1、selector指定時のbaseline load exit 3・incompatible exit 4・current operational exit 1を検証した。既存baseline text/fresh JSON/prefix JSON compatibility testも維持した。
- network-free local wheel E2Eで既存baseline fileとのcomparison JSONをparseし、top-level順序、schema/context hash、aggregate totals、full unchanged distribution rows、nonreconciliation/completeness、stderr progress、baseline bytes不変を検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_uv_packsize.py tests/test_local_wheel_integration.py -q` — 106 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 666 passed, 2 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。

次のタスク:

- P4-03cでfresh baselineのpure render/atomic writerを実装する。

### 2026-07-31: P4-03a pure comparison JSON schema/renderer

状態: `done`

実装:

- `comparison-result-v1` のdraft 2020-12 closed schemaと、exactな`AnalysisDiff`だけを受けるpure rendererを追加した。公開documentは固定順の`schema_version`、measurement、opaque context、両side summary、changes、aggregate completenessで構成し、full outer joinのunchanged rowも含める。
- contextは全`BaselineResolutionContext` safe projectionをcanonical compact JSONへ縮約し、`uv-packsize/comparison-context/v1\0` domain prefix付きSHA-256だけを公開する。requirements、個別fingerprint、raw context値は出力しない。
- nonreconciliationはdistribution aggregateとglobal deltaの差から導出し、0では`false`/`null`、非0では固定reasonを出力する。schemaはbaseline/current row sideとkindの整合、boolean/count、signed delta、`2 * MAX_BASELINE_INTEGER`までのnonreconciliation差を表現する。distribution aggregateは多数distributionの合計になり得るため上限でclampしない。
- wheel/sdist artifact検証に新renderer moduleを追加した。analysis JSON v1/v2、CLI、READMEは変更していない。

テスト:

- committed golden、固定key order、empty/zero/incomplete/nonreconciliation、MAX境界、context fingerprintの決定性と全field差、privacy、wrong type、closed schema/rangeをnetwork/I/O不要で検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_comparison_json_render.py -q` — 10 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — Ruff format/lint、ty、README生成整合性が成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 660 passed, 2 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`make build`、`uv run --locked python scripts/verify_build.py`、`git diff --check` — 成功。

次のタスク:

- P4-03bで`--comparison-json`のCLI/public contractを接続する。

### 2026-07-31: P3-04b existing-prefix read-only discovery adapter

状態: `done`

実装:

- `ExistingPrefixEnvironment`と`discover_existing_prefix()`を追加した。既存prefixを実行・変更せず、callerが明示したhost nativeの`PathFlavor`、`CaseRule`、相対site-packages layoutから`ExistingPrefixContext`と決定的な`InventoryLayout`群を構築する。Python、platform、architectureは安全に観測できないためすべて`None`に保つ。`CaseRule`はtrustedなcaller declarationであり、write probeは行わない。
- prefixは`Path`だけを受理し、relative pathはCWD基準でabsolute化する。final lexical symlinkを拒否した後にcanonical physical targetへ固定するため、ancestor symlinkは許容してもreturned layoutはtargetを保持する。site pathは非空・正規化済み・nativeな相対pathだけを受理し、absolute、drive、UNC、NUL、`.`、`..`、空componentを拒否する。各componentを`lstat`してdirectoryかつsymlinkでないことを確認し、lexical/resolved双方のprefix containmentを検証する。
- `ExistingPrefixEnvironment.layouts`はin-process inventory用のtrusted scan handleであり、analysis result/JSONではない。physical pathを含むためdataclass `repr`から除外する。path flavorがhost nativeでない場合はfilesystem access前に拒否する。duplicate/alias layoutは既存の`validated_inventory_layouts()`で決定的に検出する。全失敗は`ExistingPrefixDiscoveryError`のstable codeと固定target tokenだけに正規化する。exception causeは内部に保持され得るため、P3-04cのCLI boundaryは`from None`で公開する。
- Windows native relative componentはinventoryと同じreserved-name/character規則で検証する。ADS colon、control character、`<>:"|?*`、trailing dot/space、`con`/`prn`/`aux`/`nul`/`com1`〜`com9`/`lpt1`〜`lpt9`（extension付きも）をfilesystem access前に拒否する。
- path treeはdescriptor snapshotではないため、discovery中または後続inventory scan中の並行変更を防げないbest-effort validationである。このTOCTOU制約はP3-04cのpublic contractにも明記する。
- build artifact検証のcritical module一覧へadapterを追加した。CLI、README、JSON/schema、解析/graph接続はP3-04cへ残した。

テスト:

- `tests/test_existing_prefix.py`で複数siteの順序不変、host flavor境界、explicit case rule、POSIX/Windows-like不正path、Windows予約名/ADS/control character、prefix/site/intermediate symlink、missing/non-directory/duplicate/alias site、安全なerror、書込みなし、relative prefix canonicalization、ancestor symlink交換後のcanonical layout、`Path` type boundary、reprからのprefix非漏洩、context/layout不変条件、およびinventory analysisへの接続を検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_existing_prefix.py -q` — 成功（33 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（489 passed, 2 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointを検証した。

引き継ぎ:

- 次のタスクはP3-04cとする。read-only adapterをpublic prefix CLI、README、local prefix end-to-end/error contractへ接続する。

### 2026-07-31: P3-04a2 existing-prefix JSON schema v2

状態: `done`

実装:

- `ExistingPrefixContext`専用の閉じたJSON schema v2とpure serializerを追加した。v2 contextは`input_kind: existing-prefix`、空のrequirements/extras/index identifiers、観測済みまたは`null`のPython/platform/architecture、path/case semantics、および未観測・非該当を明示する固定`null` fieldsだけを出力する。raw prefix、site-packages、venv、executable、configuration、credentialは出力しない。
- `analysis_result_to_json_object()`と`render_analysis_json()`に明示的な`schema_version` selectorを追加した。default v1のobject/bytesは不変であり、v1は`ResolutionContext`、v2は`ExistingPrefixContext`以外を明示的な`TypeError`で拒否する。boolおよび未対応versionも拒否する。
- v2 schemaはv1を参照しないself-containedな定義とし、measurement、distribution/file、warning、duplicate ownership、completeness、totalの契約をv1と同じに保った。既存prefix golden、known/null observation、selector/context family rejection、permutation、v1 byte compatibility、閉じたschemaとunsafe field不在をテストした。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_json_render.py -q` — 成功（49 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 成功（456 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointを検証した。

引き継ぎ:

- 次のタスクはP3-04bとする。existing prefixのlayoutと安全な観測contextを、対象Pythonを実行せずread-onlyに収集するadapterを実装する。

### 2026-07-31: P3-04a1 existing-prefix context model

状態: `done`

実装:

- frozen/slotsの`ExistingPrefixContext`と`AnalysisContext` unionを追加した。既存prefix contextは`path_flavor`、`case_rule`、任意の観測済みPython version/platform/architectureだけを保持し、非`None`値はtrim済みの非空・NULなし文字列かつpath-likeではない安全なobservationとして検証する。absolute、drive-relative、relative、UNC、tildeおよびslash/backslashを含むraw path値は拒否し、エラーへ値を出力しない。
- `AnalysisResult`と`analyze_installed_environment()`は両contextを受理し、inventory layoutとのpath flavor/case rule照合は既存のtyped error contractのまま維持した。
- schema v1 serializerは`ResolutionContext`以外を明示的な`TypeError`で拒否するため、存在しないresolution属性への`AttributeError`に依存せず、既存golden JSONの形とbytesを変えない。
- optional context validation、immutability、permutation/hash determinism、layout mismatch、resolution context regression、v1 rejectionのunit coverageを追加した。dependency graph/explanationとprefix discovery、schema v2、CLIは後続taskに分離した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_models.py tests/test_analysis.py tests/test_json_render.py -q` — 成功（148 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check`、`make test` — 成功（443 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointを検証した。

引き継ぎ:

- 次のタスクはP3-04a2とする。existing-prefix contextを機械可読に表現するschema v2を、v1不変のまま実装する。

### 2026-07-31: P3-03c footprint presentation public CLI/README contract

状態: `done`

実装:

- `--breakdown`をtext-only opt-inとしてCLIへ接続した。text modeでは、測定済みの`InstalledEnvironment`からinstalled Core Metadata graphを一度だけ構築し、dependency path explanationとglobal footprint resultを順に導出する。breakdown単独は既存reportをbyte-identical prefixにしてFile Category BreakdownとDependency Size Attributionを追加する。
- `--explain --breakdown`は通常reportを一度だけ表示した後に既存のdependency explanation section、footprint sectionの順で合成する。incomplete graph時のsafe warning code/count summaryは一度だけ表示し、category totalは維持しつつdependency role totalをunavailableと明示する。
- JSON schema v1は互換境界のままにした。`--json --breakdown`および`--json --explain --breakdown`はinstalled metadata、graph、footprint aggregationを呼ばず、`--json`単独とstdout、stderr、exit behaviorがbyte-identicalである。
- READMEにcanonical global dedupe、6 file category、dependency role/mixed ownership、incomplete graph時のavailability、installed Core Metadata basis、JSON v1不変、P3-05で扱うroot別byte配賦の境界を記載した。
- local wheelhouseの実installでcategory/role table、shared direct dependencyが一度だけ分類されること、`--bin`のtotal不変、explanationとのsection合成、JSON text-option combinationsのbyte equalityを検証した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_uv_packsize.py tests/test_local_wheel_integration.py tests/test_footprint_render.py -q` — 成功（66 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check`、`make test` — 成功（409 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointを検証した。

引き継ぎ:

- P3-03は完了。次のタスクはP3-04とし、既存virtual environmentまたはprefixを安全に分析する入力modeを設計する。

### 2026-07-31: P3-03b footprint result pure text presentation

状態: `done`

実装:

- [`uv_packsize/footprint_render.py`](../uv_packsize/footprint_render.py)に、既存`render_analysis_report()`をbyte-identical prefixとして維持した`render_footprint_report()`と、将来のopt-in composer用のsection-only APIを追加した。`--bin`相当のprefix表示は変えず、global-deduplicated footprint totalは常に不変とする。
- File Category Breakdownは`FileCategory` enum順の全6行をzero rowを含めて表示し、Dependency Size Attributionはgraph complete時だけ`self`、`direct`、`transitive`、`unattributed`、`mixed-ownership`の固定順とglobal totalを表示する。両sectionは既存`format_size()`のbinary unit表記を再利用する。
- graph incomplete時のdependency size attributionは数値を表示せず、availability文とsafe warning code/countだけを表示する。section-only APIはwarning summaryの包含を制御できるため、P3-03cで`--explain`と合成してもgraph warningを重複させない。
- [`tests/test_footprint_render.py`](../tests/test_footprint_render.py)でprefix完全一致、enum/role順、zero row、empty、`--bin`不変、incomplete graphのsanitization、warning summary composition、型検証を追加し、artifact verifierにrendererをcritical moduleとして追加した。CLI、README、explanation renderer、JSON schema v1は変更していない。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_footprint_render.py -q` — 成功（11 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked ruff format --check uv_packsize/footprint_render.py tests/test_footprint_render.py`、`uv run --locked ruff check uv_packsize/footprint_render.py tests/test_footprint_render.py`、`uv run --locked ty check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check`、`make test` — 成功（403 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointに`footprint_render.py`を含むことを検証した。

引き継ぎ:

- 次のタスクはP3-03cとする。footprint presentationをtext-only opt-in CLI/README契約へ接続し、`--explain`とのwarning summary重複がないこと、JSON schema v1不変、local wheel end-to-endを検証する。

### 2026-07-31: P3-03a global footprint aggregation

状態: `done`

実装:

- [`uv_packsize/footprint.py`](../uv_packsize/footprint.py)に、`ExplainedAnalysisResult`だけを入力にするfrozen/slotsの`FootprintResult`を追加した。global category totalsはcanonical identityごとに一度だけ数え、固定された全`FileCategory`をzero rowを含めて保持する。
- dependency graphがcompleteの場合だけ、`self`、`direct`、`transitive`、`unattributed`、`mixed-ownership`のrole totalsとrole内category totalsを導出する。複数ownerが同一roleなら一度だけそのroleへ、異なるroleなら一度だけ`mixed-ownership`へ分類する。rootでもあるdistributionは`self`とする。
- graphがincompleteならinventory由来category totalsは維持し、role totalsは`None`として利用不能を明示する。inventory/graph/combined completenessは説明resultから別々に委譲する。
- aggregate modelは、全category/role、subtotal、source inventoryへの再計算一致を検証するため、外部から供給された欠損・重複・改ざん済みtotalを受理しない。root別byte配賦、既存text/CLI/README/JSON schema v1は変更していない。
- [`tests/test_footprint.py`](../tests/test_footprint.py)で、6 category/zero row/empty、rootかつdependency、shared dependencyと同名root input、duplicate ownershipのdedupe/mixed、role-category matrix、graph incomplete gate、permutation/frozen/forged aggregateをnetwork不要で検証し、artifact verifierへnew moduleを追加した。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_footprint.py -q` — 成功（10 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked ruff format --check uv_packsize/footprint.py tests/test_footprint.py`、`uv run --locked ruff check uv_packsize/footprint.py tests/test_footprint.py`、`uv run --locked ty check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check`、`make test` — 成功（392 passed, 1 skipped）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check`、`make verify-build` — 成功。wheel/sdistとinstalled entry pointに`footprint.py`を含むことを検証した。

引き継ぎ:

- 次のタスクはP3-03bとする。P3-03aのimmutable resultをpure text presentationへ接続し、既存report、CLI、README、JSON schema v1は変更しない。

### 2026-07-31: P3-02a dependency path/explanation pure result

状態: `done`

実装:

- `uv_packsize/dependency_paths.py`に、root input indexとsimple normalized node tupleを保持するimmutableな`DependencyPath`、nodeごとのroot input reachabilityとcanonical pathを保持する`DistributionAttribution`、および`ExplainedAnalysisResult`を追加した。
- `explain_dependency_paths()`は、analysisとgraphのdistribution name/version集合、root input indexes、recognized root input名、edgeからBFS reachabilityを再計算し、graph nodeのkind/root names/shared labelを検証する。canonical pathはlexical edge orderのcycle-safe shortest pathから`(edge_count, root_input_index, path_node_names)`で決める。
- 同名のrecognized root入力もinput index単位で到達性に残すが、既存graphの`is_shared`は異なるroot distribution名による既存の意味を保持する。inventory、graph、overallのcompletenessを分離した。
- text renderer、CLI、README、schema v1 JSON、inventory/installed metadataは変更していない。artifact verifierは新moduleをwheel/sdistのcritical artifactとして確認する。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked ruff format uv_packsize/dependency_paths.py tests/test_dependency_paths.py`、`ruff check`、`ty check`、`pytest tests/test_dependency_paths.py` — 成功（11 passed）。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 369 passed, 1 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check`、`git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make verify-build` — wheel/sdistへの新module含有、artifact metadata、installed entry pointを検証して成功。

引き継ぎ:

- 次のタスクはP3-02bとする。P3-02aのpure resultをopt-inの`--explain` text presentationへ接続する。schema v1 JSONおよびbyte attributionはこのtaskの対象外とする。

### 2026-07-31: P3-01b installed Core Metadata adapter

状態: `done`

実装:

- target venvを一度だけprobeし、完全な`MarkerEnvironment`とPackagingのpre-release semanticsをtarget interpreter由来の値でgraph coreへ渡すようにした。
- `InstalledEnvironment`にcontext、inventory layouts、marker environmentを束ね、`uv_packsize/installed_metadata.py`のadapterをこのenvironmentへboundした。analysisとのcontext mismatchは、値やfilesystem pathを露出しないtyped errorにした。
- adapterはsite-packagesのdirect childである非symlink `.dist-info` directoryだけを対象に、非symlink regular `METADATA`を読む。Core Metadata version `1.0`、`1.1`、`1.2`、`2.1`〜`2.5`だけを受理する。
- metadataのmissing、invalid、duplicate、name mismatch、version mismatchをsafe typed metadata stateへ変換し、graph warning/completenessへ接続した。raw metadata、parser diagnostic、filesystem pathはgraph resultへ残さない。
- graphは内部modelのまま維持し、既存text出力、JSON schema v1、公開CLI契約を変更していない。Core Metadata graphはinstalled metadataに基づく説明情報であり、resolver provenanceではない。
- artifact verifierのcritical module一覧へ`uv_packsize/installed_metadata.py`を追加し、wheelとsdistの両方にadapterが含まれることを確認する。

検証:

- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 355 passed, 1 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check` — 成功。
- `git diff --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make verify-build` — wheel/sdist metadata、artifact inventory、installed entry pointを検証して成功。

引き継ぎ:

- 次のタスクはP3-02とする。P3-01bのCore Metadata graphを、dependency pathとdirect/transitive/shared attributionを表示可能なresultへ接続する。resolverの判断・provenanceをCore Metadata graphから推測しない。

### 2026-07-31: P3-01a installed metadata dependency graph pure core

状態: `done`

実装:

- `uv_packsize.models.normalize_distribution_name`を公開し、inventory modelとdependency graphで同一のPEP 503 name normalizationを使用するようにした。
- immutableなinstalled metadata、explicit marker environment、root status、node/edge、warning/completeness modelとpure builderを`uv_packsize/dependency_graph.py`に追加した。
- `packaging`をruntime dependencyへ追加してlockを同期した。graphは`Requirement`を利用してmarkerをexplicit target environmentだけで評価し、raw Core Metadataをresultへ残さない。
- setuptools package discoveryを`uv_packsize*`へ明示的に限定し、source-onlyの`schemas/`をnamespace packageとして誤検出しないようにした。artifact verifierは`packaging`のruntime metadataとwheelへのschema混入がないことを確認する。
- P3-01aのunit testsを追加し、marker/extras固定点、空extraを含むmarker評価、root marker失敗、pre-release policy、cycle、root照合、warningのsecret非漏洩、既存schema v1 JSONの不変性を検証した。

検証:

- `uv run --locked --no-sync ruff format uv_packsize/models.py uv_packsize/dependency_graph.py tests/test_dependency_graph.py` — 成功。
- `uv run --locked --no-sync ruff check uv_packsize/models.py uv_packsize/dependency_graph.py tests/test_dependency_graph.py` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked --no-sync ty check uv_packsize tests` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked --no-sync pytest -q tests/test_dependency_graph.py tests/test_json_render.py` — 52 passed。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv sync --locked` — editable buildを含め成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test` — 300 passed, 1 skipped。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check` — 成功。
- `UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make verify-build` — wheel/sdist metadata、artifact inventory、installed entry pointを検証して成功。
- `git diff --check` — 成功。

引き継ぎ:

- 次のタスクはP3-01bとする。P3-01aのgraph modelを既存CLIやschema v1へ接続せず、まずinstalled Core Metadata adapterの安全なinput境界を確立する。

### 2026-07-31: P2-07 wheel-only installer safety

状態: `done`

実装:

- [`uv_packsize/cli.py`](../uv_packsize/cli.py)でCLIの既定build policyを`BuildPolicy.WHEEL_ONLY`にし、installerへ同じpolicyを渡して`uv pip install ... --no-build`を実行するようにした。`--allow-build`を明示した場合だけ`--no-build`を省略し、environment discoveryとJSON contextにも同一の`BuildPolicy`を渡す。
- wheel-only installの失敗は、raw uv diagnostics、requirements、pathを出さず、互換wheelがない可能性と信頼できるsourceに限った`--allow-build`再試行を案内する。build許可時のinstall失敗は既存のgenericな安全エラーを維持する。
- [`README.md`](../README.md)のhelp、安全性契約、JSON context説明を更新した。`context.build_policy`は選択したbuild許可を記録するだけで、uv diagnosticsやcacheから実際にbuildしたdistributionを推測しないことを明記した。
- unit/local-wheel integrationではinstaller commandの`--no-build`有無、default/opt-inのcontext policy、help、sanitized failureを検証した。sdist safety integrationはdefault拒否時の空JSON stdout、安全なstderr、build sentinel非実行を検証した。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_uv_packsize.py tests/test_local_wheel_integration.py tests/test_sdist_safety_integration.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check
git diff --check
```

結果:

- focused testsは42件成功した。
- 全282テストが成功し、1件は既存skipである。Ruff format/lint、ty、README生成整合性、lock check、whitespace checkも成功した。

引き継ぎ:

- F-005を解消した。Phase 2は12 / 12タスクを完了し、次のタスクはP3-01とする。実際にbuildされたdistributionのprovenanceは、uvのmachine-readableな根拠が得られるまで推測せず、F-007としてPhase 6へ送る。

### 2026-07-31: P2-06b cross-platform layout golden coverage

状態: `done`

実装:

- [`tests/test_layout_goldens.py`](../tests/test_layout_goldens.py)で、P2-06aのdeterministic local wheel fixtureからroot-a wheelを物理的には`tmp_path`配下へ展開し、Linux、macOS、Windowsの固定logical prefix/site-packages layoutへ対応する`RECORD`を生成するgolden testを追加した。各ケースはscripts、data、headersを含み、`analyze_installed_environment`までのinventory収集、`show_scripts=True`のtext renderer、JSON rendererを一貫して検証する。
- [`tests/golden/layouts/`](../tests/golden/layouts/)にplatformごとのtext/JSON goldenを追加した。JSON goldenのglobal/distribution totalsとresult由来の合計を明示的に照合し、renderer出力は完全一致で比較する。Windows caseは`Scripts`、`Lib/site-packages`、case-insensitive canonical identityを固定する。
- host platformに依存するresolver/installとentry point生成はP2-06aの実integration testの責務として維持し、本タスクでは実physical pathとtarget logical pathを分離した。低水準のRECORD path resolver unit testは重複追加していない。

検証:

- `uv run --locked pytest tests/test_layout_goldens.py`（3 passed）
- `uv run --locked ruff format --check tests/test_layout_goldens.py`（passed）
- `uv run --locked ruff check tests/test_layout_goldens.py`（passed）
- `uv run --locked ty check`（passed）
- `git diff --check`（passed）

引き継ぎ:

- P2-07でwheel-onlyをdefaultにし、sdist build許可を明示opt-inへ移行する。

### 2026-07-19: P2-06a local wheelによる実install integration

状態: `done`

実装:

- [`tests/local_wheel_factory.py`](../tests/local_wheel_factory.py)にstdlibだけを使うreview可能なfixture factoryを追加した。`uv-packsize-fixture-root-a`、`uv-packsize-fixture-root-b`、`uv-packsize-fixture-shared`のversion `1.0.0` universal wheelを、固定ZIP timestamp/permission、lexical member order、`ZIP_STORED`、validな`METADATA`/`WHEEL`/3-column `RECORD`で毎回同じbytesへ生成する。両rootはsharedへ依存し、root-aはPython source、console entry point、`.data/scripts`、`.data/data/share/...`、`.data/headers/...`を含む。
- [`tests/test_local_wheel_integration.py`](../tests/test_local_wheel_integration.py)でmockなしに`sys.executable -m uv_packsize`を実行するintegration testを追加した。child environmentは`PATH`とWindows必須process variableだけをallowlistし、task-local HOME/USERPROFILE/APPDATA/LOCALAPPDATA/TMPと明示的な`UV_NO_INDEX=1`、local `UV_FIND_LINKS`、`UV_OFFLINE=1`、`UV_NO_PROGRESS=1`、`UV_NO_CONFIG=1`、`UV_NO_CACHE=1`、`UV_PYTHON_DOWNLOADS=never`だけを渡す。親の`UV_CONFIG_FILE`、`UV_CONSTRAINT`、`PYTHONPATH`を毒入れしても継承しないことを回帰testで確認し、resolver、venv作成、install、inventory、text/JSON rendererをnetwork/config非依存で通す。
- default textが3 fixture distributionだけを表示し、`--bin`がPOSIX `bin/`またはWindows `Scripts/`下のconsole entry pointと`.data/scripts` payloadを表示してもfinal totalを変えないことを検証した。factory testはZIP memberとRECORD rowのexact coverage、self rowの空hash/size、各non-self memberの再計算したURL-safe SHA-256 hashとbyte sizeを検証する。JSONはstdoutだけをparseし、schema v1、進捗だけのstderr、complete/no warnings、3 distributionのversion、root-aのpython/metadata/script/data category、header/data suffix、global totalとdistribution sumの一致を検証した。

検証:

```bash
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv run --locked pytest tests/test_local_wheel_integration.py -q
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make ci-check
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache make test
UV_CACHE_DIR=/private/tmp/uv-packsize-ci-cache uv lock --check
git diff --check
```

結果:

- focused integration testは4件成功した。
- 全275テストが成功し、1件は既存skipである。Ruff format/lint、ty、README生成整合性、lock check、whitespace checkも成功した。

引き継ぎ:

- F-004は`partial`とする。通常suiteの実CLI成功経路はlocal wheelとlocal find-linksへ移行済みだが、Linux/macOS/Windows target layout goldenとPyPI smoke testの分離はP2-06bで完了する。
- P2-07でwheel-onlyをdefaultにするまでは、実CLIのbuild policyは`allow-build`のままである。P2-06aのfixtureにはsdistまたはbuild backendを含めない。

### 2026-07-19: P2-05b CLI JSON出力、README契約、error/exit behavior

状態: `done`

実装:

- [`uv_packsize/cli.py`](../uv_packsize/cli.py)に`--json`を追加し、成功時は`render_analysis_json(result)`の末尾LFを保ったままstdoutへ1回だけ出力するようにした。text report、進捗、completion messageをstdoutへ混在させない。
- JSON modeではcalculation、venv creation、install、analysis、completionの進捗をstderrへ切り替えた。既存のtext modeはstdout出力を維持した。
- `--bin`をtext-only presentation optionとしてhelpへ明記し、JSON modeではinventoryまたはserializerを変えないため`--json --bin`のbytesは`--json`と一致する。
- 既存のsanitized `ClickException`境界を維持し、JSON modeのoperational failureはexit 1、空stdout、stderr上の安全な進捗/エラーとした。invalid usageはClickのexit 2を維持し、programmer errorは捕捉しない。
- [`README.md`](../README.md)にschema v1、top-level fieldの用途、安全で非可逆なrequirement representation、raw symlink target非出力、stdout/stderr/exit contract、redirect例、`--bin`との相互作用を記載した。

テスト:

- 実stdlib venv fixtureでJSONをparseし、stdoutがpure serializerと完全一致すること、進捗がstderrだけに出ること、repeatと`--bin`有無でJSON bytesが一致することを検証した。
- help、default text output、uv/discovery operational failureの空stdoutとcredential/path/traceback非露出を回帰テストで検証した。

検証:

```bash
uv run --locked pytest tests/test_uv_packsize.py -q
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- CLI対象34テスト、全271テスト（1 skipped）が成功した。
- Ruff format/lint、ty、README生成整合性、lock check、whitespace checkが成功した。

### 2026-07-19: P2-05a pure JSON schema/serializer

状態: `done`

実装:

- [`uv_packsize/json_render.py`](../uv_packsize/json_render.py)に、`AnalysisResult`だけを受けるschema v1 serializerを追加した。top-levelの全fieldとnested object fieldは固定順で常に出力し、`json.dumps(..., ensure_ascii=False, allow_nan=False, indent=2, sort_keys=False)`による末尾LF 1個のJSONを返す。
- [`schemas/analysis-result-v1.schema.json`](../schemas/analysis-result-v1.schema.json)をcommitted closed schemaとして追加した。v1 major versionを互換性境界とし、context enum、file category/origin、warning、safe requirement projection、totalsを全field必須で固定した。
- raw requirement/specifier/marker/URL/credential/digestを出力しない入力順付きprojectionを定義し、symlink targetは`is_symlink`へ縮約した。direct URLはabsolute URI formまたはVCS file URI、安全なlocal pathは明示的なrelative/absolute/tilde/UNC pathとhost付き形式を含むlocal file URIだけを認め、曖昧なtargetは`opaque`へ落とす。`ResolutionContext.index_identifiers`もURL/path/userinfoを受け付けない1〜64文字のASCII symbolic aliasへ制限した。
- [`tests/test_json_render.py`](../tests/test_json_render.py)と[`tests/golden/analysis-result-v1.json`](../tests/golden/analysis-result-v1.json)を追加し、exact golden、input permutation、empty/totals、credential/local path/symlink target非漏えい、valid URL/VCS/file URIとmalformed/bare-relative/`C:relative`を含むrequirement classifier、index validation、schema/golden shapeをnetwork不要で検証した。goldenはduplicate ownership、不完全warning、Unicode path、全file categoryと全originを含む。

検証:

```bash
uv run --locked pytest tests/test_json_render.py tests/test_models.py -q
uv run --locked ruff format --check uv_packsize/json_render.py uv_packsize/models.py tests/test_json_render.py
uv run --locked ruff check uv_packsize/json_render.py uv_packsize/models.py tests/test_json_render.py
uv run --locked ty check
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- JSON/model対象100テスト、全264テスト（1 skipped）が成功した。
- Ruff format/lint、ty、README生成整合性、lock check、whitespace checkが成功した。

スコープ境界:

- CLI option、stdout/error/exit behavior、READMEのJSON公開契約はP2-05bで接続する。P2-05aでは既存CLIとREADMEを変更していない。

### 2026-07-19: P2-04b2 CLIを新測定engineとrendererへ接続

状態: `done`

実装:

- [`uv_packsize/cli.py`](../uv_packsize/cli.py)で既存のtemporary venv作成・install flowの後に、`uv --version`を既存`_run_uv`経由で照会し、安全に検証したversion tokenを取得するようにした。実際のoptional build metadata付き出力を許容し、未知の出力はraw textを表示せず拒否する。`UvCommandError`は内部診断を保持するが、public Click messageにはstageとexit codeだけを出し、uv stdout/stderrを転記しない。進捗表示はrequirementsの値を使わず、requested package数だけを表示する。
- temporary venvの実interpreter/prefixを`discover_installed_environment`へ渡し、requirements、`BuildPolicy.ALLOW_BUILD`、`compile_bytecode=False`、現在のextras/index/resolution defaultsを明示して、`analyze_installed_environment`を1回だけ実行するようにした。
- text出力を`render_analysis_report`へ一元化し、`--bin`をRECORD-owned scriptの表示分離だけを行うpresentation optionへ移行した。final global totalは`--bin`の有無で変化しない。
- legacyのsite-packages walk、CSV/metadata集計、bin再scan、独自table formatterを削除した。既知のdiscovery/inventory/analysis例外はCLI境界でsanitizedな`ClickException`へ変換し、programmer errorは捕捉しない。
- READMEをprefix-wide RECORD ownership、global dedupe/incomplete warning、`KiB`/`MiB`単位、`--bin`の非加算契約へ更新した。sdist build safetyとreproducible JSON未提供の制約は維持した。

テスト:

- PyPI/networkへ依存するCLI success testを、実際のstdlib venvとそのprefix内に置くtest-owned installed layoutへ置換した。installerと`uv --version`だけをmockし、prefix-wide script/data ownership、resolved distribution表示、incomplete warning、duplicate ownership、`--bin`のtotal不変、analysis一回呼び出し、version failure、sanitized discovery/inventory/analysis failureを検証した。venv/install/version failureではcredential URL、一時path、command secret、raw diagnosticをpublic outputへ含めないことも検証した。

検証:

- `uv run --locked pytest tests/test_uv_packsize.py` — 27 passed
- `make ci-check` — ruff format/lint、ty、README cog check成功
- `make test` — 229 passed, 1 skipped
- `uv lock --check` — 成功
- `git diff --check` — whitespace errorなし

### 2026-07-19: P2-04b1 `AnalysisResult` pure text renderer

状態: `done`

実装:

- [`uv_packsize/render.py`](../uv_packsize/render.py)を追加し、`AnalysisResult`だけからcompleteなdeterministic text reportを返す`render_analysis_report`を実装した。filesystem、subprocess、Click、networkには依存しない。
- distribution rowは`FileEntry` inventoryから導出し、logical bytes降順・normalized name昇順で整列する。footerと最終totalはcanonical identityで重複排除されたglobal totalを使い、row sumとの差はduplicate-owned filesをglobalで一度だけ数える理由としてpathやownerを出さずに説明する。
- `format_size`は1024基準で`B`、`KiB`、`MiB`、`GiB`を表示する。incomplete resultはtyped warning codeごとの件数だけをdeterministicに要約し、raw targetやdiagnosticsを出力しない。
- `show_scripts=True`ではpackage row/subtotalから`SCRIPT`を除き、canonical-deduped script fileをprefix-relativeな`FileEntry.path`で`Binaries in .venv/bin` tableへ表示する。同じcanonical identityでdisplay caseが異なる場合も、pathをdeterministicに選択する。package/script footerの合計と最終global totalは一致し、scriptを二重計上しない。
- `format_size`はboolを含むnon-intとnegative valueを明示的に拒否する。script split時のrow-total注記はdistribution rowだけでなくbinary rowも含むため、`displayed rows`と表現する。

テスト:

- [`tests/test_render.py`](../tests/test_render.py)を追加し、unit boundaryとinvalid input、同sizeのtie ordering、global dedupeとfooter、incomplete warningのsanitization、script split/dedupe、Windows case-insensitive styleのdisplay path選択、empty resultをnetwork・filesystem不要のfixtureで検証した。

検証:

```bash
uv run --locked pytest tests/test_render.py -q
uv run --locked ruff format --check uv_packsize/render.py tests/test_render.py
uv run --locked ruff check uv_packsize/render.py tests/test_render.py
uv run --locked ty check
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- focused renderer testsは14件成功した。
- Ruff format/lint、ty、README生成整合性、lock checkはすべて成功した。
- 全test suiteは227件成功、1件skipした。
- whitespace errorはなかった。

スコープ境界:

- CLI、uv execution、environment discovery、inventory analysis、READMEの公開text契約は未変更である。P2-04b2で既存temporary venv flowをmeasurement engineとrendererへ接続する。

### 2026-07-19: P2-04a temporary venv environment discovery adapter

状態: `done`

実装:

- [`uv_packsize/environment.py`](../uv_packsize/environment.py)を追加し、temporary venvのPythonを`-I`で一度だけJSON probeして`InstalledEnvironment(context, layouts)`を構築する`discover_installed_environment`を実装した。
- probe payloadから実際の完全な数値Python version、sysconfig platform、architecture、path flavorを得て、caller suppliedのresolution設定とともにimmutableな`ResolutionContext`へ渡す。purelib/platlibのphysical/logical layoutを検証・dedupeし、同一physical siteへ矛盾したlogical siteを割り当てない。
- prefix、base prefix、interpreterを検証し、site-packages外をprobeしない。siteごとのcase probeはUUID directoryを作成してcase aliasを確認し、finallyで削除する。
- interpreter identityはraw path文字列ではなく`samefile`で照合し、同時にreported/invoked executableの各prefix下containmentを検証する。subprocess stdoutはbytesで取得してstrict UTF-8 decodeする。
- invalid venv/probe/layout/case/filesystem failureは`EnvironmentDiscoveryError`のcodeとsanitized targetだけで表し、raw paths、requirements、subprocess diagnosticsをmessageへ含めない。

テスト:

- [`tests/test_environment.py`](../tests/test_environment.py)を追加し、caller contextの保持、purelib/platlib dedupe、actual temporary venv probeの成功、isolated venv Pythonの単一probe、siteごとのcase probe、sanitized error、case mismatchを検証した。valid JSONでもnumeric Python versionでないpayloadとmalformed UTF-8を拒否し、venv内/外hardlink alias、Windows case variantを検証する。Windowsではsymlink権限を要求しないtemporary venv fixtureを使用する。
- POSIX filesystem上でWindows logical prefix/site-packagesを構築し、Windows path flavorとcase-insensitive layoutをhost依存なしに検証した。

検証:

```bash
uv run --locked pytest tests/test_environment.py -q
uv run --locked ruff check uv_packsize/environment.py tests/test_environment.py
uv run --locked ruff format uv_packsize/environment.py tests/test_environment.py
uv run --locked ty check
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- focused environment testsは13件成功し、Windows限定case testは非Windows hostでは1件skipした。全test suiteは213件成功、1件skipした。
- Ruff format/lint、ty、README生成整合性、lock checkはすべて成功した。
- whitespace errorはなかった。

スコープ境界:

- CLI、uv command/version query、`analyze_installed_environment`、renderer、JSON、networkは接続していない。P2-04bで既存temporary venv flowからこのadapterとmeasurement engineを接続する。

### 2026-07-19: P2-03 installed environment contextとinventoryのAnalysisResult接続

状態: `done`

実装:

- [`uv_packsize/analysis.py`](../uv_packsize/analysis.py)を追加し、caller確定済みの`ResolutionContext`、layout collection、supplemental ownership collectionから完全な`AnalysisResult`を返す`analyze_installed_environment`を実装した。
- contextを最初に検証し、layout/supplemental iterableを各1回だけtupleへmaterializeして要素型を検証する。全layoutのpath flavor/case ruleをfilesystem scan前にcontextと照合し、不一致を`PATH_FLAVOR_MISMATCH`/`CASE_RULE_MISMATCH`のtyped errorとsanitized targetで報告する。
- `PathFlavor`/`CaseRule`を[`uv_packsize/models.py`](../uv_packsize/models.py)へ移し、`ResolutionContext`の必須比較条件にした。inventory moduleからの既存importは同moduleがmodel enumをimport/re-exportすることで互換性を維持した。
- collectorを1回だけ呼び、そのdistribution tupleを`AnalysisResult`へ直接渡す。context、resolved versions、file inventory、derived totals/warnings/completenessをコピー・補正せず、inventoryのtyped errorsも変換しない。

テスト:

- [`tests/test_analysis.py`](../tests/test_analysis.py)へnetwork不要のinstalled-environment fixturesを追加し、全context fieldsとobject identity、resolved versions、layout/supplemental permutationの等価性とhash一致を検証した。
- empty environmentのcomplete/zero result、明示的`DISCOVERED` file、nested distribution incompleteness、shared ownershipのglobal dedupe/derived warning/relation、distribution totalsとglobal totalの差を検証した。
- path flavor/case rule mismatchがcollector呼出し前にtyped errorになること、collection validation、collectorの単一呼出し、scan/supplemental/conflict errorの同一instance伝播を検証した。
- `compile_bytecode=False`は観測inventoryをfilterせず、実在generated bytecodeを保持する契約をfixture化した。

検証:

```bash
uv run --locked pytest tests/test_analysis.py tests/test_models.py tests/test_inventory.py -q
uv run --locked ruff check uv_packsize/analysis.py uv_packsize/models.py uv_packsize/inventory.py tests/test_analysis.py tests/test_models.py tests/test_inventory.py
uv run --locked ty check
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- analysis/model/inventory対象175テスト、全200テストが成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- lockは同期済みで、whitespace errorはなかった。

スコープ境界:

- CLI、installer、subprocess、renderer、JSON、networkへは接続していない。既存CLIの公開出力と測定挙動は変更していない。
- platform、architecture、Python、uv/build/bytecode条件の事実確認はinstalled environmentを作成するcallerの責任であり、orchestration層では推測しない。

### 2026-07-19: P2-02b 全distribution scanと明示的なsupplemental discovery

状態: `done`

実装:

- [`uv_packsize/inventory.py`](../uv_packsize/inventory.py)へ、compatibleな複数`InventoryLayout`を検証し、全direct-child `.dist-info`を決定的に収集する`collect_distributions`を追加した。layout alias/incompatibility、filesystem failure、invalid dist-info、distribution name/version衝突をtyped errorで報告する。
- distribution name/versionをowner keyとするimmutableな`SupplementalOwnership`を追加し、callerが明示した測定prefix相対のexact fileだけを`DISCOVERED`として既存collectorへ統合した。同一raw pathとcase aliasはset semanticsで一意化し、origin優先順位を保つ。
- cross-ownerの同一canonical identityはlogical bytes、category、symlink targetが一致する場合だけ許可し、不一致は`InventoryConflictError`として`AnalysisResult`構築前に拒否する。
- METADATAを優先してdistribution identityを読み、missing/invalid時のdirname fallbackをtyped incomplete warningにした。空RECORDとRECORD self-entry欠落もそれぞれtyped incomplete warningとして扱い、P2-02aからのmetadata/RECORD完全性課題を完了した。
- invalid supplemental raw pathをerror targetへ含めず、final symlinkはtargetをfollowせずlink entryを収集し、intermediate symlink escape、missing file、directory/special file、filesystem errorをtyped supplemental errorにした。

テスト:

- 複数POSIX/Windows layout、logical case variant、resolved physical symlink alias、filesystem列挙順とlayout入力順、uppercase `.DIST-INFO`、direct-child限定、distribution衝突をnetwork不要fixtureで検証した。
- exact supplemental file、同一raw path/case alias/複数ownershipの順序不変、RECORD/GENERATED/FALLBACK/missing claimの優先、unknown/stale owner、invalid/missing/special/escape、prefix外targetのfinal symlink、compatible/incompatible shared ownershipを検証した。
- valid/missing/invalid METADATA、fallback不能なdirname、空RECORD、self-entry欠落を検証し、収集結果を`AnalysisResult`へ追加補正なしで渡してglobal dedupeできることを確認した。

検証:

```bash
uv run --locked pytest tests/test_inventory.py tests/test_models.py -q
uv run --locked ruff check uv_packsize/inventory.py uv_packsize/models.py tests/test_inventory.py tests/test_models.py
uv run --locked ty check
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- inventory/model対象156テスト、全181テストが成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- lockは同期済みで、whitespace errorはなかった。

スコープ境界:

- collectorは既存CLI/renderer/installerへ未接続で、公開出力と現行測定挙動は変更していない。
- invalid/outside RECORDの複数raw path詳細はcredentialやhost pathを漏らさないため保持せず、distribution-targetのtyped warningとして集約する現行契約を維持した。

### 2026-07-19: P2-02a RECORD path resolverとsingle-distribution collector

状態: `done`

実装:

- [`uv_packsize/inventory.py`](../uv_packsize/inventory.py)へ、physical/target logical pathを分離する`InventoryLayout`、明示的な`PathFlavor`/`CaseRule`、host非依存RECORD path resolver、single-distribution collectorを追加した。
- POSIX relative/absolute path、Windows drive/UNC/slash/backslash/case ruleをlexicalにnormalizeし、component containment、Win32 alias、case-insensitive host adapter、intermediate symlink escapeをfilesystem access前に検証する。
- strict RECORD CSVからprefix内のsite-packages、scripts、data、headersを収集し、path/layout由来のcategoryと`RECORD`/`GENERATED`/`FALLBACK` originを付与する。
- final symlinkはfollowせず`lstat` sizeとraw `readlink` targetを記録し、hardlinkはlexical pathごとに数える。missing/duplicate/malformed/outside/special file/filesystem errorはtyped warningとderived incompletenessへ変換する。
- model warning codeをcollector failureへ拡張し、すべてのdistribution-target warningがcontainer自身を指す不変条件へ一般化した。POSIXの有効なwhitespace filenameとraw symlink targetもmodelで表現できるようにした。

テスト:

- [`tests/test_inventory.py`](../tests/test_inventory.py)へnetwork不要のtemporary filesystem fixturesを追加した。
- POSIX/Windows/UNC path、valid `..`、outside/sibling/underflow、Win32 invalid path、case collision、strict CSV/UTF-8/hash/ASCII size、site-packages外file、missing/duplicate/generated/fallback、zero-byte、hardlink、final/intermediate symlink、special file、filesystem errorを検証した。
- inventory/model専用122テストと全147テストが成功した。

検証:

```bash
uv run --locked pytest tests/test_inventory.py tests/test_models.py -q
uv run --locked ruff check uv_packsize/inventory.py tests/test_inventory.py uv_packsize/models.py tests/test_models.py
uv run --locked ty check uv_packsize/inventory.py tests/test_inventory.py uv_packsize/models.py tests/test_models.py
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- 対象122テスト、全147テストが成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- lockは同期済みで、whitespace errorはなかった。

残課題:

- P2-02aはsingle-distribution APIであり、全distribution scanと`DISCOVERED` originはP2-02bの範囲である。
- missing/unreadable METADATAはdirname fallback、空RECORDとRECORD self-entry欠落は未検証のmetadataとして扱う。いずれもP2-02bでcompleteness契約を決定する。
- collectorは既存CLI/renderer/installerへ未接続で、公開出力と現行測定挙動は変更していない。

### 2026-07-19: P2-01 AnalysisResultとfile inventoryのデータモデル設計

状態: `done`

実装:

- [`uv_packsize/models.py`](../uv_packsize/models.py)へPython 3.10対応・標準ライブラリのみのfrozen/slots/keyword-only modelを追加した。
- `ResolutionContext`はrequirements順を保持しつつextrasとindex identityをset semanticsで正規化し、buildとbytecode条件を必須のtyped値として保持する。
- `FileEntry`はownershipを持たず、prefix相対のlexical path、case-normalized canonical identity、logical bytes、category、4種類のorigin、独立したsymlink targetを保持する。
- `DistributionResult`のtotalとcompleteness、`AnalysisResult`のglobal totalとcompletenessをinventory/warningから導出し、可変な重複集計値を持たせなかった。
- cross-distributionの同一identityはglobal totalで一度だけ数え、immutableなowners relationとderived warningで説明する。size、category、symlink targetの矛盾や同一distribution内の重複identityは拒否する。
- warningはtyped code、target kind、target identityで表現し、dedupe/orderを決定的にした。missing RECORD/fileはincompleteを導出し、duplicate ownership/RECORD entryはwarningを保持しつつcompleteとして扱う。

テスト:

- [`tests/test_models.py`](../tests/test_models.py)へnetwork・resolver・filesystemを使わない63件のunit testsを追加した。
- immutable/hashable、collection防御、distribution/extra name正規化、invalid string/path/size/type、warning target、input permutation、total dedupe、ownership relation、conflicting signature、completenessを検証した。

検証:

```bash
uv run --locked pytest tests/test_models.py -q
make ci-check
make test
uv lock --check
git diff --check
```

結果:

- 対象63テストが成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全88テストが成功した。
- lockは同期済みで、whitespace errorはなかった。

残課題:

- filesystem collector、logical symlink sizeの定義、各`FileOrigin`を選ぶ収集規則はP2-02で実装・fixture化する。
- P2-01のmodelは既存CLIへ接続していないため、公開出力と現行測定挙動は変更していない。

### 2026-07-19: P1-09 Phase 1総合検証と引き継ぎ

状態: `done`

総合監査:

- P1-01〜P1-08はすべて`done`で、各完了条件と検証記録を確認した。
- project/lock/artifact versionは`0.1.2`、requires-pythonは`>=3.10`で一致する。
- CIとpublish test matrixはPython 3.10〜3.14、uvは`0.11.3`で固定され、CIは独立lock check、publishはartifact gateを持つ。
- subprocess失敗はCLI境界でexit 1のClick errorとなり、READMEは測定範囲、既知制約、sdist buildの安全性を記載する。
- regression tests、artifact verifier、publish workflow contractがPhase 1変更を継続検証する。
- working treeは総合監査開始時点でP1-09の進捗文書変更だけを含み、`main`は`origin/main`より7コミット先行していた。
- 直近コミットは`build: verify release artifacts before publish`、`test: strengthen phase one regression coverage`、`docs: define measurement and installation safety`、`fix: normalize uv subprocess failures`、`chore: restore release metadata and lock checks`だった。

検証:

```bash
uv lock --check
make ci-check
make test
make verify-build
uv run --locked uv-packsize --version
uv run --locked uv-packsize six --python 0.0
git diff --check
git status --short --branch
git log -5 --oneline --decorate
```

結果:

- `uv lock --check`は成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全25テストが成功した。
- wheelとsdistを再buildし、metadata、archive構造、installed entry pointを検証した。
- CLI versionはexact `uv-packsize, version 0.1.2`だった。
- 無効な`--python 0.0`はexit 1で、`Invalid version request`を含む簡潔なuv診断を表示し、Python tracebackはなかった。
- whitespace errorはなかった。

Phase 1判定:

- Phase 1は9 / 9タスクの完了条件を満たしたため`done`とする。
- GitHub Actions上のCI/publish workflow実走、release、tag、PyPI publishは未検証・未実施として残す。
- 次のタスクはP2-01とし、Phase 2全体の詳細分解はP2-01のmodel判断後に行う。

### 2026-07-19: P1-08 distribution artifactの検証

状態: `done`

artifact検証:

- `uv build --no-sources`で`dist/uv_packsize-0.1.2-py3-none-any.whl`と`dist/uv_packsize-0.1.2.tar.gz`をbuildした。
- wheel/sdistのName `uv-packsize`、Version `0.1.2`、Requires-Python `>=3.10`をarchive内部metadataから検証した。
- wheelのCRC、`Requires-Dist: click`、critical modules、`uv-packsize = uv_packsize.cli:cli` entry pointを検証した。
- sdistはextractせず、single root、absolute pathと`..`の不在、link/device等の危険なmember type不在、pyproject/README/LICENSE/critical modulesを検証した。
- publish対象inventoryは期待するwheel 1個とsdist 1個だけを許可し、stale version等のunexpected fileを自動削除せず失敗する。uvが生成するhidden `dist/.gitignore`はpublish対象外として扱う。
- workspace外のtemporary directoryから`uv run --isolated --no-project --with <absolute wheel> -- uv-packsize --version`を実行し、exact `uv-packsize, version 0.1.2`を確認した。
- hard-codeした期待metadataはP1-08の`0.1.2`専用であり、source側の値はP1-02/P1-07のproject metadataとlock一致テストで別途固定している。

publish workflow:

- test matrixをPython 3.10〜3.14へ更新し、test/deploy双方のuvを`0.11.3`へ固定した。
- deployの`needs: [test]`を維持し、`make verify-build`成功後にpublish actionを実行する。
- F-006を解消した。

generated artifacts:

- `dist/`をroot `.gitignore`へ追加した。
- 検証で生成したwheel、sdist、uv生成の`dist/.gitignore`はignored fileとしてworkspaceに残した。既存artifactの削除は行っていない。

検証:

```bash
make verify-build
find dist -maxdepth 1 -type f -print | sort
uv run --locked python -m zipfile -l dist/uv_packsize-0.1.2-py3-none-any.whl
uv run --locked python -m tarfile -l dist/uv_packsize-0.1.2.tar.gz
uv run --locked pytest tests/test_uv_packsize.py -q -k 'publish_workflow or build_verifier'
make ci-check
make test
uv lock --check
ruby -e 'require "yaml"; YAML.safe_load(File.read(".github/workflows/publish.yml"), aliases: true)'
git diff --check
```

結果:

- `make verify-build`は複数回成功し、wheel/sdist metadata、archive構造、installed entry pointを検証した。
- wheelとsdistのfile listingを確認した。
- P1-08のworkflow/inventory対象テスト2件は成功した。
- Ruff format check、Ruff lint、ty、README生成整合性はすべて成功した。
- 全25テストが成功した。
- `uv lock --check`、publish workflowのYAML parse、whitespace checkは成功した。

未検証・制約:

- isolated wheel smokeはwheel自体を絶対pathで指定するが、依存`click`の解決にはuv cacheまたはpackage indexを利用し得る。
- GitHub Actions上のpublish workflow実走と、release/PyPI publishは実施していない。
- Phase 1の総合検証とPhase 2への引き継ぎはP1-09で行う。

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

### 2026-07-31: P4-03d `--write-baseline` CLI/public contract

状態: `done`

変更:

- fresh install専用の`--write-baseline PATH`と、既存targetの明示的置換用`--overwrite-baseline`をCLIへ接続した。後者だけの指定、`--prefix`または`--baseline`との併用はexternal I/O前にusage errorとなる。
- write modeは最初の計算progressから完了表示までstderrへ送り、analysisとtext presentationの成功後、stdoutの直前にfresh baselineをrenderしてatomic writerへ一度だけ渡す。render/write失敗はpathやOS診断を出さないexit 3へ正規化し、stdoutを空にする。
- `--json --write-baseline`はrender済みpayloadを再renderせずstdoutへ出すため、保存ファイルとstdoutのbytesは完全に一致する。通常text、`--bin`、`--explain`、`--breakdown`、`--contributions`は保存payloadを変えない。
- READMEへwrite/no-clobber/explicit overwrite、stdout/stderrとexit 3、POSIXの0600 atomic publication、trusted parent policy、directory durabilityのplatform依存、Windows等では既存`--json > baseline.json`を使うportable fallbackを記載した。

検証:

```bash
uv run --locked pytest tests/test_uv_packsize.py -q
uv run --locked pytest tests/test_local_wheel_integration.py -q
make ci-check
make test
uv lock --check
make build
uv run --locked python scripts/verify_build.py dist
```

結果:

- CLI unit 101件、network-free local wheel integration 16件が成功した。local E2EはJSON stdout/file bytes一致、0600、直後のtext/comparison JSON read、no-clobber時の元bytes保持、explicit overwrite後の再loadを確認した。
- text write modeは`--bin`、`--explain`、`--breakdown`、`--contributions`ごとにbaseline payloadがplain fresh v1 JSONと同一で、writerが一度だけ呼ばれ、graph optionではgraph builderも一度だけ呼ばれることを固定した。presentationまたはgraph失敗ではwriterを呼ばずtargetを作らずstdoutを空にする。`--json --write-baseline`とtext-only optionsの組合せはgraph builderを呼ばず、plain write JSONとstdout/file bytesが同一であることも固定した。
- `make ci-check`、全696 passed/2 skippedの`make test`、`uv lock --check`、wheel/sdist build、artifact verifier、`git diff --check`も成功した。

次のタスク:

- P4-04aでbaseline write/readの契約を前提にbudget policyのpure domain modelを設計・実装する。

## 発見事項・後続候補

新しい問題を発見した場合は、既存タスクへ無断で混ぜず、ここへ一時記録してから適切なPhaseへ割り当てる。

| ID | 発見事項 | 割り当て | 状態 |
|---|---|---|---|
| F-001 | `RECORD`のsite-packages外パスを除外しており、scripts/data/headersを完全には測定できない | P2-02a/P2-02b/P2-04b2 | `done` |
| F-002 | `--bin`がWindowsの`Scripts`を分析しない | P2-02b/P2-04b1/P2-06b | `done` |
| F-003 | 1024基準の値を`KB/MB`と表示している | P2-04b1/P2-04b2 | `done` |
| F-004 | 通常の成功系testがPyPIとpackage indexのavailabilityに依存している | P2-06a/P2-06b | `done` |
| F-005 | sdist build backendを暗黙に実行する可能性がある | P2-07 | `done` |
| F-006 | publish workflowのtest matrixがPython 3.9〜3.13のままで、projectの対応範囲と一致しない | P1-08 | `done` |
| F-007 | 実際にbuildされたdistributionのprovenanceを、uv diagnosticsやcacheから安全に確定できない。stableな上流featureと対応versionが確定するまで推測しない | P6-03（上流Issue草案）、上流stable feature待ち | `blocked` |
| F-008 | 既存`load_baseline()`はdescriptor close時の`OSError`をsanitized `BaselineLoadError`へ変換しない。body errorを優先し、成功body後のclose failureではparseへ進まないdescriptor lifecycleへhardeningした | baseline read hardening | `done` |
| F-009 | P4-04dの`pyproject.toml` source readerへpre/open/postのdevice、inode、mode、size、mtime_ns、ctime_ns再照合を追加し、同一inode・同一lengthを含む観測可能なrewriteを拒否した。filesystem-level immutable snapshotは保証しない | config source observable rewrite hardening | `done` |
| F-010 | CLI text polishは、P0のsecurity基盤や包括的なUX redesignと混在させず、リリース後の独立タスクとして扱う。terminal-safe共通display/table primitives、opt-in rich summary、progressだけを抑止する`--quiet`、default-offのTTY colorを完了した | リリース後のCLI text polish | `done` |
| F-011 | GitHub ActionsのNode.js 20廃止予告へ対応し、`setup-uv@v7`、`configure-pages@v6`、`upload-pages-artifact@v5`、`deploy-pages@v5`へ更新した。local検証は完了し、push後のCI/Pages実runとannotation消滅確認が残る | Node 24対応Actions major update | local `done` / deployment verification pending |
