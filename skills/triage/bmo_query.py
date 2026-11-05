#!/usr/bin/env python3
"""List the bugs a triage run should look at, as JSON on stdout.

Two sources:
  --url URL          a Bugzilla buglist.cgi URL, or a short link (mzl.la) that
                     redirects to one, e.g. the query link in BugBot's
                     "no Severity field set" email.
  --component SPEC   (repeatable) build the BugBot-equivalent untriaged query
                     over these components; SPEC is "Product::Component", or a
                     bare component name with --product.

Read-only and anonymous: restricted (security) bugs are not returned.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmo_http  # noqa: E402

BMO = "https://bugzilla.mozilla.org"
FIELDS = "id,summary,product,component,status,assigned_to,creator,creation_time,keywords"
UA = {"User-Agent": "fx-bug-toolkit-triage"}


def parse_component(spec, default_product=None):
    """'Core::DOM: Events' -> ('Core', 'DOM: Events'); a bare name takes default_product."""
    if "::" in spec:
        product, component = spec.split("::", 1)
        return product.strip(), component.strip()
    if not default_product:
        raise ValueError(f"component {spec!r} has no product; use Product::Component or --product")
    return default_product, spec.strip()


def untriaged_query(pairs):
    """BugBot's untriaged-defects query (no severity, no pending needinfo) over (product, component) pairs."""
    if not pairs:
        raise ValueError("no components")
    params = [
        ("resolution", "---"),
        ("keywords_type", "nowords"), ("keywords", "intermittent-failure"),
        ("email2", "wptsync@mozilla.bugs"), ("emailreporter2", "1"), ("emailtype2", "notequals"),
        ("f1", "bug_type"), ("o1", "equals"), ("v1", "defect"),
        ("f2", "flagtypes.name"), ("o2", "notsubstring"), ("v2", "needinfo?"),
        ("f3", "bug_severity"), ("o3", "anyexact"), ("v3", "--, n/a"),
        ("f4", "status_whiteboard"), ("o4", "notsubstring"), ("v4", "[no-nag]"),
        ("f5", "keywords"), ("o5", "nowords"), ("v5", "meta"),
        ("j6", "OR"), ("f6", "OP"),
    ]
    n = 7
    for product, component in pairs:
        params += [
            (f"j{n}", "AND"), (f"f{n}", "OP"),
            (f"f{n + 1}", "product"), (f"o{n + 1}", "equals"), (f"v{n + 1}", product),
            (f"f{n + 2}", "component"), (f"o{n + 2}", "equals"), (f"v{n + 2}", component),
            (f"f{n + 3}", "CP"),
        ]
        n += 4
    params.append((f"f{n}", "CP"))
    return params


def buglist_params(url):
    """Query params of a BMO buglist.cgi (or rest/bug) URL; rejects anything else."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "bugzilla.mozilla.org":
        raise ValueError(f"not a bugzilla.mozilla.org URL: {url}")
    if parts.path not in ("/buglist.cgi", "/rest/bug"):
        raise ValueError(f"not a buglist URL: {url}")
    params = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
              if k not in ("include_fields", "limit", "offset", "list_id", "query_format", "order")]
    if not params:
        raise ValueError(f"buglist URL has no query: {url}")
    return params


def rest_url(params):
    return f"{BMO}/rest/bug?" + urllib.parse.urlencode(params + [("include_fields", FIELDS)])


def oldest_first(bugs):
    return sorted(bugs, key=lambda b: (b.get("creation_time", ""), b.get("id", 0)))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


SHORT_LINK_HOSTS = ("mzl.la", "bugzil.la")


def link_host_ok(url):
    """Only Bugzilla and Mozilla's short-link hosts are followed (no fetches elsewhere)."""
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.netloc in SHORT_LINK_HOSTS + ("bugzilla.mozilla.org",)


def resolve(url):
    """Follow a short link's redirects (without fetching the buglist page) to the BMO URL."""
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(5):
        if not link_host_ok(url):
            raise ValueError(f"not a Bugzilla or mzl.la/bugzil.la URL: {url}")
        if urllib.parse.urlsplit(url).netloc == "bugzilla.mozilla.org":
            return url
        try:
            opener.open(urllib.request.Request(url, method="HEAD", headers=UA), timeout=30)
            return url
        except urllib.error.HTTPError as e:
            location = e.headers.get("Location")
            if e.code in (301, 302, 303, 307, 308) and location:
                url = urllib.parse.urljoin(url, location)
                continue
            raise
    raise ValueError(f"too many redirects: {url}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--component", action="append")
    ap.add_argument("--product", help="product for bare --component names")
    args = ap.parse_args(argv)
    if args.url:
        params = buglist_params(resolve(args.url))
    else:
        params = untriaged_query([parse_component(c, args.product) for c in args.component])
    bugs = json.loads(bmo_http.get(rest_url(params)))["bugs"]
    json.dump(oldest_first(bugs), sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
