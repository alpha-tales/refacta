---
description: Standards for installing dependencies in the Alpha Tales pnpm workspace. Apply when adding or updating packages to keep the monorepo clean and deterministic.
globs: 
alwaysApply: false
---
---
description: Standards for installing dependencies in the Alpha Tales pnpm workspace. Apply when adding or updating packages to keep the monorepo clean and deterministic.
globs:
alwaysApply: false
---

# Package-Installation Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Package installation rule applied"
- **Use pnpm only**; npm/yarn are not allowed. :contentReference[oaicite:0]{index=0}  
- **Never install at the repo root**. Always `cd` into the target workspace (e.g. `apps/web`). :contentReference[oaicite:1]{index=1}  
- Prefer `pnpm add --filter <workspace>` to install a dependency from the root if you can’t cd. :contentReference[oaicite:2]{index=2}  
- Use the `workspace:` protocol for internal packages so versions remain in sync. :contentReference[oaicite:3]{index=3}  
- Add dev-only tools (linters, test runners) to the root (`pnpm add -D <pkg>` in `/`) so every package shares them. :contentReference[oaicite:4]{index=4}  
- Never commit `node_modules` folders; rely on pnpm’s store.  
- Run `pnpm install --frozen-lockfile` in CI to guarantee reproducible builds. :contentReference[oaicite:5]{index=5}  

---

## Installation Workflows

### Installing a runtime dependency **from inside** the workspace
```sh
cd apps/web
pnpm add react-query

Installing from the repo root with filtering
sh
Copy
Edit
pnpm add react-query --filter apps/web     # same effect as above
Both commands write the entry to apps/web/package.json only. 
dev.to

Adding an internal workspace package
sh
Copy
Edit
pnpm add common-ui --filter apps/web --workspace  # writes "workspace:*"
This enforces local linking and prevents registry resolution. 
github.com

Dev / CI Guidelines
CI: pnpm install --frozen-lockfile then pnpm --filter ... run build to build just the affected packages. 
dev.to

Caching: Enable pnpm store cache on your CI runner to speed up subsequent jobs.

Scripts: When writing root scripts, scope them:

jsonc
Copy
Edit
"scripts": {
  "build:web": "pnpm --filter apps/web run build"
}
Examples
<example> ✅ **Correct** - Uses `pnpm add lodash --filter apps/web` - Lockfile updated once; only `apps/web/package.json` changes. 
</example> 

<example type="invalid"> ❌ **Incorrect** - Runs `npm install lodash` in root — introduces duplicate lockfile and pollutes root `package.json`. 
</example>
