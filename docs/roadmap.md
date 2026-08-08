# uv-packsize ロードマップ

最終更新: 2026-07-19

実際のタスク状態と検証記録は[`implementation-plan.md`](./implementation-plan.md)で管理する。

## 1. この文書の目的

`uv-packsize` の現在地を整理し、単発のパッケージサイズ表示ツールから、Pythonプロジェクトの依存フットプリントを継続的に把握・比較・制御できるツールへ発展させるための方針を示す。

このロードマップでは、次の問いに答えられる状態を目標とする。

1. このパッケージと依存関係をインストールすると、どれだけの容量になるか。
2. どの依存関係やファイル種別が容量を占めているか。
3. バージョン更新や依存変更によって、何がどれだけ増減したか。
4. CIで定めた容量予算を超えていないか。

## 2. 現状

現在のCLIは、次の手順でパッケージサイズを計測している。

1. 一時ディレクトリにvirtual environmentを作成する。
2. `uv pip install`で指定パッケージと依存関係をインストールする。
3. 各distributionの`.dist-info/RECORD`を読み、所有ファイルの論理サイズを集計する。
4. オプション指定時は`.venv/bin`のファイルサイズも加算する。
5. distributionごとのサイズと合計を人間向けテーブルとして表示する。

中心実装は[`uv_packsize/cli.py`](../uv_packsize/cli.py)にあり、依存ライブラリも`click`のみで、コード量の小さいCLIとして保守しやすい状態にある。

調査時点では、以下を確認した。

- 11件のテストが成功する。
- Ruffのformat/lint、tyの型チェック、README生成チェックが成功する。
- `requests==2.32.5`の実計測では、5 distributions、合計約2.26 MiB相当を検出できる。
- ローカル`main`には、従来のディレクトリ名ベース集計を`RECORD`ベースへ改善する未公開コミットがある。
- PyPIで公開されている最新版は`0.1.1`である。

## 3. 目指す位置づけ

