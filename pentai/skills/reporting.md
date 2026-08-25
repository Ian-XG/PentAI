# Reporting Playbook

Turn findings into a report the owner can act on. For each finding record:

- Title and severity (critical / high / medium / low / info).
- Affected target and evidence (steps to reproduce - the exact request/response,
  payload, or command output that proves it).
- Impact in plain language (the finding's description).
- Remediation.

Call record_finding the moment each one is confirmed - not save_note, which is
for scratch notes and recon breadcrumbs that are NOT themselves a finding.
record_finding is what populates /report and the final engagement report;
anything left in a freeform note won't show up there. Once the engagement's
findings are recorded, run /report to render and save the full report.
