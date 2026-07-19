# uv-packsize 実装計画・進捗

最終更新: 2026-07-19

この文書は、[`roadmap.md`](./roadmap.md)を実行可能なタスクへ分解し、現在の作業位置、完了条件、検証結果を一か所で追跡するための単一の管理表である。エージェントの作業規則は[`AGENTS.md`](../AGENTS.md)を参照する。

## 現在の状態

| 項目 | 状態 |
|---|---|
| 現在のPhase | Phase 2: 信頼できる測定エンジン |
| `in_progress` | なし |
| 次のタスク | P2-04: 既存temporary venv/CLIを`AnalysisResult`測定engineへ接続する |
| Phase 1進捗 | 9 / 9 完了（Phase 1 `done`） |
| Phase 2進捗 | 4タスク完了（P2-01、P2-02a、P2-02b、P2-03 `done`） |
| Blocker | なし |
| 次の成果物 | 現行CLIから新測定engineを使用するend-to-end flow |

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
| Phase 2 | 信頼できる測定エンジン | `in_progress` |
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
| P2-04 | Phase 2 | 既存temporary venv/CLIを`AnalysisResult`測定engineへ接続する | `todo` |
| P3-01 | Phase 3 | installed metadataからdependency graphを構築する | `todo` |
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

## 作業記録

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
| F-001 | `RECORD`のsite-packages外パスを除外しており、scripts/data/headersを完全には測定できない | Phase 2 | `todo` |
| F-002 | `--bin`がWindowsの`Scripts`を分析しない | Phase 2 | `todo` |
| F-003 | 1024基準の値を`KB/MB`と表示している | Phase 2 | `todo` |
| F-004 | 通常の成功系testがPyPIとpackage indexのavailabilityに依存している | Phase 2 | `todo` |
| F-005 | sdist build backendを暗黙に実行する可能性がある | Phase 2 | `todo` |
| F-006 | publish workflowのtest matrixがPython 3.9〜3.13のままで、projectの対応範囲と一致しない | P1-08 | `done` |
