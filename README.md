# Webshare-Account-Generator v2.2.0

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Engine](https://img.shields.io/badge/Engine-SeleniumBase%20UC%20Mode-orange?style=for-the-badge&logo=googlechrome&logoColor=white)](https://seleniumbase.io/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=for-the-badge)](https://github.com/LakoFusion/Webshare-Account-Generator)
[![Status](https://img.shields.io/badge/Status-Active%20%26%20Maintained-success?style=for-the-badge)](https://github.com/LakoFusion/Webshare-Account-Generator)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Discord](https://img.shields.io/badge/Community-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/rxw8Hwk3qA)

**Automated Webshare free-tier account provisioning: bulk-register accounts, scrape 10 free proxies per account, and mint 40-character API keys — resilient against Cloudflare bot checks.**

<div align="center"><img src="https://images.g2crowd.com/uploads/product/image/social_landscape/social_landscape_4fd0902ca921bdefa4512f0cf9915064/webshare-proxy-servers.png" alt="Webshare-Account-Generator Showcase" width="750"/></div>

</div>

---

> [!CAUTION]
> ## Security Warning — Read Before Running
> This tool writes **plaintext passwords and live API keys** to `output/accounts.txt` and proxy credentials to `output/proxies.txt`. Anyone with these files owns the accounts.
> - **Never** commit `output/` to a public repository — it is already covered by the bundled `.gitignore`.
> - **Never** share your `accounts.txt` / API keys in screenshots, issues, or chat.
> - Rotate or delete keys from the Webshare dashboard if a file was ever exposed.

---

## Supported Platforms & Requirements

| OS | Notes | Status |
| :--- | :--- | :--- |
| **Windows 10 / 11** | Run in PowerShell; headed Chrome required (manual captcha solving) | Fully supported |
| **Linux / VPS** | Needs a display (`Xvfb` or RDP/VNC) since the browser runs headed | Supported |
| **macOS 12+** | Intel & Apple Silicon via Rosetta/native Chrome | Supported |

| Requirement | Version |
| :--- | :--- |
| Python | 3.10 – 3.12+ |
| Google Chrome | Latest stable (SeleniumBase auto-manages the driver) |
| Python packages | See `requirements.txt` (`seleniumbase`, `selenium`, `colorama`, `numpy`) |

> SeleniumBase downloads and locks its driver under `downloaded_files/` automatically — no manual driver setup needed.

---

## Why Webshare-Account-Generator?

Manually creating Webshare accounts means fighting Cloudflare Turnstile on every signup, waiting out challenge pages, and copy-pasting proxies and API keys one by one. This tool turns that into a supervised loop:

* **Undetected browser core** — runs on SeleniumBase UC Mode with natural fingerprints and per-account session resets (cookies + localStorage), so Cloudflare challenges stay solvable instead of hard-blocking.
* **Real-time rejection detection** — the moment the red `This email cannot be used` error appears, the current email is swapped for a fresh one from a 4,352-name pool and signup is retried immediately. No more burning the full 5-minute wait on a dead email.
* **Two-layer creation gate** — the run only advances when hard proof exists (the `Go To Proxy List` button inside the success popup, or a real dashboard URL). A captcha still on screen can never be mistaken for a finished account.
* **Dashboard fallback scraper** — if the run lands on the Dashboard `Congratulations` banner, it clicks `View My Proxy List` itself before scraping, so proxies are never missed on layout variations.
* **Zero-flicker minimalist console** — a 4-block ANSI status screen (account / stage / queue / loop-network-fails) rendered atomically with pure spaces and fixed-width padding. No Unicode box characters, no broken columns on resize.

---

## Key Features

### Core Registration Pipeline
* End-to-end signup: fill email + generated password, tick Terms, click Sign Up.
* Email rotation across 4,352 unique alphanumeric base names (`names.txt`) with numeric suffixes and timestamp fallback against collisions.
* Up to 5 email attempts per account, each with its own full captcha time budget.

### Captcha & Anti-Ban Handling
* 5-minute supervised captcha window per email with live `MM:SS` countdown in the console.
* Challenge-redirect aware: Cloudflare interstitial URLs can never trigger a false success.
* Consecutive-failure guard (`FAIL 0/3`) — stops after 3 failed accounts so you can inspect the browser/network instead of burning the pool.

### Proxy Harvesting
* Scrapes all 10 free proxies per account from the MUI data grid.
* Auto-clicks `View My Proxy List` when the table is behind the Dashboard banner.
* Standard output format ready for other tools: `username:password@host:port`, one per line.

### API Key Minting
* 3-tier extraction: legacy CSS selectors, then copy-input values, then full-DOM regex for `[a-z0-9]{40}` — survives Webshare CSS-in-JS class renames.
* Auto-toggles masked-key visibility before scanning; appends `API Key` + `Label` to the account's block.

### Minimalist Console UI
* Four visual blocks: Header & Status / Account & Stage & Queue / Loop-Network-Fails / Recent Activity timeline.
* Pure-ANSI, space-padded, single-write anti-flicker rendering (`ESC [ H ESC [ J`); safe against missing fields (never crashes the main loop).

---

## Architecture Workflow

```text
[Name Pool 4.3k+] --> [Fill Form + Terms + Sign Up] --> [Cloudflare Check]
                                                            |
                        +-----------------------------------+------------------+
                        |                                                      |
                        v                                                      v
               [Captcha Shown]                                     [Rejected at Once]
                        |                                                      |
            [User Solves (300s budget)]                              [Swap Email + Retry]
                        |
                        v
        [Wait: Go To Proxy List button? / Email error? / Timeout?]
                        |
        +---------------+---------------+
        |                               |
        v                               v
 [SUCCESS + reason]              [EMAIL_REJECTED]
        |                               |
        v                               v
[Verify-Created Gate]            [New Email, Budget Reset]
        |
        v
[View My Proxy List (if needed)] --> [Scrape 10 Proxies] --> [Mint API Key] --> [Save to output/]
```

---

## Installation & Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/LakoFusion/Webshare-Account-Generator.git
cd Webshare-Account-Generator
```

### 2. Create and activate a virtual environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the generator
```bash
python main.py
```

* A headed Chrome window opens on the Webshare register page — **stay nearby**: when a captcha appears you have up to 5 minutes to solve it by hand in the browser.
* The console shows live status (`WAITING CAPTCHA` + countdown). Press `Ctrl+C` anytime to stop; the browser stays open for manual inspection.

---

## Output Specifications

### `output/accounts.txt`
One block per account (API Key lines are appended after minting):

```text
==================================================
Email: neonlight42@gmail.com
Password: X0z7akrz
Created: 2026-10-12 10:30:41
API Key: 0123456789abcdef0123456789abcdef01234567
Label: AutoKey_20261012_103041
```

### `output/proxies.txt`
One proxy per line, ready to import:

```text
username:password@31.59.20.176:6754
username:password@198.23.239.134:6540
```

---

## Project Structure

```text
Webshare-Account-Generator/
|-- main.py              # Entrypoint: registration loop, proxy/API stages, status console
|-- names.txt            # 4,352 unique alphanumeric base names for email rotation
|-- requirements.txt     # seleniumbase, selenium, colorama, numpy
|-- .gitignore           # Ignores output/, downloaded_files/, venv, caches
|-- LICENSE              # MIT
|-- README.md            # This file
|-- output/
|   |-- accounts.txt     # Generated accounts (plaintext credentials — keep private)
|   `-- proxies.txt      # Harvested proxies, one per line
`-- downloaded_files/    # SeleniumBase-managed driver files (auto-created, ignore it)
```

---

## Disclaimer, Community & License

### Disclaimer
> **For educational and testing purposes only.** Automating third-party signup flows may violate the provider's Terms of Service and can lead to account suspension or IP restrictions. The maintainers assume no liability for banned accounts, lost keys, or any misuse of this software. Use at your own risk.

### Community & Contact
* **Discord**: [Join the server](https://discord.gg/rxw8Hwk3qA)
* **TikTok:** [@noxofusion](https://www.tiktok.com/@noxofusion)
* **YouTube:** [@noxofusion2010](https://www.youtube.com/@noxofusion2010)

### License
Distributed under the **MIT License** — see [LICENSE](LICENSE) for full terms.