一時venvへ実際にインストールし、`RECORD`から論理サイズを求める方式自体は妥当である。一方、同様の方法を採用する[pip-weigh](https://github.com/muddassir-lateef/pip-weigh)は、JSON出力、容量予算、依存ツリー、クロスプラットフォーム指定をすでに提供している。

また、周辺領域には次のツールや機能がある。

- `uv tree --show-sizes`: 解決された依存関係と圧縮wheelサイズを表示する。
- [pydistcheck](https://pypi.org/project/pydistcheck/): wheelやsdist単体の圧縮・展開サイズと内容を分析する。
- [pypkgsize](https://github.com/crkacer/pypkgsize): 既存環境のパッケージサイズを分析する。

したがって、`uv-packsize`は単にサイズ表を高機能化するのではなく、次の領域へ集中する。

> uvで解決・インストールされる依存関係の実フットプリントを、再現可能な形式で記録し、変更理由の説明とCI上の容量制御につなげる。

主要な差別化要素は以下とする。

- installed logical sizeの明確で信頼できる測定仕様
- `uv.lock`、`pyproject.toml`、dependency groupsとの連携
- direct、transitive、shared dependencyの区別
- バージョン、extras、Python、platform間の比較
- baseline差分と容量予算によるCI制御
- 安定したversioned JSON schema

## 4. 現在の課題

### 4.1 ロックファイルとリリースの不整合

[`pyproject.toml`](../pyproject.toml)のプロジェクトバージョンは`0.1.1`だが、[`uv.lock`](../uv.lock)内では`0.1.0a1`になっている。また、[`makefile`](../makefile)が`uv run --frozen`を使用しているため、ロックファイルが古くても通常のチェックが成功する。

実際に`uv lock --check`を実行すると、ロックファイルの更新が必要だと判定された。

対応方針:

- 次回リリースを`0.1.2`へ上げる。
- `uv.lock`を更新する。
- CIでは`--frozen`ではなく`--locked`を使用する。
- `uv lock --check`を独立したCIチェックとして追加する。
- build後のwheel/sdistメタデータと期待バージョンを検証する。

### 4.2 「サイズ」の意味が曖昧

現状のREADMEには、次の点が定義されていない。

- 圧縮wheelサイズか、インストール後の論理サイズか。
- Python本体、virtual environment、uvキャッシュを含むか。
- `.pyc`を含むか。
- console scripts、headers、data filesを含むか。
- hardlink、clone、symlinkをどのように扱うか。
- 複数のルートパッケージで共有される依存をどう扱うか。

デフォルトの測定値を、次のように定義する。

> 対象のPython・platform・解決条件に対してインストールされたdistribution所有ファイルのlogical bytes。Pythonインタープリター、virtual environmentの基礎ファイル、uvキャッシュは含めない。

表示単位は、1024基準であれば`KiB`、`MiB`、`GiB`を使用する。

### 4.3 `RECORD`の一部しか集計していない

[Python Packagingの`RECORD`仕様](https://packaging.python.org/en/latest/specifications/recording-installed-packages/)では、パスは絶対パス、または`.dist-info`のあるディレクトリからの相対パスとして記録できる。site-packages外のscriptsやdataも含まれ得る。

現在の実装はsite-packages外のパスをすべて除外し、`--bin`指定時のみ`.venv/bin`を別集計している。そのため、次の問題がある。

- scriptsを所有distributionへ帰属できない。
- `bin`以外へ配置されるdataやheadersを見落とす。
- Windowsの`Scripts`ディレクトリを分析しない。
- `RECORD`欠落時にdistribution本体ではなく`.dist-info`だけを数える。
- 不完全な測定結果を明示できない。

対応方針:

- temporary prefix全体を測定スコープとして扱う。
- `RECORD`に記録された各ファイルをdistributionへ帰属させる。
- ファイルを`python`、`native`、`data`、`metadata`、`script`などへ分類する。
- `RECORD`欠落、存在しないファイル、重複所有をwarningまたはerrorとして結果に残す。
- logical sizeと実ディスク占有量を混同しない。

### 4.4 結果の再現条件が残らない

現在の出力には、distribution名とサイズしか含まれない。比較可能な結果には少なくとも次が必要である。

- 入力requirements
- 解決されたdistribution名とversion
- direct / transitiveの区別
- dependency edgesと導入理由
- Python version
- OS、architecture、target platform
- uv version
- extras、index、resolution strategy
- bytecode compilationの有無
- 測定日時
- 測定結果が完全か不完全か
- JSON schema version

これらを内部の`AnalysisResult`に保持し、人間向け表示とJSON出力を同じデータから生成する。

### 4.5 エラー処理

virtual environment作成時の`subprocess.CalledProcessError`が変換されていないため、無効なPython指定などでPython tracebackがそのまま表示される。

対応方針:

- subprocess呼び出しを1つのadapterへまとめる。
- stdout、stderr、exit codeを保持した専用例外を用意する。
- CLI境界で`click.ClickException`へ変換する。
- ユーザー向けメッセージと`--verbose`の診断情報を分離する。
- resolver failure、Python discovery failure、build failure、invalid metadataを別のexit codeまたはerror kindとしてJSONへ残す。

### 4.6 sdistビルドの安全性

通常の`uv pip install`は、wheelがない場合にsdistをビルドできる。つまり、サイズを確認するだけの操作でも第三者のbuild backendを実行する可能性がある。

対応方針:

- デフォルトは`--no-build`によるwheel-onlyモードにする。
- sdistが必要な場合は`--allow-build`で明示的に許可する。
- 結果には、buildを許可したかどうかのpolicyだけを記録する。uvの診断やcache内容から実際にbuildしたdistributionを推測しない。
- 実際にbuildされたdistributionのprovenanceは、uvが信頼できるmachine-readableな情報を提供できる段階で上流連携として扱う。
- クロスプラットフォーム分析はwheel-onlyに限定する。

### 4.7 テストの外部依存

現在のintegration testsはPyPI上の実在パッケージや存在しないパッケージ名に依存する。この構成は、ネットワーク障害、index障害、パッケージ削除、resolverメッセージ変更の影響を受ける。

対応方針:

- テスト用wheel fixtureをリポジトリ内で生成または保持する。
- local `--find-links` indexを使ってresolverとinstallerをテストする。
- unit tests、local integration tests、PyPI smoke testsを分離する。
- PyPI smoke testは定期実行または手動実行とし、通常PRの必須条件にしない。
- Linux、macOS、Windowsのpath layoutをfixtureで検証する。

### 4.8 Pythonサポート範囲

Python 3.9は2025-10-31にEOLとなった一方、現在のCIにはPython 3.14が含まれていない。[Python Developer's Guide](https://devguide.python.org/versions/)

明確な互換性要件がなければ、次回minor releaseで`requires-python = ">=3.10"`とし、CI対象を3.10から3.14に更新する。

## 5. 推奨アーキテクチャ

現在の単一CLIモジュールへ機能を追加し続けず、次の責務へ分離する。

```text
ResolutionContext
    -> Installer
    -> File Inventory
    -> Dependency Graph
    -> Analysis / Budget / Diff Policy
    -> Renderer (text / JSON / CSV)
```

### ResolutionContext

入力requirements、Python、platform、extras、index、resolver optionなど、解決結果に影響する条件を保持する。

### Installer

`uv`の呼び出しと一時環境を管理する。venv、`--target`、`--prefix`の違いを上位層へ漏らさない。

一時venvは当面維持してよい。`uv pip install --target`や`--prefix`への変更は、測定仕様とfixtureを確立した後にベンチマークして判断する。

### File Inventory

distributionごとの合計だけではなく、ファイル単位で次を保持する。

- distribution名とversion
- 絶対パスまたは測定prefixからの相対パス
- logical bytes
- file category
- `RECORD`由来か、補完検出か
- symlink、hardlinkなどの属性
- warningまたは不完全性

集計値はこのinventoryから導出する。

### Dependency Graph

任意のrequirementsをインストールするモードでは、インストール済みCore Metadataの`Requires-Dist`とenvironment markersからグラフを構築する。

uvプロジェクトやlockfileを分析するモードでは、明示された`--project`と`--lockfile`だけを読む限定的な直接`uv.lock` readerを用いる。readerは、このプロジェクトが検証したlock formatの`version`/`revision`組合せと、その用途に必要な閉じたfield subsetだけをallowlistで受ける。PEP 621の非selection project field、標準`[build-system]`/`[tool]` table、v1/revision 3のlock contextとartifact recordは、既知のtable/field shapeを検証してから無視する。ただし`[tool.uv]`の`default-groups`は暗黙のdependency group選択を変えるため、readerの明示selectionと混同せず安全に拒否する。他の`tool.uv`設定を一般的に拒否して互換範囲を恣意的に狭めない。一方、root name、dependency group、extra、dynamic extra、root metadataのgroup/extra整合などselectionへ影響するsemanticは明示的に検証し、未知・欠損・不正なschema、未知の必須semantic、曖昧なpackage/selectionは推測やpartial graphへのfallbackをせず拒否する。入力fileはleafだけでなく全parent componentのsymlinkを拒否し、bounded readの前後でdevice/inode/mode/size/mtime/ctimeを再照合する。ただし、同一descriptor上の内容をimmutable snapshotにするものではないため、入力は安定したtrusted directoryに置く。readerはworkspace metadataを起動・入力・補完に使わず、raw TOML、path、source URL、credential、opaque IDを公開result、baseline、利用者向けdiagnosticへ出力しない。

project/lockのinstall adapterは、readerが一度の安全読込で検証したproject/lock bytesをprivate snapshotとして受け取り、標準名`pyproject.toml`と`uv.lock`でunique temporary staging directoryへだけ配置する。そこで`UV_PROJECT_ENVIRONMENT`を別のunique absolute temporary prefixに設定し、`uv sync --project <staging directory> --locked --no-install-project --no-default-groups`に、検証済みselection由来の`--group`/`--all-groups`と`--extra`だけを追加して実行する。子processのenvironmentはPATHとOSが実行に必要とする最小変数、temporary root内のprivate `UV_CACHE_DIR`だけから構築し、`UV_PROJECT_ENVIRONMENT`と`UV_NO_CONFIG=1`を明示する。ambientの`UV_*`、active virtual environment、index/source/build configuration、外部`uv`設定は継承しない。private cacheもstaging/targetと同じcleanup対象である。これにより、staged `[tool.uv]`のうちreaderが安全に無視した一般設定もselection/build policyを暗黙に変えない。`--lockfile`は使わず、隣接する標準名lock fileを`uv`へ解決させる。`--frozen`はlock freshnessを検査しないので使わない。original inputの再読・更新、ambient project discovery、workspace metadataは行わない。

staged rootのlocal installは`--no-install-project`により行わない。root sourceはv1/revision 3で実際に生成されるexactな`{ editable = "." }`または`{ virtual = "." }`だけを受理する。前者は通常の`uv sync`ならrootをeditable installし得るproject、後者はbuild-systemを持たないvirtual rootを表すが、project/lock modeではいずれもrootをinstall・測定しない。この差を結果へ推測して出力しない。non-rootはexactな`registry` sourceだけを受理し、registry値がlocal wheelhouse pathであっても、同じlock内のexactな`{ path = "..." }` wheel artifact recordとともに、locked installが読むopaqueなlocationとして検証後に保持する。これらpath/URLは選択済みartifactのlocationであり、公開result、baseline、errorへ反射しない。一方、dependencyの`path`、`directory`、`editable`、`virtual`、VCSなどregistry以外のsource kind、artifact recordの未知key/shapeはsupported subset外として拒否する。defaultのwheel-only policyは`uv sync`でも維持し、source buildは`--allow-build`の明示opt-inだけで許可する。

`uv sync`はstale lockなどの失敗後にもtarget prefixの骨組みを残し得る。そのためstaging directoryとtemporary prefixは成功、installer/inventory failure、例外のすべてでfinally cleanupする。cleanupはユーザー指定inputや既存prefixを対象にせず、失敗時もraw path、command、`uv` diagnosticを利用者向けoutputへ出さない。

[`uv workspace metadata`](https://docs.astral.sh/uv/reference/internals/metadata/)は別の将来adapter候補として隔離する。P5-01で確認した`uv 0.11.3`の`schema.version: "preview"`は通常CLI、baseline、CI比較の入力として常に非対応である。将来追加する場合も、上流がnumericかつstableと宣言したschema versionを出力し、このプロジェクトが明示的に支持してからに限る。

### Policy

同じ分析結果に対して、次のポリシーを適用できるようにする。

- total size上限
- baselineからの最大増加量
- 特定distributionの上限
- native/data/scriptなどカテゴリ別上限
- incomplete resultをCI失敗にするか

### Renderer

内部結果と表示を分離し、最低限次を提供する。

- 人間向けtable/tree
- versioned JSON
- 必要になった段階でCSVまたはMarkdown

## 6. ロードマップ

### Phase 0: 測定契約と継続判断（1〜2日）

目的:

- プロダクトの範囲を決め、競合と重なる機能を無計画に実装しない。

実施項目:

- installed logical sizeの定義をREADMEへ記載する。
- 想定利用者を「Docker/Lambda等のデプロイ容量を管理したいuv利用者」と仮定し、実際の利用目的と照合する。
- wheel-onlyをデフォルトとする安全方針を決める。
- one-shot calculatorだけが必要なら、既存ツール利用、連携、または上流`uv`への貢献も選択肢にする。

完了条件:

- 同じ入力に対して「何を含み、何を含まないか」を説明できる。
- 継続開発する差別化領域が、project/lock連携、diff、budgetのいずれかに定まっている。

### Phase 1: リリース品質の回復（1週目）

実施項目:

- versionを`0.1.2`へ更新する。
- `uv.lock`を同期する。
- CIを`--locked`へ変更する。
- `uv lock --check`を追加する。
- subprocess errorを利用者向けエラーへ変換する。
- Python 3.10〜3.14でCIを実行する。
- build artifactのversionとmetadataを検証する。
- 現在ローカルにある`RECORD`ベースの修正をリリース可能な状態にする。

完了条件:

- stale lockでCIが失敗する。
- 無効なPythonや解決失敗でtracebackを表示しない。
- PyPIへ`0.1.2`として再現可能に公開できる。

### Phase 2: 信頼できる測定エンジン（2〜3週目）

実施項目:

- `ResolutionContext`、`DistributionResult`、`FileEntry`、`AnalysisResult`を導入する。
- resolved versionと環境情報を取得する。
- `RECORD`に記録されたprefix全体のファイルを分析する。
- scripts/data/headersをdistributionへ帰属させる。
- Windows `Scripts`を含むplatform fixtureを追加する。
- 欠損・不正・重複したmetadataをwarningとして保持する。
- `KiB`、`MiB`、`GiB`表記へ変更する。
- versioned JSON schemaを追加する。
- PyPI依存テストをlocal wheel fixtureへ置き換える。

完了条件:

- 全FileEntryの合計とdistribution total、global totalが一致する。
- 同一入力・同一環境で繰り返したJSON結果が、測定日時など明示的な可変項目を除いて一致する。
- Linux、macOS、Windows layoutのgolden testsが成功する。

### Phase 3: サイズの理由を説明する（4〜5週目）

実施項目:

- direct、transitive、shared dependencyを区別する。
- 各distributionが導入された依存経路を表示する。
- self sizeとtransitive totalを分ける。
- Python/native/data/metadata/script別の内訳を表示する。
- 既存virtual environmentまたはprefixを分析するモードを追加する。
- 複数root package間のshared dependencyを二重計上しない。

完了条件:

- 「合計が大きい」だけでなく、上位の増加要因と導入経路を説明できる。
- 複数root packageの合計と個別寄与の関係が明示される。

### Phase 4: CIでの継続管理（6〜7週目）

実施項目:

- JSON baselineの保存と読込を実装する。
- `compare`または同等の差分機能を追加する。
- `--max-total`、`--max-increase`を追加する。
- budget超過、分析失敗、不完全結果のexit codeを定義する。
- `pyproject.toml`でポリシーを設定できるようにする。
- GitHub Actionsの最小利用例を用意する。

Phase 4の残作業は、domain policy（P4-04a）、pure presentation（P4-04b）、trusted policy mapping normalizer（P4-04c）、`pyproject.toml` source resolution/file I/O、CLI/config選択、exit code、CI exampleへ分割して進める。入力source、公開契約、CI integrationをdomain modelと同じ変更単位に混ぜない。CLI接続では自動config discoveryを行わず、明示sourceとfield単位のCLI overrideだけを受ける。policy未選択時の既存CLI/JSON契約は不変とし、budget violationはoperational failureと区別した専用exit codeで表す。

完了条件:

- dependency updateのPRで、増減したdistributionとbyte数を表示できる。
- 設定した容量予算を超えた場合だけCIを失敗させられる。
- baseline schemaの互換性を検査できる。

### Phase 5: project/lockと比較分析（8週目以降）

実施項目:

- `pyproject.toml`、`uv.lock`、dependency groupsを入力として扱う。
- 明示された`--project`/`--lockfile`から、allowlistした`uv.lock` schemaだけを直接読む。未知schemaは拒否し、`uv workspace metadata`は使わない。`schema.version: "preview"`だけの出力はP5-01で非対応と固定した。
- 検証済みsnapshotをtemporary staging経由で`uv sync --locked --no-install-project`へ適用し、元のproject/lockを変更せずtemporary prefixを測定する。stale lockを含む失敗後もtemporary staging/prefixをcleanupする。
- 初期project/lock modeではlocal root packageをinstall・測定せず、lockだけで再現不能またはbuild code実行につながるlocal sourceを拒否する。
- package version、extras、Python version、platform間を比較する。
- installed logical sizeとcompressed wheel sizeを並べる。
- Linux wheelをmacOSやWindows上で分析するwheel-onlyモードを追加する。
- Docker、Lambdaなど用途別profileの必要性を検証する。

完了条件:

- 実際のuvプロジェクトについて、現在のlockと変更後のlockを比較できる。
- platform固有wheelを混同せず、測定contextを結果から再構築できる。
- original project/lockを変更せず、offline local-wheel fixtureでlocked install、selection、cleanup、sanitized failureを再現できる。

### Phase 6: エコシステム連携（必要性を確認後）

候補:

- 再利用可能なPython APIの公開
- GitHub ActionまたはPR comment integration
- `pydistcheck`との役割分担・連携
- `uv tree --show-sizes`へのinstalled-size追加提案
- 標準化可能なJSON schemaや測定契約の公開

Phase 6では、既存CLIの再利用より大きい価値が確認できるまで、custom
GitHub Action、PR comment、baselineの自動更新を追加しない。まずはexplicit
project/lock、read-only baseline、budget、comparison JSONを使う最小workflowを
公開し、job summaryにはsafeな固定fieldだけを出す。この形ならfork PRやsecretsを
必要とせず、baseline更新はreview可能な別変更として保てる。

`uv workspace metadata` はpreviewかつschemaが安定していないため、通常CLI、
baseline、CI比較の入力にはしない。実際にsource buildされたdistributionの
provenanceなど、現在の公開出力だけでは安全に確定できない情報は推測しない。
必要な上流機能は、提出前にローカルのissue草案として要件・安全境界・非目標を
整理し、GitHubへの投稿は明示承認を得てから行う。

## 7. 当面実装しないもの

次は、測定の信頼性とCI利用が確立するまで優先しない。

- Web dashboard
- 独自dependency resolver
- 大規模なTUIや装飾中心の出力
- 根拠のない「軽量な代替パッケージ」推薦
- 独自の永続キャッシュ層
- import解析による未使用依存の自動削除
- SBOM、license、脆弱性分析の全面的な再実装

これらは別ツールの責務と重なりやすく、現在の目的であるフットプリント測定と回帰検知を不明瞭にする。

## 8. 成功指標

### 正確性

- inventoryの合計と表示totalが一致する。
- `RECORD`欠落などの不完全測定を正常値として扱わない。
- scripts、data、headersを見落とさずdistributionへ帰属できる。

### 再現性

- 入力、解決結果、Python、platform、uv versionをJSONから確認できる。
- 同じcontextの実行結果が安定する。
- lockfileが古い場合はCIが失敗する。

### 安全性

- デフォルトでは第三者のsdist build backendを実行しない。
- buildを許可した場合は結果に記録される。

### 利用価値

- 容量の大きいdistributionと導入理由を説明できる。
- dependency update前後の増減を比較できる。
- 容量予算をCIで強制できる。

### 保守性

- resolver、installer、inventory、graph、rendererが分離されている。
- 通常のテストが外部PyPIに依存しない。
- JSON schemaとexit codeが文書化されている。

## 9. 直近の推奨着手順

最初の実装単位は次の順序とする。

1. `0.1.2`へのversion更新と`uv.lock`同期
2. `--locked`、`uv lock --check`によるCI修正
3. subprocess errorの整理
4. 測定契約のREADME記載
5. 内部result modelとJSON出力
6. prefix全体を対象にした`RECORD` inventory
7. local wheel fixturesへのテスト移行
8. dependency graphと差分・budget機能

依存ツリーの装飾やクロスプラットフォーム比較から始めず、まず「正しい結果を機械可読に出せること」を確立する。
