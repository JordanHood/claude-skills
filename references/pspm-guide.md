# PSPM Guide

[PSPM](https://pspm.dev) (Package Manager for AI Agent Skills) is npm for agent skills. It handles installation, versioning, dependencies, and publishing across 30+ AI agents including Claude Code.

## Install PSPM

```bash
npm install -g @anytio/pspm
```

Or use without installing:
```bash
npx @anytio/pspm <command>
```

## Installing Skills

### From this repo

```bash
# Install individual skills
pspm add github:<user>/claude-skills/skills/pipeline
pspm add github:<user>/claude-skills/skills/notify
pspm add github:<user>/claude-skills/skills/guardrails

# Specify agents
pspm add github:<user>/claude-skills/skills/pipeline --agent claude-code
```

### From the PSPM registry

```bash
pspm add @user/<username>/pipeline
pspm add @user/<username>/notify@^0.1.0    # semver range
```

### From GitHub (general)

```bash
pspm add owner/repo                         # default branch
pspm add owner/repo/path/to/skill           # subdirectory
pspm add github:owner/repo@main             # specific branch
pspm add github:owner/repo/skills/my-skill@v1.0.0  # tag + path
```

### From local paths (development)

```bash
pspm add ./skills/pipeline                  # relative
pspm add file:../my-other-skills/cool-skill # explicit
```

### Installation scope

| Scope | Flag | Skills stored at | Symlinks at |
|-------|------|-----------------|-------------|
| Project | (default) | `.pspm/skills/` | `.claude/skills/` |
| Global | `-g` | `~/.pspm/skills/` | `~/.claude/skills/` |

## Managing Skills

```bash
pspm list                    # show installed skills
pspm outdated                # check for updates
pspm update                  # update to latest compatible
pspm remove <name>           # uninstall
pspm audit                   # verify integrity
```

## Publishing Skills

### 1. Create pspm.json

```bash
pspm init
```

Or write manually:

```json
{
  "name": "@user/<username>/<skill-name>",
  "version": "1.0.0",
  "description": "What this skill does",
  "files": ["pspm.json", "SKILL.md", "scripts/", "references/"]
}
```

### 2. Login

```bash
pspm login                   # browser auth
pspm login --api-key <key>   # API key
```

### 3. Publish

```bash
pspm publish --access public     # public (irreversible)
pspm publish --access private    # private (Pro tier)
```

### 4. Version management

```bash
pspm version patch    # 0.1.0 -> 0.1.1
pspm version minor    # 0.1.0 -> 0.2.0
pspm version major    # 0.1.0 -> 1.0.0
```

## Lockfile

PSPM creates `pspm-lock.json` for reproducible installs:

```bash
pspm install                     # restore from lockfile
pspm install --frozen-lockfile   # CI/CD (fails if lockfile outdated)
```

## File Exclusion

Create `.pspmignore` to exclude files from publishing:

```
*.test.ts
__tests__/
.env*
*.log
docs/superpowers/   # design docs, not part of the skill
```

Falls back to `.gitignore` if `.pspmignore` doesn't exist.

## Monorepo Pattern

This repo uses a monorepo pattern with multiple skills:

```
claude-skills/
  skills/
    pipeline/
      SKILL.md
      pspm.json
    notify/
      SKILL.md
      pspm.json
      scripts/
    guardrails/
      SKILL.md
      pspm.json
      examples/
  references/
    pspm-guide.md
  README.md
```

Each skill has its own `pspm.json` and can be installed independently using the path specifier:

```bash
pspm add github:user/claude-skills/skills/pipeline
```

## Supported Agents

PSPM installs symlinks for the target agent:

| Agent | Symlink directory |
|-------|------------------|
| Claude Code | `.claude/skills/` |
| Cursor | `.cursor/skills/` |
| Codex | `.agents/skills/` |
| Gemini CLI | `.agents/skills/` |
| Windsurf | `.windsurf/skills/` |
| Continue | `.continue/skills/` |
| + 24 more | Various |

## Search & Discovery

```bash
pspm search pipeline         # keyword search
pspm search typescript --json
pspm search --sort recent --limit 10
```
