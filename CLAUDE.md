# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A Frappe / ERPNext custom app for **vehicle rental operations** (GCC market). Handles vehicle & driver lifecycle, CICPA pass compliance, LOA (Letter of Authority) quota management, maintenance, toll/fine tracking, and rental profitability reporting.

- **App name**: `rental_management`
- **Runtime**: Frappe Framework + ERPNext (+ HRMS for some Employee features)
- **Languages**: Python (server controllers, validations, scheduled tasks), JavaScript (client scripts), JSON (DocType definitions, custom field extensions)
- **License**: MIT

## Directory layout

```
rental_management/
├── hooks.py                      # Frappe entry point — doc_events, scheduler, doctype_js
├── api.py                        # Whitelisted API endpoints
├── public/js/                    # Client scripts loaded via doctype_js hook
│   └── driver.js                 # Auto-fetches Nationality from Employee
├── rental_management/
│   ├── doctype/                  # 32 custom doctypes (cicpa, loa, driver_movement, …)
│   ├── custom/                   # JSON extensions to standard ERPNext doctypes (Vehicle, Driver, Customer, Employee, Project)
│   ├── validations/              # Document validate-hook implementations
│   ├── scripts/                  # autoname_assets.py, jinja.py
│   ├── report/                   # Custom reports (vehicle_profitability, …)
│   ├── workspace/                # Desk UI configuration
│   └── number_card/              # Dashboard cards
└── tasks/daily.py                # Scheduled task entry point
```

## Core business logic (read before changing)

### CICPA ↔ LOA quota lifecycle

A **CICPA** is a regulatory pass issued to either a Driver or a Vehicle, drawn from an **LOA**'s quota pool. The full lifecycle is:

1. **Create + Submit** — `validate()` checks remaining quota; `on_submit()` increments `total_created_*_cicpa`, recomputes `allocated_*_quota` / `remaining_*_quota`, then writes back to the Driver/Vehicle (`custom_has_cicpa=1`, `custom_cicpa=<name>`, appends row to certification list).
2. **Status change** — only via `mark_pass_status()` whitelisted API. Direct `db.set_value` will bypass `on_update` and leave LOA counters stale.
3. **Recovered statuses** (`Lost`, `Cancelled`, `Expired`) free the slot back to `remaining_*_quota`. Reactivating to `Active` re-checks quota.
4. **Cancel** — `before_cancel()` recovers quota *before* clearing the LOA link, deletes CICPA Logs, and unlinks from Driver/Vehicle.

Invariants:
- One Active submitted CICPA per Driver and per Vehicle (enforced in `validate()`).
- `_recalculate_loa_quota()` and `_recover_quota_on_cancel()` are the only places quota counters get updated. Don't manipulate them by hand.
- Submitted-doc field writes must use `db_set`, not assignment.

### Driver / Vehicle / Employee validate hooks

`validations/{driver,vehicle,employee,customer,job_offer}_hooks.py` are wired in `hooks.py` under `doc_events`. They sync custom certification tables with the global `Existing Certificates` doctype. Side effects to watch for:

- Saving a Driver/Vehicle re-runs CICPA sync → could double-process if called from `cicpa.py.on_submit()`. The current code does `save(ignore_permissions=True)` and relies on idempotent operations.

## Bench commands

```bash
# After pulling JSON changes:
bench --site <site> migrate
# After changing public/js or fixtures:
bench build && bench --site <site> clear-cache
# Run scheduled task manually:
bench --site <site> execute rental_management.tasks.daily.daily
# Tail logs while testing:
bench --site <site> console        # interactive Python with frappe loaded
```

## Conventions

- **Naming patterns**: `DM-{date}-{#####}` (Driver Movement), `MA-{date}-{#####}` (Maintenance), `SD-{date}-{######}` (Salik or Darbs), `ORI-CICPA-{#####}` (CICPA), `ACC-ASS-YYYY-REF-000001` (Assets via `autoname_assets.py`).
- **Custom field naming**: prefix `custom_` for fields added to standard doctypes (e.g. `custom_has_cicpa`, `custom_cicpa`, `custom_nationality`). Always check `field_order` in the customize-form property setter to know what actually appears on the form — defined ≠ displayed.
- **Terminology**: `CICPA`, `LOA`, and `Salik or Darbs` are domain terms — do not rename them. Other labels should be plain professional English.
- **Field labels**: when changing a Select field's options, remember stored values must migrate too. Prefer relabeling Link/Data field display labels (safe) over changing Select option values (requires data migration).
- **Quotas**: the canonical display columns on LOA are `total_*_quota`, `allocated_*_quota` (labeled "Consumed"), and `remaining_*_quota`. The `total_created_*_cicpa` and `total_cancelled_*_cicpa` counters exist but are hidden — they're internal bookkeeping.

## Gotchas

- **`fetch_from` requires matching field types**. Driver's `custom_nationality` is `Link → Nationality`; Employee's standard `nationality` is `Data`. Crossing types silently fails — that's why nationality is wired through `public/js/driver.js` instead.
- **Standard vs custom fields with the same name**: Driver has both a standard `nationality` (Link) and a custom `custom_nationality` (Link) field. The form's field_order determines which one is shown. Currently `nationality` is displayed; `custom_nationality` exists but is unused.
- **Property setters** (in `custom/*.json` under `property_setters`) override DocType field metadata at runtime. If a label change in `custom/<doctype>.json`'s `custom_fields` block doesn't show up, check for a conflicting property setter.
- **Submitted-doc edits**: any field that should be editable after submit needs `"allow_on_submit": 1` in the DocType JSON.
- **Hooks fire in order**: `validate → before_save → on_update → on_submit → on_change`. `on_change` runs on every save *and* on submit — guard side effects with `is_new()` or `has_value_changed()`.

## When extending

- **New doctype** → `rental_management/rental_management/doctype/<name>/` with `.json`, `.py`, `.js`, `__init__.py`. Add module under `modules.txt` only if introducing a new module.
- **Field on a standard doctype** → edit `rental_management/rental_management/custom/<doctype>.json` (do NOT edit the upstream ERPNext doctype). Use `custom_` fieldname prefix.
- **Client-side handler on a standard doctype** → add a file under `public/js/` and register in `hooks.py` under `doctype_js`.
- **Server-side validation on a standard doctype** → add a function under `validations/` and wire it in `hooks.py` under `doc_events`.
- **Recurring job** → add an entry under `scheduler_events` in `hooks.py` pointing to a function in `tasks/`.

## Testing changes before pushing

1. `bench --site <site> migrate` — applies DocType JSON changes.
2. `bench build && bench --site <site> clear-cache` — rebuilds JS bundles.
3. Hard-reload the form in the browser (the cached form module is sticky).
4. For quota-affecting changes, sanity-check on a test LOA: create CICPA → verify Consumed +1, Remaining −1 → mark as Lost → verify Consumed −1, Remaining +1.

## Authoring notes (for Claude)

- Prefer editing existing files over creating new ones.
- Don't rename `CICPA`, `LOA`, or `Salik or Darbs` in labels — they are recognised regulatory terms.
- Don't change Select option values without a migration patch — existing data references the old values.
- Don't add error handling around operations that can't reasonably fail (e.g. wrapping every `frappe.get_doc` in try/except). The existing code does this in places; don't propagate the anti-pattern.
- Keep error messages user-facing: tell the user what's wrong *and* how to resolve it (see the "quota fully consumed" messages for the pattern).
