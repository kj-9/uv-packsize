# uv-packsize 実装計画・進捗

最終更新: 2026-07-31

この文書は、[`roadmap.md`](./roadmap.md)を実行可能なタスクへ分解し、現在の作業位置、完了条件、検証結果を一か所で追跡するための単一の管理表である。エージェントの作業規則は[`AGENTS.md`](../AGENTS.md)を参照する。

## 現在の状態

| 項目 | 状態 |
|---|---|
| 現在のPhase | Phase 3: サイズの理由を説明する（`in_progress`） |
| `in_progress` | なし |
| 次のタスク | P3-04: 既存virtual environmentまたはprefixを分析する入力modeを設計する |
| Phase 1進捗 | 9 / 9 完了（Phase 1 `done`） |
| Phase 2進捗 | 12 / 12タスク完了（Phase 2 `done`） |
| Blocker | なし |
| 次の成果物 | existing environment/prefix input modeの設計 |

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
| Phase 3 | サイズの理由を説明する | `in_progress` |
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
| P3-04 | Phase 3 | 既存virtual environmentまたはprefixを分析する入力modeを設計する | `todo` |
| P3-05 | Phase 3 | 複数rootの個別寄与とshared dependencyの非二重計上を表示・検証する | `todo` |
| P4-01 | Phase 4 | baseline JSONと差分ポリシーを設計する | `todo` |
| P5-01 | Phase 5 | `uv workspace metadata`の対応schemaを調査・固定する | `todo` |
| P6-01 | Phase 6 | 上流連携の費用対効果を再評価する | `todo` |

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

## 作業記録

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
| F-007 | 実際にbuildされたdistributionのprovenanceを、uv diagnosticsやcacheから安全に確定できない | P6-01（上流連携） | `todo` |
