# Verification protocol

Every adapter passes these steps before it joins the panel. Steps 1 to 6 are the protocol as stated in the proposal; the supplementary checks are also run where they apply. Each step names the trap class it exists to catch (`docs/trap-catalog.md`).

1. **Totals reconciliation.** The adapter's row count on the real export must match the count the source publishes or displays in its interface. Any difference is explained in the adapter's docstring before registration. Catches traps 4 and 5.
2. **Export-versus-interface audit.** Apply the identity filter in the source's interface and in the exported file separately and compare. The two are produced by different code. Catches trap 1.
3. **Identity-label audit.** List every distinct value of the field that records owner identity, exactly as the source spells it, with counts, before writing any filter. The accepted set is chosen and recorded by a person. Labels are matched by decision, not resemblance. Catches traps 1, 2, and 3.
4. **Idempotency.** Running an adapter twice into the same snapshot changes nothing. Catches trap 5.
5. **Clean-environment run.** The full pipeline executes on a machine where no human has placed files or credentials beyond what the workflow provides. Catches trap 7.
6. **Human review at four choke points.** A person reviews the distinct identity values, the totals reconciliation, the entity-resolution review file, and the snapshot summary (counts by source, retained records, flagged sources).

Supplementary checks

- **Documentation-versus-data.** Compare each field the documentation promises against the fields present and their value distributions. Catches trap 2.
- **Retention.** Simulate a source that fails or returns empty; prior records persist with registry state unchanged and the source is flagged. Catches trap 5.
- **Reference reproduction where available.** When an independent extract of the target population exists, have an agent reproduce it and investigate every mismatch. The match rate is diagnostic, not evidence of accuracy, unless the reference is a genuine peer measure.
- **Stratified hand audit** against live sources, with sample size and findings reported per source. Specified; not yet run.

Status fields (trap 6) are read and mapped to `certification_status` where a source publishes them; one source is mapped so far. Making the status check an explicit protocol step for every new source is the change the pilot produced.
