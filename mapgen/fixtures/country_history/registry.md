# Fixture tag registry (same roster-row shape as planning/tag_registry.md)

| TAG | Region file | Polity | Kind | Primary culture | Placeholder capital | Notes |
|-----|-------------|--------|------|-----------------|---------------------|-------|
| FXA | `00_test` | Alpha | start | `x` | — | kingdom with a defined tier |
| FXB | `00_test` | Beta | start | `x` | — | principality using a profile |
| FXC | `00_test` | Gamma | start | `x` | — | no country definition: government trigger unresolved |
| FXF | `00_test` | Formable | formable | `x` | — | formables are out of scope |
| FXM | `00_test` | Mu | start | `t` | — | government trigger tests the primary culture (passes) |
| FXD | `01_bad` | Delta | start | `x` | — | unknown ids |
| FXE | `01_bad` | Epsilon | start | `x` | — | locked, disallowed, wrong government |
| FXG | `01_bad` | Zeta | start | `x` | — | justification bookkeeping |
| FXK | `01_bad` | Kappa | start | `x` | — | invalid election date |
| FXL | `01_bad` | Lambda | start | `x` | — | locked by tier and by law, election missing |
| FXN | `01_bad` | Nu | start | `x` | — | government trigger tests the primary culture (fails) |
| FXJ | `01_bad` | Eta | start | `x` | — | start tag with no entry |
| FXH | `01_bad` | Theta | formable | `x` | — | formable given an entry |
| FXI | `02_bad_baseline` | Iota | start | `x` | — | other region |
