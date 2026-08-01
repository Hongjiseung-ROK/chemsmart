# Pretransport Tool-Schema Binding Diagnostic

This directory is a retained development diagnostic, not a DeepSeek model
experiment result.

- All 12 planned settings-by-knowledge runs were rejected before transport.
- The recorded transport-attempt count is zero, so no model response or model
  performance observation exists.
- The preregistered tool schema omitted Runtime V2's constant virtual
  `ask_user` tool. The fail-closed request-binding gate correctly detected the
  mismatch.
- The campaign receipt and empty response/tool-trace projections are retained
  to document this harness integration defect. They must be excluded from all
  component-effect, model-quality, token, cost, and latency analyses.
- The corrected campaign uses a new campaign and run identity ending in `r1`.

No Gaussian, ORCA, xTB, scheduler, or HPC operation was attempted.
