# Validation — 2026-11-05

- .NET SDK 10.0.403, Linux: build PASSED, zero warnings/errors.
- Python black-box API regression suite PASSED: unauthorized access, ingestion, duplicate suppression, conflicting ID rejection, out-of-order observation protection, percentage range validation, future clock rejection, stale data, partial coverage, critical transition, evidence reference and persistence after process restart.
- JavaScript syntax check (`node --check`) PASSED.
- Browser visual/end-to-end validation NOT COMPLETED: browser executable unavailable; attempted browser installation encountered download/archive failure. Do not interpret syntax checks as browser validation.
- Windows CIM collector NOT EXECUTED: environment is Linux. Required before Windows pilot enrollment.
- No capacity, power-loss durability, remote TLS, multi-tenancy or production certification performed.

Source archive excludes build outputs, collected data and credentials. Run the documented smoke suite on a machine with .NET 10 and Python 3 before extending this milestone.
