# Printer Profiles

Printer profiles are model-specific support contracts. A BLE printer can be detected
without being safe to print.

## Current Profile

The first profile is `seznik-minix-s1-lyin48d-gy`.

- Support level: `official`
- Protocol: AiYin/LuckPrinter GS v0 wrapper
- Width: 384 dots
- Default density: `medium`
- Default paper mode: `continuous`
- Required next stage after read-only verification: protocol sanity test

## Support Levels

- `detected_unverified`: service or name matched, but model and firmware are not yet verified.
- `official`: maintained in this repo and covered by profile tests.
- `community_verified`: validated by external diagnostics and test prints.
- `experimental`: useful for testing but not trusted for normal printing.
- `unsupported`: no known profile signal matched.

## Contribution Requirements

New profiles must include:

- A profile JSON file under `profiles/<profile-id>/profile.json`.
- Model and firmware evidence from Stage A read-only verification.
- BLE service, write characteristic, and notify characteristic identifiers.
- Conservative print defaults and safety limits.
- A hardware-test artifact with user paths and device identifiers redacted before sharing.
- A Stage A evidence summary for maintainer review before sharing a full artifact ZIP.

Profiles must not unlock printing from detection alone. Printing remains gated by the
certification stages in [hardware-certification.md](hardware-certification.md).
