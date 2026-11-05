# `/triage` team profiles vs. the gecko-triage Hackbot agent

Compares this repo's `/triage` with `TRIAGE_TEAM=dom-core` and `run_locked.py`
(branch `triage-team-profiles`) to the `gecko-triage` agent in
[mozilla/bugbug#7239](https://github.com/mozilla/bugbug/pull/7239), read at
[`4310a0f`](https://github.com/mozilla/bugbug/tree/4310a0f96b4a4ee38aa1094ebe8beddc0469eadc/agents/gecko-triage).
Both aim at the same thing: per-team Gecko bug triage that drafts a comment and
field changes for a person to approve. gecko-triage grew out of this repo's A/V
`/triage` and still runs four of its skills (`analyze-profile`, `check-log`,
`spec-check`, `bug-start`).

## Where they differ

| | `/triage` (this branch) | gecko-triage (bugbug#7239) |
|---|---|---|
| Runs | Locally, in Claude Code, on the triager's machine | Hackbot Cloud Run job, one bug per run (BugBot cron or the Hackbot UI) |
| Queue | BugBot's "no severity, no pending needinfo" list, once a day | Each changed bug in the team's components, again on every change |
| Output | Local draft JSON, reviewed in the triage dashboard, posted from the triager's account with an "(AI-assisted triage, with review.)" line | Recorded actions, applied by hackbot-api as `hackbot@mozilla.tld` after a person approves (auto-apply possible later) |
| Team config | One `teams/<team>.md` per team; it replaces the whole per-bug workflow | `teams/<team>/team.toml` plus five rule files layered on shared `rules/`; a team rule wins where it is more specific |
| Teams so far | `av` (the old `/triage`, moved word for word), `dom-core` | `media` |
| Scope for DOM Core | Severity and at most one comment, plus component move, duplicate, see-also, `spec-needed`, needinfo; no investigation | Full triage: investigation (`bug_investigator` runs `bug-start`) before "Analyzed" and before most asks, meta bugs, fix tags, closes, security group |
| Priority | Never set (DOM Core) | Always set P1–P3 with severity; the shared rules say a triaged bug has both |
| Rule enforcement | Prompt rules; `validate_draft.py` checks each draft; in locked runs a PreToolUse hook enforces them; `close-verifier` | Code: preflight skips, record-time hooks on every action, post-run checks on other bugs, `close_verifier` |

## Things gecko-triage does that this branch doesn't

- **Stricter close verification.** Both require a confirm from a fresh-context
  verifier that tries to prove a close wrong (here the `close-verifier` subagent,
  enforced by the locked hook and `validate_draft.py`). gecko-triage also makes
  the verifier read any tool result that was saved to a file to its end before
  it can confirm, and allows one verifier per run; here it's one per bug.
- **Code-driven duplicate search.** It searches by crash signature and the rarest
  summary words before the model starts, then runs a concept search over summaries
  and comments. Here the profile tells the model to search summaries by function,
  IPC message or API name. That search found more duplicates than free-text
  search in the DOM Core sample (`tmp-dom-core/research/findings.md`, not checked in).
- **Needinfo bounds in code.** It allows only people on the bug, the team's listed
  experts, a commit author from the VCS history, or the target team on a move.
  Here the locked runner's hook reads the bug and checks needinfo and CC
  targets against its participants, but also accepts any
  `@mozilla.com`/`@mozilla.org` account, with no expert list.
- **Post-run checks** on the bugs a draft names (`dupe_of` closed or a meta bug,
  restricted bugs named in the comment).
- **Re-triage on every change**, with "watching" when nothing substantive changed.
- **Security group.** It adds a public bug to the product's security group when
  its analysis finds a vulnerability. Here the DOM profile drafts nothing for
  such a bug and only flags it for the triager.

## Things this branch does that gecko-triage doesn't

- **DOM Core rules from triage history.** `teams/dom-core.md` is based on 1451
  triage events and 87 bugs read closely:
  - check reporter and AI-report claims instead of repeating them;
  - match duplicates by cause, and check a FIXED candidate's fix date;
  - route by the moz.build `BUG_COMPONENT` of the code that would change, not
    the crash frame or bugbug's guess;
  - test interop claims in Chrome *and* Safari, or read wpt.fyi;
  - when the spec is silent, point to a spec issue and add `spec-needed`;
  - crashes: one line with the socorro numbers;
  - perf: compare Release with Nightly first;
  - severity follows the security rating, and S3 is the default.

  gecko-triage's shared rules are media-shaped: about:support is asked for by
  default, and the severity matrix is about crashes.
- **No priority, and severity only on defects.** This matches
  [Triage for Bugzilla](https://firefox-source-docs.mozilla.org/bug-mgmt/policies/triage-bugzilla.html#what-is-a-triaged-bug):
  a triaged defect has a severity, and priority is required only for
  enhancements. gecko-triage's `rules/workflow.md` says "a triaged bug is a bug
  with severity and priority set".
- **A comment only when it adds something.** Developer-filed bugs with a root
  cause and an owner get severity only, matching how DOM Core triagers worked.
- **Hardening for a machine that isn't disposable** (below).

## Security model

gecko-triage runs in a disposable container and leans on that:

- The agent holds no Bugzilla key. A broker sidecar holds a read key and serves
  only public data.
- Writes are recorded actions, bounded by hooks and applied by hackbot-api.
- Comments are passed to the model as escaped JSON, so comment text can't pose
  as another author. Secrets are blanked from the CLI's environment, and on Linux
  the process is made undumpable. Comment links are limited to allowlisted hosts.
- Inside the container the session runs with `bypassPermissions`, and the base
  tools include Bash, WebFetch and WebSearch. Bash can reach the network and write
  anywhere the process can. `log_analyst` is told not to fetch logs with curl, but
  "that part is a rule, not a guard" (its README).
- `fetch_attachment` unpacks zip, gzip and tar (with caps) and runs
  `ffprobe`/`ffmpeg` on videos (with CPU, memory and time limits).

`run_locked.py` runs on the triager's own machine, so it restricts more:

- Claude Code's `--restricted` mode (the user's settings and permission allowlists
  don't apply), no MCP servers, and a fixed tool list.
- A PreToolUse hook:
  - Bash may run only the read-only CLIs and the plugin's scripts, with no shell
    operators;
  - writes are allowed only inside the triage directory, and drafts must pass
    `validate_draft.py`;
  - WebFetch may reach public sites only: no loopback, private or link-local
    addresses (the hook resolves the hostname to check), no credentials in URLs,
    no non-default ports, no long query strings.
- The Bash sandbox: network only to Mozilla and spec hosts, no reads of
  `~/.config`, `~/.ssh` and similar.
- API keys are stripped from the environment, so runs are read-only and anonymous.
- `read_attachment.py` reads text attachments as escaped text between
  tags with a random id, and images only after checking their magic
  bytes. It refuses archives, executables, PDFs, office files, media and unknown
  binaries.
- The model drives no browser. With `--browsers`, `run_testcases.py`, which runs
  no model, loads the testcases the run saved (served under a CSP, a dead proxy
  for Firefox and Chrome, a fresh profile per page, crash and security bugs
  skipped), and a second locked pass adds the results.

## Questions for bugbug#7239

- Can a team turn off setting priority, and the default about:support ask? DOM
  Core sets severity only. The policy above doesn't require priority on defects.
- Does the Cloud Run job block the metadata server and other internal addresses?
  Bash and WebFetch are unrestricted in the container, and bug text is untrusted. I
  couldn't tell from the PR whether egress or the service account limits this.
- Could DOM Core become a gecko-triage team? Its `team.toml` and five rule files
  could start from `teams/dom-core.md`. Two things stand in the way: the shared
  rules assume investigation and priority, and the bot posts from
  `hackbot@mozilla.tld` rather than the triager's account.
- Is there interest in the duplicate search by function or IPC name, and in the
  wpt.fyi and cross-browser checks for interop claims?
