# api-price

A small, reviewable catalog of public text-token API prices used by local
tools such as Infra Sentinel. It maps exact consumer-visible model IDs to
documented rates; it does not infer prices from model-family names.

The catalog is a reference, not a provider invoice. Storage, tools, grounding,
multimodal input, regional processing, priority service, subscriptions, and
request-level context uplifts remain out of scope unless a catalog row says
otherwise.

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

`scope` and `model` form an exact lookup key. Date ranges are inclusive and
must not overlap for the same key. Rates are USD per one million text tokens.
`cache_write_per_million` is optional because not every provider publishes a
separate cache-write rate.

Current source references include:

- [OpenAI model pricing](https://developers.openai.com/api/docs/models)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Cloud partner-model pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
