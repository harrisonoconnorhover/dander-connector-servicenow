# Changelog

## 0.2.1 — 2026-08-07 (alpha)

- Promote the live-smoked compatibility candidate without changing connector runtime behavior.
- Confirm successful source-free operation on public Dander `0.6.0rc2` alongside the deep
  Salesforce acceptance pipeline.

## 0.2.1rc1 — 2026-08-06 (alpha)

- Extend package compatibility through Dander `0.6.x` without changing connector runtime behavior.
- Validate the existing read-only ServiceNow capabilities against public Dander `0.6.0rc1`.
- Carry the corrected public README into the next immutable PyPI description.

## 0.2.0 — 2026-08-05 (alpha)

- Add record-free connection testing through ServiceNow's Aggregate API.
- Add exact incident counts without materializing business records.
- Add targeted incident lookup by validated `sys_id` through the Table API.
- Require Dander `0.5.x` for the shared read-capability contract.

## 0.1.1

- Declare compatibility with Dander `0.5.x`; connector runtime behavior is unchanged from
  `0.1.0`.

## 0.1.0

- Promote the live-validated ServiceNow connector without runtime changes from `0.1.0rc1`.
- Confirm two successful hosted incident runs, duplicate-free replay, released leases, and a
  clean final Terraform plan against a disposable ServiceNow tenant.

## 0.1.0rc1

- Add the first-party `servicenow_table` Dander connector plugin.
- Package the read-only incidents template, declared schema, and presentation-safe descriptor.
- Preserve stable bounded full reads through Dander's generic dlt REST runtime.
- Cover OAuth, pagination, replay, throttling, permissions, and malformed records with a stateful
  simulator.
