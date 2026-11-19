# api-price

A small, reviewable catalog of public text-token API prices used by local
tools such as Infra Sentinel. It maps exact consumer-visible model IDs to
documented rates; it does not infer prices from model-family names.

The catalog is a reference, not a provider invoice. Storage, tools, grounding,
multimodal input, regional processing, priority service, subscriptions, and
request-level context uplifts remain out of scope unless a catalog row says
otherwise.

Latest review: [2026-11-19](reviews/2026-11-19.md) — 122 model IDs and aliases,
151 scope/model keys and 245 effective-dated or qualified price periods
across 11 provider scopes, plus the existing client scopes.
The [2026-11-15 review](reviews/2026-11-15.md) and
[2026-11-12 review](reviews/2026-11-12.md) retain the preceding references.

## Files

- `api-price.toml` is the source catalog.
- `api-price.manifest.json` identifies the released catalog by version, byte
  size, and SHA-256.
- `scripts/check.py` validates both files with the Python standard library.

## Update

1. Verify changed prices against the linked provider references.
2. Add a new effective-dated row instead of rewriting historical periods.
3. Increment `catalog_version` and `updated_at`.
4. Run `python3 scripts/check.py --write-manifest api-price.manifest.json`,
   then `python3 scripts/check.py`.
5. Commit, tag the commit, and publish both catalog files as assets on a new
   GitHub Release.

Consumers may check the latest release without following mutable branch
content:

- `https://github.com/glenzli/api-price/releases/latest/download/api-price.manifest.json`
- `https://github.com/glenzli/api-price/releases/latest/download/api-price.toml`

For a reproducible build, replace `latest` with `download/<tag>`.

## Catalog contract

`scope` and `model` form an exact lookup key. Supported provider scopes are
`openai`, `google`, `anthropic`, `deepseek`, `qwen`, `zai`, `kimi`, `minimax`,
`xai`, `mistral`, and `cohere`; `codex`, `antigravity` and `claude-code` retain
explicit client references. A scope is not inferred from a neighboring model name.

Date and optional request-input ranges are inclusive. `rate_tier` selects a named
service/context or peak/off-peak band. Qualified ranges cannot overlap. A consumer
needs single-request input counts and the applicable tier; missing conditions
must not select a cheaper tariff from daily/session totals. MiniMax's ambiguous
512k unit stays in explicit named bands, rather than an invented numeric bound.

Rates are USD per million text tokens. `cached_input_per_million` and
`cache_write_per_million` are optional provider fields: absence means unknown,
not zero. Existing client scopes require the cache-read reference. Write fees
that vary by TTL are not collapsed into an unspecified single price.

Current source references include:

- [OpenAI model pricing](https://developers.openai.com/api/docs/models)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Cloud Gemini pricing](https://cloud.google.com/model-garden/pricing)
- [Google Cloud partner-model pricing](https://cloud.google.com/model-garden/partner-models/pricing)
