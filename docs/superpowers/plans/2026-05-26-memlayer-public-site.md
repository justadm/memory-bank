# MemLayer Public Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public static site for `memlayer.ru` and `memlayer.ru/api` with curated docs content, copyable command blocks, and an optional lightweight theme switcher.

**Architecture:** Keep the public site fully static under `deploy/msk/site`, wire copy/theme behavior through one small shared JS file, and add a dedicated nginx sample for `memlayer.ru` separate from the `adm.memlayer.ru` runtime.

**Tech Stack:** static HTML, CSS, small vanilla JS, nginx, pytest file-content checks.

---

### Task 1: Add failing tests for public site assets

**Files:**
- Create: `tests/test_public_site_assets.py`

- [ ] **Step 1: Write failing tests for required files**
- [ ] **Step 2: Verify tests fail before implementation**

### Task 2: Implement static public site assets

**Files:**
- Create: `deploy/msk/site/index.html`
- Create: `deploy/msk/site/api/index.html`
- Create: `deploy/msk/site/styles.css`
- Create: `deploy/msk/site/site.js`

- [ ] **Step 1: Add homepage content**
- [ ] **Step 2: Add `/api` content**
- [ ] **Step 3: Add copy-button behavior**
- [ ] **Step 4: Add lightweight theme switcher**
- [ ] **Step 5: Verify tests pass**

### Task 3: Add nginx sample and docs

**Files:**
- Create: `deploy/msk/nginx/memlayer.ru.conf`
- Modify: `README_DEPLOY.md`
- Modify: `WORKLOG.md`

- [ ] **Step 1: Add nginx static-site sample**
- [ ] **Step 2: Document memlayer.ru static root deployment**
- [ ] **Step 3: Run full pytest suite**
- [ ] **Step 4: Commit**
