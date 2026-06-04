---
bug_id: 2044320
investigated_at: 2026-06-02T00:00:00Z
status: investigated
summary: MP4 with two adjacent colr boxes fails to parse — an mp4parse strictness regression that also breaks animated AVIF
root_cause: When a video sample entry contains a second `colr` box, mp4parse's read_video_sample_entry calls fail_with_status_if(strictness != Permissive, Status::ColrBadQuantityBMFF), which returns Err under ParseStrictness::Normal (the only strictness Firefox uses for video via mp4parse_new), aborting the whole context parse; that becomes Mp4parseStatus::Invalid and MP4Metadata.cpp turns it into NS_ERROR_DOM_MEDIA_METADATA_ERR.
affected_files:
  - third_party/rust/mp4parse/src/lib.rs#L5773-L5787
  - third_party/rust/mp4parse/src/lib.rs#L2074-L2082
  - third_party/rust/mp4parse/src/lib.rs#L404-L418
  - third_party/rust/mp4parse_capi/src/lib.rs#L577
  - dom/media/mp4/MP4Metadata.cpp#L98-L107
  - image/decoders/nsAVIFDecoder.cpp#L339
  - modules/libpref/init/StaticPrefList.yaml#L8884
regression_range: 92f89567f9fd-abdde6f33992
related_bugs: [2044532, 2030296, 1729071, 2033628]
complexity: low
notes: >-
  Regressor is gecko commit c1c75b1a145a (bug 2030296 Part 1) updating vendored mp4parse to 952f5173,
  which introduced ColrBadQuantityBMFF and the read_video_sample_entry colr-fail (verified via
  `git log -S ColrBadQuantityBMFF`; corroborated by the bug 2044532 mozregression window). The earlier
  draft mis-attributed it to bug 2033628 / fb7ed9ef. This bug ALSO covers bug 2044532 (animated AVIF
  "contains errors") -- same read_video_sample_entry check, reached via nsAVIFDecoder at the
  image.avif.compliance_strictness=Normal default. One upstream mp4parse fix resolves both. ISO 14496-12:2015
  §12.1.5.1 permits "one or more" colr boxes (advisory, no normative behaviour). Minimal fix: demote the duplicate-colr BMFF case from hard-fail
  to warn-and-skip even under Normal strictness, upstream then re-vendor.
---

# Bug 2044320 Investigation

## Summary

