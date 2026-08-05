# Changelog

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
