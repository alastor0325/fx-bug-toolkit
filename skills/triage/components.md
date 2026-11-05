# Triage Components

Which Bugzilla components `/triage` covers comes from the **team profile**
(`$TRIAGE_TEAM`, default `av`). Each profile's **Profile settings** section lists
its default set:

| Team | Profile | Default components |
|---|---|---|
| `av` (default) | [`teams/av.md`](teams/av.md) | the eight Firefox Audio/Video components |
| `dom-core` | [`teams/dom-core.md`](teams/dom-core.md) | the twenty DOM Core components |

The queue fetch, the meta-bug search (if the profile uses one), and the
pre-flight scope filter are all driven from the resolved set.

## Overriding the set — `$TRIAGE_COMPONENTS`

To triage a different set (a narrower subset, or additional components), set
`$TRIAGE_COMPONENTS` to a **`;`-separated** list:

```sh
export TRIAGE_COMPONENTS="Core::DOM: Navigation;Core::DOM: Events"
```

Rules:

- **Exact names.** Each entry must match the Bugzilla product and component names
  exactly (case and spaces matter).
- **`Product::Component`**, or a bare component name, which takes the profile's
  product (`Core` for both current profiles). Qualify names that exist in several
  products, e.g. `Session Restore`.
- **Separator is `;`.** Component names contain spaces, `/`, and `:`, but never
  `;`.
- **Unset = the profile's default set** (the common case).
- **The override applies to whichever team is selected.** Unset it when you
  switch teams.

The first time you run `/triage`, the skill shows the profile's list and asks
whether to keep it or customize it, then persists your choice to
`~/.fx-bug-toolkit.env.sh` (see the skill's **Setup check**).