- **Bug**: [Bug 2044320](https://bugzilla.mozilla.org/show_bug.cgi?id=2044320)
- **Title**: Parse MP4 metadata failed with mp4 containing two adjacent colr boxes
- **Component**: Core :: Audio/Video: Playback
- **Severity/Priority**: -- / -- (unset)
- **Status**: UNCONFIRMED
- **Public**: Yes

> **This bug is the consolidation point for [bug 2044532](https://bugzilla.mozilla.org/show_bug.cgi?id=2044532)** (animated AVIF "contains errors"). Both are the *same defect* in `read_video_sample_entry`, reached via two surfaces. The single upstream mp4parse fix below resolves both. See **Two surfaces** under Root Cause.

An MP4 whose video sample entry carries two adjacent `colr` boxes — the recognized backward-compatible HLG signaling convention — fails to load in Firefox 151 with `NS_ERROR_DOM_MEDIA_METADATA_ERR` ("Parse MP4 metadata failed"); it played fine in 149. The regressor is **gecko commit [`c1c75b1a145a`](https://github.com/mozilla-firefox/firefox/commit/c1c75b1a145a) (bug 2030296 Part 1)**, which updated vendored mp4parse to `952f5173` and introduced `ColrBadQuantityBMFF` — making a second `colr` box in a video sample entry a hard parse error whenever strictness is not `Permissive`. (Verified by `git log -S ColrBadQuantityBMFF`; the reporter's pointer to upstream `1fea957f` is the upstream change that `952f5173` already contained.) Firefox always parses video MP4 with `ParseStrictness::Normal`, so the new check fires and aborts the entire metadata parse. The fix is to demote that single check from a fatal error to the warn-and-skip behavior the surrounding code already implements (keep the first `colr`, skip the rest), then re-vendor.

---

## Implementation Plan

> This section drives `/firefox-implementation`. Keep it current as the approach evolves.

### Patch Arrangement

The change lives in vendored third-party Rust (`third_party/rust/mp4parse*`). The clean path is to fix it upstream in mozilla/mp4parse-rust, then re-vendor into mozilla-central. A local-only vendor patch is possible but discouraged because `./mach vendor rust` would clobber it on the next bump.

| Patch | Description | Key changes | Depends on |
|---|---|---|---|
| P1 (upstream) | In mp4parse-rust, stop failing the BMFF video path on a duplicate `colr` box | `mp4parse/src/lib.rs` `read_video_sample_entry`: remove the `fail_with_status_if(strictness != Permissive, ColrBadQuantityBMFF)` call (or gate it on `Strict` only), keep the existing `warn!` + `skip_box_content`; add a regression test in `mp4parse_capi/tests/test_colour_info.rs` plus a `two-colr` fixture | — |
| P2 (gecko) | Re-vendor mp4parse to the rev containing P1 | Bump `rev` in `toolkit/library/rust/shared/Cargo.toml`, `./mach vendor rust`, regenerate `Cargo.lock` and `third_party/rust/mp4parse*`; optionally add a gecko-level mochitest fixture | P1 landed/tagged upstream |

If landing upstream is not feasible on the needed timeline, an interim option is a local vendor patch (edit `third_party/rust/mp4parse/src/lib.rs` directly + record it under `third_party/rust/mp4parse/.cargo-checksum.json` regeneration). Document it so it is re-applied on the next bump. Preferred order is still upstream-first.

### Mechanism Replacement (if applicable)

Not applicable — this is a one-line behavioral relaxation, not a mechanism swap.

### Test Strategy

- **Type**: Rust integration test (in `mp4parse_capi`), optionally a gecko mochitest with a real `two-colr.mp4`.
- **Location**: [`third_party/rust/mp4parse_capi/tests/test_colour_info.rs`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/tests/test_colour_info.rs) (worktree: `~/firefox-2044320/third_party/rust/mp4parse_capi/tests/`) plus a new `tests/video_colr_two_colr.mp4` fixture. A gecko mochitest fixture would go under `dom/media/test/`.
- **What it covers**: A video sample entry containing two adjacent `colr` boxes must parse to `Mp4parseStatus::Ok` and surface the *first* box's color info (HLG: transfer=18 for the HLG-signaling box, or whatever the fixture's first box carries).
- **Covers both surfaces**: because both bug 2044320 (MP4 playback) and bug 2044532 (animated AVIF) fail at the same Rust check, the parser-level test guards both. An optional animated-AVIF reftest under `image/test/reftest/avif/` (a sequence with two `colr` boxes) gives end-to-end coverage of the 2044532 surface specifically.
- **Rationale**: The bug is entirely inside the Rust parser; the cheapest, most direct regression guard is a parser-level test that asserts the previously-failing input now parses. The existing `test_colour_info.rs` already opens fixtures via `open_parser` (which asserts `Mp4parseStatus::Ok`), so a `two-colr` fixture reusing that helper is the natural shape. A gecko mochitest is a nice end-to-end belt-and-suspenders but is redundant for catching this specific regression and requires shipping a binary fixture into `dom/media/test`.

**Fixture provenance + verified structure**: the reporter's public `two-colr.mp4` (`http://smp-scratch.tools.bbc.co.uk/bob/firefox-colr/two-colr.mp4`) was downloaded with user approval (via the `/download-guard` rule) and its box tree walked. Confirmed: the `hev1` video sample entry carries **two adjacent `nclx colr` boxes**, in this order:

1. primaries=9 (BT.2020), **transfer=18 (HLG / ARIB STD-B67)**, matrix=9 — the HLG-signaling box
2. primaries=9 (BT.2020), **transfer=14 (BT.2020 10-bit)**, matrix=9 — the HLG-unaware fallback

This is exactly the backward-compatible HLG dual-`colr` convention, ordered most-accurate-first, and is spec-valid per ISO/IEC 14496-12 §12.1.5 (zero-or-more `colr`). It confirms the root cause and pins the test expectation: the fixed parser must keep the **first** box (transfer=18, HLG). The in-tree regression test can reuse this file or a hand-built minimal equivalent (a 78-byte visual sample-entry header + `hvcC` + two `nclx colr` boxes). Do NOT auto-download in future runs — the `/download-guard` gate applies.

---

## Problem Analysis

### Problem Description

Users experience: playing certain HLG MP4s (those using the two-`colr` backward-compatible signaling) fails outright in Firefox 151 with a console error:

> Media resource ...two-colr.mp4 could not be decoded, error: Error Code: NS_ERROR_DOM_MEDIA_METADATA_ERR (0x806e0006). Details: virtual RefPtr<MP4Demuxer::InitPromise> mozilla::MP4Demuxer::Init(): Parse MP4 metadata failed

Expected: the file plays (as it did in Firefox 149), keeping the first `colr` box's color information and ignoring the second.

**Failure pattern**: Consistent (not intermittent). The failure is deterministic for any MP4 whose video sample entry has more than one `colr` box. No Treeherder/CI dimension — this is a real-content regression reported by an external user, not a test orange.

The reporter correctly identified the regressor as upstream mp4parse-rust commit `1fea957f`. UA: Firefox/151.0 on macOS.

### Root Cause

When parsing a video sample entry's child boxes, mp4parse hits the `ColourInformationBox` arm. On the *second* `colr` box (`colour_info.is_some()`), it logs "keeping first" and then calls `fail_with_status_if`:

[`third_party/rust/mp4parse/src/lib.rs:5773-5787`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#5773-L5787):
```rust
BoxType::ColourInformationBox => {
    if colour_info.is_some() {
        warn!("Multiple colr boxes in video sample entry, keeping first");
        fail_with_status_if(
            strictness != ParseStrictness::Permissive,
            Status::ColrBadQuantityBMFF,
        )?;                       // <-- returns Err under Normal, aborts parse
        skip_box_content(&mut b)?;   // <-- never reached under Normal
    } else if let ParsedColourInformation::Supported(colr) =
        read_colr(&mut b, strictness)?
    { ... }
}
```

[`fail_with_status_if`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#2074) (lib.rs:2074-2082) returns `Err(Error::from(status))` when `violation == true`, else logs a warning and returns `Ok`:
```rust
fn fail_with_status_if(violation: bool, status: Status) -> Result<()> {
    let error = Error::from(status);
    if violation { Err(error) } else { warn!("{error:?}"); Ok(()) }
}
```

Firefox's C API entry point [`mp4parse_new`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/src/lib.rs#577) hardcodes `ParseStrictness::Normal` (capi lib.rs:577 — `mp4parse_new_common(io, ParseStrictness::Normal, parser_out)`). Since `Normal != Permissive`, `violation` is `true`, so `fail_with_status_if` returns `Err`. The `?` operator propagates the `Err` out of `read_video_sample_entry`, aborting the whole context parse.

The status maps to an nsresult as follows:
- `ColrBadQuantityBMFF` is not in the panic-list of [`From<Status> for Error`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#404) (lib.rs:404-418), so it falls into the `_ => Self::InvalidData(parse_status)` arm.
- The capi maps `Error::InvalidData(_)` to `Mp4parseStatus::Invalid` (→ `MP4PARSE_STATUS_INVALID`).
- [`MP4Metadata.cpp:98-107`](https://searchfox.org/mozilla-central/source/dom/media/mp4/MP4Metadata.cpp#98) calls `mp4parse_new`; on a non-`OK` status it returns `NS_ERROR_DOM_MEDIA_METADATA_ERR` (line 107, since the status is not `OOM`) — exactly the console error the reporter sees.

#### Two surfaces (this bug + bug 2044532)

The same `read_video_sample_entry` check is reached through two independent decoder entry points, producing two separately-reported bugs with one root cause:

| | Bug 2044320 (this bug) | Bug 2044532 |
|---|---|---|
| Content | **MP4 video** playback, two adjacent `colr` boxes (backward-compatible HLG) | animated **AVIF image**, two `colr` boxes (libavif output) |
| Entry point | [`MP4Demuxer::Init`](https://searchfox.org/mozilla-central/source/dom/media/mp4/MP4Demuxer.cpp#86) → `MP4Metadata` → [`mp4parse_new`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/src/lib.rs#577) | [`AVIFParser::Init`](https://searchfox.org/mozilla-central/source/image/decoders/nsAVIFDecoder.cpp#339) → `mp4parse_avif_new` |
| Strictness | `mp4parse_new` hardcodes `Normal` | [`image.avif.compliance_strictness`](https://searchfox.org/mozilla-central/source/modules/libpref/init/StaticPrefList.yaml#8884) = `Normal` (default 1) |
| Symptom | `NS_ERROR_DOM_MEDIA_METADATA_ERR`, "Parse MP4 metadata failed" | image error page, "...contains errors" |
| Shared cause | `read_video_sample_entry` rejects the 2nd `colr` at Normal strictness | same |

Both run at `ParseStrictness::Normal`, so both hit `fail_with_status_if(Normal != Permissive, ColrBadQuantityBMFF)`. **The P1 upstream mp4parse fix resolves both bugs.** Both are assigned to alwu; bug 2044532 is treated as a duplicate root cause and the work happens here.

**Spec basis (verbatim spec text, verified per CLAUDE.md).** The governing clause is **ISO/IEC 14496-12:2015(E), § 12.1.5 "Colour information", subclause 12.1.5.1 "Definition"** (p. 158), which defines the `ColourInformationBox` (`colr`) inside a `VisualSampleEntry`. It reads, verbatim:

> "Colour information may be supplied in **one or more ColourInformationBoxes** placed in a VisualSampleEntry. These should be placed in order in the sample entry starting with the most accurate (and potentially the most difficult to process), in progression to the least. These are **advisory** and concern rendering and colour conversion, and there is **no normative behaviour** associated with them; a reader may choose to use the most suitable. A ColourInformationBox with an unknown colour type may be ignored."

So the spec **explicitly permits more than one** `colr` box in a single visual sample entry ("one or more"), defines their handling as advisory with "no normative behaviour", and tells the reader it "may choose to use the most suitable" (i.e. keep the first/most-accurate). A video sample entry with two `colr` boxes is therefore *spec-valid*, and the two-`colr` form is the established backward-compatible HLG signaling convention. The upstream commit's justification cites the 2020 edition as "at most one"; even if 2020 tightened the wording, the 2015 edition Firefox honored through v149 explicitly permits it and real content depends on it — so rejecting it under `Normal` strictness is a behavior regression.

**Citation for the commit message** — ISO/IEC 14496-12:2015(E) § 12.1.5.1: *"Colour information may be supplied in one or more ColourInformationBoxes placed in a VisualSampleEntry ... These are advisory ... there is no normative behaviour associated with them; a reader may choose to use the most suitable."*

[Assumption: the exact 2020 §12.1.5 wording is not directly quoted here — the 2020 ISO PDF was access-restricted during this investigation. The 2015 text was read verbatim from the publicly available ISO/IEC 14496-12:2015(E) PDF; the 2020 edition retains the same §12.1.5 structure including the "this box takes precedence ... over-rides the information in the bitstream" sentence.]

### Code Analysis

#### Key Files

1. **[`third_party/rust/mp4parse/src/lib.rs:5773-5787`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#5773-L5787)** — the `ColourInformationBox` arm of `read_video_sample_entry`. This is where the fatal `fail_with_status_if` call lives and where the fix goes. Note the surrounding code already implements the lenient behavior (`warn!` + `skip_box_content`); only the `fail_with_status_if` in between turns tolerance into a hard error.
2. **[`third_party/rust/mp4parse/src/lib.rs:2074-2082`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#2074)** — `fail_with_status_if`: the gate that converts the strictness check into an `Err`.
3. **[`third_party/rust/mp4parse/src/lib.rs:404-418`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#404)** — `From<Status> for Error`: confirms `ColrBadQuantityBMFF` becomes `Error::InvalidData`, not a panic.
4. **[`third_party/rust/mp4parse_capi/src/lib.rs:577`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/src/lib.rs#577)** — `mp4parse_new` hardcodes `ParseStrictness::Normal`; `mp4parse_new_strict` (the only `Strict`/configurable entry point) is not used by Firefox for video.
5. **[`dom/media/mp4/MP4Metadata.cpp:98-107`](https://searchfox.org/mozilla-central/source/dom/media/mp4/MP4Metadata.cpp#98)** — the Firefox caller that turns a non-OK `Mp4parseStatus` into `NS_ERROR_DOM_MEDIA_METADATA_ERR`.
6. **[`third_party/rust/mp4parse/src/lib.rs:469-475`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#469)** — the human-readable string for `ColrBadQuantityBMFF` ("Each sample entry shall have at most one ColourInformationBox (colr)...").

#### Current Behavior

`MP4Demuxer::Init` → `MP4Metadata` ctor → [`mp4parse_new`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/src/lib.rs#577) (Normal strictness) → `mp4parse_new_common_safe` → `P::read` → ... → [`read_video_sample_entry`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#5617). On the second `colr` box, `fail_with_status_if` returns `Err(InvalidData(ColrBadQuantityBMFF))`, which propagates back up through `mp4parse_new_common_safe` ([capi lib.rs:622-631](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/src/lib.rs#622), `.map_err(Mp4parseStatus::from)`) as `Mp4parseStatus::Invalid`. `MP4Metadata.cpp` then returns `NS_ERROR_DOM_MEDIA_METADATA_ERR`, failing `MP4Demuxer::Init`.

### Specification Compliance

- **Spec**: ISO/IEC 14496-12:2015(E) **§ 12.1.5.1** — Colour information, Definition (Colour Information Box `colr` in `VisualSampleEntry`), p. 158.
- **Required (verbatim)**: *"Colour information may be supplied in **one or more** ColourInformationBoxes placed in a VisualSampleEntry. ... These are advisory ... and there is **no normative behaviour** associated with them; a reader may choose to use the most suitable. A ColourInformationBox with an unknown colour type may be ignored."*
- **Firefox (current)**: Rejects any sample entry with > 1 `colr` box under `Normal` strictness, failing the whole parse.
- **Verdict**: ❌ Non-compliant with §12.1.5.1 (which Firefox honored through v149). The clause explicitly allows "one or more" `colr` boxes and assigns them no normative behaviour, so a hard parse failure on the second box contradicts the spec. The two-`colr` HLG convention is real-world content; tolerate-and-keep-first ("a reader may choose to use the most suitable") is the spec-aligned, backward-compatible behavior.

### Related Context

- **Regressor (gecko, CORRECTED)**: [`c1c75b1a145a`](https://github.com/mozilla-firefox/firefox/commit/c1c75b1a145a) — "Bug 2030296 - Part 1: Update mp4parse to 952f5173" (autoland `abdde6f33992`/`29c78c2f832b`). `git log -S "ColrBadQuantityBMFF" -- third_party/rust/mp4parse/src/lib.rs` returns this commit as the sole introducer of both the status and the `read_video_sample_entry` colr-fail. This matches the bug 2044532 mozregression window [`92f89567f9fd`…`abdde6f33992`](https://hg-edge.mozilla.org/integration/autoland/pushloghtml?fromchange=92f89567f9fde03d1bcd8d2821b312f62fd9d7bc&tochange=abdde6f33992058321d54cdac634de1ae1578803). Uplifted to beta 151, consistent with the reporter's "works in 149, broken in 151". *(An earlier draft of this doc mis-attributed the regressor to bug 2033628 / `70a6a5ceb778` / `fb7ed9ef`; that bump left the already-present check unchanged.)*
- **Regressor (upstream)**: mozilla/mp4parse-rust commit [`1fea957ff92037f05d47230bbec6801e0ace7cd7`](https://github.com/mozilla/mp4parse-rust/commit/1fea957ff92037f05d47230bbec6801e0ace7cd7) — introduced `ColrBadQuantityBMFF` and the "fail unless Permissive" check for duplicate `colr` in BMFF video, plus the `ParsedColourInformation::{Supported,Unsupported}` enum. This commit was already contained in rev `952f5173`, which bug 2030296 Part 1 vendored.
- **Related bugs**: [Bug 2044532](https://bugzilla.mozilla.org/show_bug.cgi?id=2044532) (same root cause, animated-AVIF surface — consolidated here), [Bug 2030296](https://bugzilla.mozilla.org/show_bug.cgi?id=2030296) (the vendor update that introduced the check, while adding video-track `colr` parsing), [Bug 1729071](https://bugzilla.mozilla.org/show_bug.cgi?id=1729071) (historical AVIF multiple-`colr` handling — the AVIF/HEIF item path uses the separate `ColrBadQuantity` status, which should stay strict), [Bug 2033628](https://bugzilla.mozilla.org/show_bug.cgi?id=2033628) (a later mp4parse bump, NOT the regressor).
- **Existing tests**: [`third_party/rust/mp4parse_capi/tests/test_colour_info.rs`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/tests/test_colour_info.rs) — already has `video_colr_nclx_hdr10` etc. using `open_parser` (which asserts `Mp4parseStatus::Ok`); the regression test belongs here.
- **Reporter repro (do not auto-download)**: `http://smp-scratch.tools.bbc.co.uk/bob/firefox-colr/plain.html` loading `two-colr.mp4`.

---

## Patch Details

### P1: Tolerate duplicate `colr` box in BMFF video sample entries (upstream mp4parse-rust)

**Scope**: Stop the duplicate-`colr` case in `read_video_sample_entry` from being a fatal parse error under `Normal` strictness; keep the first box and skip the rest, matching pre-`1fea957f` behavior and the surrounding lenient code.

| File | Change |
|---|---|
| [`mp4parse/src/lib.rs` `read_video_sample_entry`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#5773) | Remove the `fail_with_status_if(strictness != Permissive, ColrBadQuantityBMFF)?;` call (lines 5776-5779), or change its condition to `strictness == Strict` so only true Strict mode rejects. Keep the existing `warn!` and `skip_box_content(&mut b)?`. The AVIF/HEIF path (which uses `ColrBadQuantity`, a different status, at [lib.rs:3153](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#3153)) is untouched. |
| [`mp4parse_capi/tests/test_colour_info.rs`](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse_capi/tests/test_colour_info.rs) | Add `video_colr_two_colr` test: open a fixture with two adjacent `colr` boxes, assert `Mp4parseStatus::Ok` and that the *first* box's color info is surfaced. |
| `mp4parse_capi/tests/video_colr_two_colr.mp4` (new) | Minimal fixture with two `colr` boxes in one video sample entry. |

**Test command**: `cargo test -p mp4parse_capi video_colr_two_colr` (run inside the mp4parse-rust checkout). In-tree after re-vendor, `mp4parse_capi` tests run via the gtest harness / `./mach rusttests` as applicable.
**Gotchas**:
- Do NOT relax the AVIF/HEIF `ColrBadQuantity` check ([lib.rs:3153](https://searchfox.org/mozilla-central/source/third_party/rust/mp4parse/src/lib.rs#3153)) — that is a separate status for image items and has its own (stricter) spec basis (bug 1729071). Only the BMFF-video `ColrBadQuantityBMFF` path changes.
- The `invariant being preserved`: a malformed/over-specified `colr` cardinality must not break playback of otherwise-valid video; mp4parse already chose "keep first" for the *data*, so the error return is the only inconsistency.
- Whether to keep `ColrBadQuantityBMFF` reachable at all under `Strict`: gating on `strictness == Strict` (vs. deleting the call) preserves the status for any future strict consumer and is the smaller semantic change. Confirm with upstream maintainers (kinetik / media-playback-reviewers) which they prefer.

### P2: Re-vendor mp4parse into mozilla-central

**Scope**: Pull the P1 fix into the tree by bumping the vendored rev.

| File | Change |
|---|---|
| [`toolkit/library/rust/shared/Cargo.toml`](https://searchfox.org/mozilla-central/source/toolkit/library/rust/shared/Cargo.toml#15) | Update `mp4parse_capi` `rev` from `fb7ed9ef...` to the upstream commit containing P1. |
| `Cargo.lock` | Regenerated by `./mach vendor rust`. |
| `third_party/rust/mp4parse/`, `third_party/rust/mp4parse_capi/` | Re-vendored sources + `.cargo-checksum.json` regenerated. |

**Test command**: `./mach build binaries` then `./mach rusttests` (or the mp4parse gtest). A gecko mochitest with a real `two-colr.mp4` under `dom/media/test/` is optional belt-and-suspenders.
**Gotchas**: `./mach vendor rust` requires cargo-vet; pre-existing vet failures for unrelated crates don't block the mp4parse resolution (per wiki `mp4parse-local-development-firefox`). If upstream landing is blocked, fall back to an interim local vendor patch and document it for re-application on the next bump.

---

## 🤖 Claude Notes

**Worktree**: `~/firefox-2044320/`
**Build**: `./mach build binaries` (C++/Rust-only change — no frontend).
**TDD**: write the `video_colr_two_colr` test first (must FAIL on current `fb7ed9ef` behavior: parse returns `Mp4parseStatus::Invalid` so `open_parser`'s `assert_eq!(rv, Mp4parseStatus::Ok)` panics), then apply the one-line relaxation, verify it passes.
**Sample-file approval gate**: do NOT download the BBC `two-colr.mp4`. Either get explicit user approval to fetch it, or synthesize a minimal two-`colr` fixture in-tree.
**Upstream-first**: the real fix is in mozilla/mp4parse-rust; coordinate the PR + tag, then re-vendor (P2). A local vendor patch is the fallback only.
**Do not commit** — user reviews first.
