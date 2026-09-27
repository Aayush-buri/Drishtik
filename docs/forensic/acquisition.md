# Forensic Acquisition

This document outlines the forensic boundaries and capabilities of the Drishtik acquisition subsystem.

## Acquisition Methods

- **FILE_COPY**: Acquires generic ordinary files. Performs bounded memory chunk reads, computing primary SHA-256 and secondary/reference MD5 hashes.
- **DIRECTORY_COPY**: Acquires a directory of files. Hashes each file individually and produces a manifest.
- **RAW_IMAGE**: Acquires a raw bitstream image (e.g. DD, RAW, BIN). Sector size is recorded only when explicitly declared by the source, otherwise remains NULL. Never hardcode 512 merely because it is common.
- **E01_IMAGE**: Acquires an Expert Witness Format (E01) image. If libewf/pyewf is available, detailed inspection is performed. If E01 is detected but pyewf is unavailable, the acquisition does not claim detailed E01 inspection was completed. It preserves the detection result, records the limitation explicitly, and marks the acquisition as failed/incomplete for full validation.
- **NETWORK_LIVE_PULL**: Performs non-transcoding RTSP live acquisition.
- **UNSUPPORTED**: Unsupported physical acquisition remains explicitly unsupported.

## Hashes and Metadata

- **SHA-256** is the primary integrity hash.
- **MD5** is used as secondary/reference only.
- Sector size is recorded when known and never guessed.
- Vendor and device metadata are only populated when actually available.

## Network Live Pull Claim Boundary

- NETWORK_LIVE_PULL explicitly represents: **non-transcoding RTSP live acquisition; byte-for-byte source comparison not applicable**.
- Drishtik does NOT claim source == destination for RTSP live acquisition.
- The captured file itself may be hash-verified, but not against a nonexistent raw DVR-storage hash.

## Source Immutability

- Source opening is strictly read-only.
- For file-based sources, size and mtime are captured before acquisition and verified after acquisition. The acquisition fails safely if the source changed.
- **Note**: Drishtik does not claim hardware write-blocking unless an external forensic write-blocking mechanism is actually used. Do not overstate capabilities.

## Failure Semantics

On failure or partial acquisition:
- Status must not become COMPLETED.
- Preserves the error or limitation reason.
- Records the acquired size where known and the hashes that were actually computed.
- Does not invent final source hashes.
- Generates an ACQUISITION_FAILED audit log containing structured metadata (acquisition identifier, method, status, SHA-256 when available, acquired size, and relevant limitation/error).
