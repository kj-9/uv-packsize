# uv向け provenance / stable metadata 要件 Issue 草案

状態: ローカル草案。GitHub Issueは未作成・未投稿。投稿、検索、更新はユーザーの明示承認後にだけ行う。

対象: `uv` が、ロック済みprojectの選択結果とsource buildの実行結果を、測定・CIツールが安全に消費できる形で提供できるようにする提案。

## 問題

`uv-packsize`は、ロック済みprojectをprivate staging directoryへ配置し、`uv sync --locked`で一時環境へ同期してinstalled logical sizeを測定する。現在、source buildを既定で拒否し、`--allow-build`を明示した場合だけ許可する。しかし、公開されたmachine-readableな根拠だけから「このrunでどのdistributionが実際にbuildされたか」「選択済みartifactは何だったか」を安全に確定する方法はない。

`uv workspace metadata`は、公式ドキュメントでpreview / schema不安定とされている。`schema.version: "preview"`は、通常CLI、baseline、CI comparisonの互換境界として使えない。そのため、preview JSONやhuman-readable diagnostics、cacheの痕跡をparseしてprovenanceを推測するのは安全でなく、`uv-packsize`では行わない。

ロックファイルのversioning自体は重要な互換境界であり、locked semanticsも安定して機械判定できる必要がある。現状は、必要な範囲に限った直接`uv.lock` readerと`uv sync --locked`を使うが、これは上流のstable metadata APIの代替を目指すものではない。

## 現行の安全境界

- preview workspace metadataは起動・parse・fixture化せず、stableでnumericなschema versionが明示されるまで通常入力にしない。
- diagnostic、cache、filesystemの副作用からbuild実績やartifact選択を推測しない。
- raw path、source URL、credential、lock contents、opaque IDを公開result、baseline、comparison、利用者向けerrorへ反射しない。
- untrustedなmetadata値をdiagnosticや表示へそのまま反射しない。固定されたcode、enum、count、検証済みのsafe fieldだけを出力する。
- `--locked`の失敗を成功やpartial resolutionへフォールバックさせない。lock freshness / selection / artifact provenanceの意味を人間向け出力から推測しない。

## 実測ツール向けの上流要件

上流が提供する場合、次の出力はstdoutの単一JSON documentなど、機械可読な明確なtransportで提供されることを希望する。

1. **安定schemaとversioning**
   - numericでstableと宣言されたschema versionを持つ。
   - 公開JSON Schemaと互換性・breaking changeのversioning方針を提供する。
   - 未知version、未知の必須semantic、schema validation failureをconsumerが安全に拒否できる。

2. **selectionの明示**
   - root、workspace member、dependency group、extraのselection entrypointと実効selectionを区別して表す。
   - marker evaluationに使ったenvironmentと、marker / conflictによって除外・競合した候補をどう扱うかの明確なguidanceを提供する。
   - selectionに関係する曖昧さやconflictを、human proseではなくstable codeで判定できる。

3. **選択済みartifactと候補の区別**
   - resolverが検討したcandidate群と、最終的にselected / installed対象となったartifactを混同しない。
   - selected artifactには、consumerが比較に使えるstable identityとartifact hashを提供する。
   - source URL、local path、credential、opaque internal IDを必須の公開identityにしない。必要ならredacted / opaqueではないstableな公開用identityを別に定義する。

4. **runごとのbuild outcomeとprovenance**
   - buildを許可したpolicyだけでなく、そのrunでbuildが実際に発生したかを明示する。
   - buildが発生した各対象について、distribution identity、入力または生成artifactの安全なidentity、artifact hash、outcomeを記録する。
   - build未実行、cache reuse、wheel download、build failureを区別する。失敗時もpartialな成功実績と混同しない。

5. **診断とlocked semantics**
   - failure / warning / incomplete outcomeを、redactedでmachine-readableなdiagnostic codeと最小のsafe structured fieldで提供する。
   - path、source URL、credential、opaque ID、任意のuntrusted package metadataをdiagnostic textやfieldへ反射しない。
   - `--locked`のfreshness検査、選択条件、lock不整合時の失敗をstable semanticsとして文書化し、consumerがexit codeだけへ過度に依存せずに判定できるようにする。

## 非目標

- `uv tree --show-sizes`へinstalled logical sizeを追加する提案ではない。
- custom GitHub Action、PR comment、baseline自動更新の提案ではない。
- `pydistcheck` APIとの統合や、その機能の再実装を求めるものではない。
- uvの内部cacheやpreview outputを外部ツールが推測して読むことを推奨しない。

## 期待する次の進め方

- uv側で既存または計画中のstable machine-readable APIとの重複・適切なsurfaceを確認する。
- 上記を満たす最小schemaの可否、schema lifecycle、redaction policy、locked/build outcome semanticsを議論する。
- stable featureが提供され、supported versionと安全なfieldが確定するまで、`uv-packsize`のF-007は未解決のままとする。

## 提出用英語本文（draft）

**Title:** Provide stable, versioned machine-readable selection and build provenance for locked project runs

`uv-packsize` measures the installed logical footprint of a locked project in a private temporary environment. It intentionally defaults to wheel-only operation and only permits source builds through an explicit opt-in. Today, however, a consumer cannot safely determine from a public machine-readable interface which distributions were actually built in a particular run, nor distinguish a resolved selected artifact from candidates considered by the resolver.

We do not use `uv workspace metadata` for this purpose. The official documentation describes it as preview / unstable, and `schema.version: "preview"` is not a compatibility boundary suitable for normal CLI output, baselines, or CI comparisons. Parsing human diagnostics, cache state, or filesystem side effects to infer provenance would also be unsafe.

Could uv provide a stable machine-readable surface for locked project runs with the following properties?

1. A numeric, stable schema version; a published JSON Schema; and documented compatibility / breaking-change versioning.
2. Explicit selection entrypoints and effective selection for roots, workspace members, dependency groups, and extras. Please document marker evaluation and how excluded or conflicting candidates are represented.
3. A clear distinction between resolver candidates and the final selected artifact. Selected artifacts should have a safe stable identity and artifact hash without making a path, source URL, credential, or opaque internal ID a required public identity.
4. Per-run build outcome and provenance: whether a build occurred, the distribution identity, safe input/output artifact identity, artifact hash, and a distinction among no build, cache reuse, wheel download, build success, and build failure.
5. Redacted machine-readable diagnostics with stable codes and minimal safe fields. Paths, source URLs, credentials, opaque IDs, and arbitrary untrusted metadata should not be reflected verbatim. Please also document stable locked semantics for freshness, selection, and lock mismatch so consumers do not have to infer them from prose or exit codes alone.

Non-goals: this is not a request to add installed logical sizes to `uv tree --show-sizes`, to create a custom GitHub Action or PR-comment workflow, or to integrate with the `pydistcheck` API. It is also not a request for consumers to parse uv's cache or preview output.

Our current fallback is an intentionally narrow direct `uv.lock` reader plus `uv sync --locked`, with conservative rejection of unsupported inputs. That does not solve actual build provenance. We would be glad to validate a proposed stable schema with an offline local-wheel fixture.

References:

- https://docs.astral.sh/uv/reference/internals/metadata/
- https://docs.astral.sh/uv/concepts/resolution/#lockfile-versioning
