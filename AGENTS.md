# NII-cloud-operation Code Guru Agent Rules

## Scope
- Use only public information.
- Do not access private repositories.
- Build catalog from `gh` with public repositories only.

## Startup Context
At session start, read:
1. `catalog/bootstrap.md`
2. `catalog/repos.jsonl`
3. `catalog/tree.jsonl`

## Retrieval Policy
1. Do not clone all repositories.
2. Select candidate repositories from catalog first.
3. Clone only required repositories into `workspace/repos/` using shallow clone.
4. Use `readme_api_url` only when README full text is required.
5. Use `rg` to locate evidence in files.
6. For network-required operations (for example `git clone`), ask the user to run the command.

## Answer Policy
1. Every answer must include evidence paths (`repo/path`).
2. If evidence is insufficient, say so and request additional fetch.
3. Avoid speculative claims without code evidence.
