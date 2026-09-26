# Format & Connectivity Provenance Ledger

**Purpose.** For a forensic tool, "it works" is not enough — an evaluator (or
opposing counsel) needs to know *how* each vendor's format was understood:
was it from the vendor's own SDK, a published standard, peer-reviewed
research, or original reverse engineering? This ledger answers that question
per vendor, in the format SWGDE-style validation reports expect. Update the
"Verified by team?" column as each row is actually checked — don't mark
anything "Verified" that hasn't genuinely been rechecked against its source.

| Vendor | Component | Legal method used | Citation | Verified by team? |
|---|---|---|---|---|
| Dahua | `parsers/dahua/demuxer.py` — DHAV frame parsing, packed timestamp decode | Clean-room byte-level analysis, consistent with published literature | Yang et al. (2015), SHS Web of Conferences; *Information* 16(11):983 (2025) on DHFS4.1 — see in-file Provenance block | ☐ Not yet — confirm exact bit-layout against primary text |
| Hikvision | `parsers/hikvision/demuxer.py` — PES/MPEG-PS parsing | **Open ISO standard**, not proprietary | ISO/IEC 13818-1 (MPEG-2 Systems) | ✅ Standard is public; no reverse-engineering claim needed here |
| Hikvision | `parsers/hikvision/demuxer.py` — HIKV wrapper skip | Clean-room byte-level analysis, consistent with published literature | Han et al. (2015); Sandeepa et al. (2018), IEEE IC4 | ☐ Not yet — confirm wrapper length against Han et al. |
| CP Plus | `parsers/cpplus/adapter.py` — DHAV compatibility path | Empirical OEM-relationship inference (CP Plus units are commonly Dahua-manufactured hardware) | No published academic citation found as of Sep 2026 — see Section "CP Plus" below | ☐ Document which specific CP Plus model(s) this was verified against |
| Honeywell | *(not yet implemented)* | If built via ONVIF: standards-based, no reverse-engineering claim | ONVIF Core Specification / Profile S | N/A — not yet built |
| Matrix | *(not yet implemented)* | If built via ONVIF: standards-based, no reverse-engineering claim | ONVIF Core Specification / Profile S | N/A — not yet built |
| Uniview | *(not yet implemented)* | Uniview publishes an official Network Device SDK | Uniview Download Center (vendor SDK) | N/A — not yet built |
| TP-Link (VIGI) | *(not yet implemented)* | TP-Link publishes an official VIGI NVR OpenAPI | TP-Link VIGI OpenAPI documentation | N/A — not yet built |
| Godrej | *(not yet implemented)* | No public SDK found; likely rebadged OEM hardware | None yet — see Section "Godrej" below | N/A — not yet built |
| **All vendors (network layer)** | `backend/app/forensics/acquisition/network_stream.py` — live device connection | **Standards-based**: ONVIF Profile S/G (read-only calls only) with a vendor-published-default-path fallback | ONVIF Core Specification v2.6, Sec. 8 (GetDeviceInformation/GetProfiles/GetStreamUri/GetSystemDateAndTime); each vendor's own product/API manual for the fallback RTSP paths | ☐ Not yet tested against real hardware — see file docstring |

## Why this ledger matters for admissibility

SWGDE's video-evidence guidance expects an examiner to be able to explain
*how* a tool arrived at its output, not just that it produced one. A
technical evaluator (or a defense expert during discovery) reviewing this
codebase should be able to trace any parsing decision back to either:

1. A vendor's own published SDK/API documentation, or
2. An open international standard (ISO, ONVIF), or
3. A specific, checkable citation in peer-reviewed or industry (SWGDE/DFRWS)
   literature, or
4. An explicitly documented original clean-room finding, with the sample
   files, dates, and person who performed the analysis on record.

Before this codebase existed, none of the vendor-format code carried any of
these four markers — a technical evaluator had no way to tell reverse
engineering from a lucky guess. This file exists to close that gap. **Do not
add a new parser to this project without adding a row here on the same day.**

## CP Plus

CP Plus does not appear to publish structural documentation of its DVR
storage format, and no dedicated academic paper on CP Plus internals was
found as of September 2026. The current adapter's approach — treating CP
Plus files as Dahua-compatible — rests on the well-known fact that CP Plus,
like many Indian-market security brands, commonly sells Dahua-manufactured
OEM hardware. This is a reasonable engineering starting point, but it is an
**inference**, not a confirmed fact for every CP Plus model on the market.
Action: log the exact CP Plus model number and firmware version for every
unit this adapter is tested against, and note in the case file whether DHAV
compatibility actually held for that specific unit.

## Godrej

No public developer SDK was found for Godrej Security Solutions as of
September 2026; their public tooling is limited to consumer mobile apps. As
with CP Plus, Godrej hardware may be OEM-sourced. Before building a Godrej
parser, the recommended first step is firmware/hardware fingerprinting (checking
chipset identifiers and file headers) to determine whether an existing
Dahua/Hikvision/Uniview-compatible path applies, rather than starting
original reverse engineering from zero.

## Maintenance note

This ledger should be updated every time a new parser is added, an existing
one is modified, or a new source is found. Treat an out-of-date row here the
same way you'd treat an unlabeled evidence bag — it's a chain-of-custody gap
in your documentation, not just your code.
