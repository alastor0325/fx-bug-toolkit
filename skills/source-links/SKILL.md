---
name: source-links
user-invocable: false
description: >
  Rule for hyperlinking source code and documentation references.
  Apply whenever mentioning files, functions, line numbers, specs, or any
  resource that has a URL to back it up. Prefer revision-pinned URLs so
  links remain valid as trunk moves.
allowed-tools: []
---

# Source Link Rules

Whenever you mention a specific file, function, type, line, spec section, or
any other resource that has a public URL, **always hyperlink the referenced
text**. Never cite a source location or document as plain text if a link
exists.

## Golden Rule

**Prefer revision-pinned URLs over trunk/tip/HEAD URLs.** Trunk links rot as
code moves; a pinned link keeps pointing at the line you cited. Use trunk
URLs only when the host does not support pinning (see
[Chromium Code Search](#chromium-code-search)).

## When to Link

- Source files and functions (Firefox, Chromium, any open-source project)
- Specification sections (WHATWG, W3C, TC39, IETF, etc.)
- Bug reports (Bugzilla, GitHub Issues, Chromium Issue Tracker)
- Documentation pages
- Any other web-accessible resource

## Anchor Text Rules

- Use the function name, identifier, or short description as anchor text —
  not the raw URL.
- If citing a line range, use the starting line number.
- If no specific line is known, link to the file root.
- Apply in all output contexts: prose, tables, code snippets, and plans.
- If you are not sure whether a URL exists or is stable, omit the link rather
  than guessing one.

## Searchfox (Firefox, WebKit)

### URL Format

```
https://searchfox.org/{repo}/rev/{hash}/{path}#{line}
https://searchfox.org/{repo}/rev/{hash}/{path}#{start}-{end}
```

### Repository IDs

| Repo ID                               | Description             |
|---------------------------------------|-------------------------|
| `firefox-main`                        | Firefox trunk (primary) |
| `firefox-beta` / `mozilla-beta`       | Beta branch             |
| `firefox-release` / `mozilla-release` | Release branch          |
| `firefox-esr115`                      | ESR 115                 |
| `firefox-esr128`                      | ESR 128                 |
| `firefox-esr140`                      | ESR 140                 |
| `wubkat`                              | WebKit                  |

### Revision Resolution Strategy

1. Get the local revision: `git rev-parse HEAD`.
2. Validate it on searchfox by fetching a sentinel path such as
   `https://searchfox.org/firefox-main/rev/{hash}/moz.configure`.
   - If `200`: use this hash for all links in the session.
   - If `404` (searchfox hasn't indexed this revision yet): fetch
     `https://searchfox.org/firefox-main/source/moz.configure` and extract
     the indexed revision from the page content.
3. Cache the validated revision for the remainder of the session so every
   link uses the same pin.
4. For ESR / beta branches, repeat the resolution with the appropriate
   repo ID.

### Mercurial Hash Compatibility

```
https://searchfox.org/{repo}/hgrev/{hg-hash}/{path}#{line}
```

Searchfox auto-redirects Mercurial hashes to the matching Git revision, so
`hgrev/` URLs are safe when you only have an hg hash on hand.

## GitHub

```
https://github.com/{owner}/{repo}/blob/{hash}/{path}#L{line}
https://github.com/{owner}/{repo}/blob/{hash}/{path}#L{start}-L{end}
```

## GitLab

```
https://{host}/{owner}/{repo}/-/blob/{hash}/{path}#L{line}
```

Known hosts: `gitlab.xiph.org`, `code.videolan.org`.

## googlesource.com

```
https://{host}/{repo}/+/{hash}/{path}#{line}
```

Known hosts: `chromium.googlesource.com`, `aomedia.googlesource.com`,
`webrtc.googlesource.com`.

## Codeberg

```
https://codeberg.org/{owner}/{repo}/src/commit/{hash}/{path}#L{line}
```

## Chromium Code Search

```
https://source.chromium.org/chromium/chromium/src/+/main:{path};l={line}
```

`source.chromium.org` does **not** support revision pinning in URLs. When
you need a pinned Chromium link, use the googlesource.com mirror instead:

```
https://chromium.googlesource.com/chromium/src/+/{hash}/{path}#{line}
```

## FFmpeg (via GitHub mirror)

```
https://github.com/FFmpeg/FFmpeg/blob/{hash}/{path}#L{line}
```

The Firefox `moz.yaml` revision maps to a git commit on this mirror.

## Bugzilla

```
https://bugzilla.mozilla.org/show_bug.cgi?id={id}
```

Anchor text: `[Bug {id}](URL)`.

## Specifications

Trusted spec domains:

- `html.spec.whatwg.org` — WHATWG HTML Standard
- `w3c.github.io` — W3C specs (WebCodecs, MSE, EME, etc.)
- `webaudio.github.io` — Web Audio API
- `tc39.es` — ECMAScript
- `datatracker.ietf.org` — IETF RFCs
- `www.rfc-editor.org` — RFC editor
- `itu.int` — ITU-T codec specs (H.264, H.265)

Format: `[Section Name](full URL with anchor)`.

## Examples

**Searchfox (revision-pinned):**
[`MediaDecoder::Shutdown`](https://searchfox.org/firefox-main/rev/8fe6930c0832009b3162bebee7d4ede1a4c8c9a8/dom/media/MediaDecoder.cpp#456)

**Searchfox (WebKit):**
[`MediaPlayer::pause`](https://searchfox.org/wubkat/rev/abc123def456/Source/WebCore/platform/graphics/MediaPlayer.cpp#120)

**GitHub:**
[`nestegg_read_packet`](https://github.com/mozilla/nestegg/blob/abc123def456/src/nestegg.c#L1234)

**GitLab:**
[`dav1d_decode`](https://code.videolan.org/videolan/dav1d/-/blob/abc123def456/src/decode.c#L567)

**googlesource.com:**
[`vpx_codec_decode`](https://chromium.googlesource.com/webm/libvpx/+/abc123def456/vpx/vpx_decoder.c#89)

**Chromium (pinned via googlesource):**
[`MediaFoundationCdm::OnHardwareContextReset`](https://chromium.googlesource.com/chromium/src/+/abc123def456/media/cdm/win/media_foundation_cdm.cc#680)

**Codeberg:**
[`SoundTouch::processRemainingFrames`](https://codeberg.org/soundtouch/soundtouch/src/commit/abc123def456/source/SoundTouch/SoundTouch.cpp#L345)

**FFmpeg:**
[`avcodec_send_packet`](https://github.com/FFmpeg/FFmpeg/blob/abc123def456/libavcodec/decode.c#L567)

**File-level (no specific line):**
[`MFMediaEngineParent.cpp`](https://searchfox.org/firefox-main/rev/8fe6930c0832009b3162bebee7d4ede1a4c8c9a8/dom/media/ipc/MFMediaEngineParent.cpp)

**Spec section:**
[HTML Living Standard §8.5 — The `media` element](https://html.spec.whatwg.org/multipage/media.html#media-element)

**Bug:**
[Bug 1234567](https://bugzilla.mozilla.org/show_bug.cgi?id=1234567)
