# Security Policy & Forensic Data Handling Standards

## Overview

The **Drishtik** platform is engineered for high-integrity digital forensic investigations where chain of custody, data privacy, evidence preservation, and application security are paramount. This document outlines mandatory security protocols, repository hygiene rules, and evidence-handling standards for all developers, contributors, and operators.

---

## Absolute Repository Rules (Zero-Tolerance)

The following items **MUST NEVER** be committed to the Git repository under any circumstances:

1. **Real CCTV Evidence & Surveillance Media**: No actual surveillance footage, extracted video clips (`.dav`, `.mp4`, `.avi`, `.h264`, `.h265`), or audio captures may ever enter source control.
2. **Forensic Disk Images & Memory Dumps**: Raw physical drive images (`.dd`, `.raw`, `.img`), Expert Witness format images (`.E01`, `.e01`), Advanced Forensic Format (`.aff`, `.aff4`), or virtual disk images (`.vmdk`, `.vhd`).
3. **Passwords, Private Keys & Secrets**: No master passwords, API keys, private keys (`.key`, `.pem`), TLS certificates (`.crt`), wallet credentials, or environment files (`.env`).
4. **Case-Specific PII & Real Case Data**: No witness names, case numbers, officer credentials, or location metadata from live investigations.

Synthetic or sanitized minimal test vectors are permitted only in `sample_data/` and must adhere strictly to repository data policies.

---

## Core Security & Forensic Integrity Principles

### 1. Security & Forensic Integrity Have Priority
Whenever a tradeoff arises between developer convenience and forensic integrity or security posture, **forensic integrity and security always take precedence**. No optimization or feature may compromise evidence immutability or auditability.

### 2. Evidence Immutability & Non-Destructive Handling
- **Original evidence must never be modified.**
- All physical acquisition and disk examination procedures must be conducted through hardware or software write-blockers.
- Where live disks are examined, the engine must operate strictly in read-only mode (`O_RDONLY` / read-only mount).
- Analysis must be performed against bit-stream duplicate forensic images or verified working copies, never on master media.

### 3. Imported Evidence is Untrusted Input
- Video files, proprietary stream containers, filesystem index blocks, and external metadata must be treated as **hostile, untrusted input**.
- Parser routines, demuxers, and decoders must employ defensive boundary checks, integer overflow protections, and isolated subprocess execution (sandboxing) where appropriate to prevent memory corruption, buffer overflows, and arbitrary code execution from malicious or malformed container streams.

### 4. Secure Local Evidence Storage
- Evidence ingested on local workstations must reside in secured, access-controlled directory paths with restricted OS-level permissions.
- Ingested files must be cryptographically hashed (SHA-256) upon arrival to establish an initial cryptographic baseline.
- Cached frames, temporary index tables, and decoded temporary artifacts must be cleaned up securely after examination sessions.

### 5. Authentication & Role-Based Access Control (RBAC) Architecture
Authentication and access control are planned for upcoming phases:
- Every investigator, administrator, and viewer will authenticate with individual, unique credentials (never shared passwords).
- Three explicit role tiers:
  - **ADMIN**: Manages cases, configures system settings, adds collaborators, and governs cryptographic custody.
  - **INVESTIGATOR**: Examines evidence, runs parsers, performs recovery, triggers AI detections, and generates draft reports.
  - **VIEWER**: Read-only examination of finalized evidence, timelines, and approved reports.
- Backend services will enforce role verification on all API endpoints.

### 6. Cryptographic Chain of Custody
- **SHA-256** is the mandatory, primary cryptographic algorithm used to certify evidence authenticity.
- **MD5** may be computed concurrently as an optional secondary reference hash solely for legacy backward compatibility.
- Any discrepancy in hash validation must trigger an immediate integrity alert in the application.

---

## Reporting a Vulnerability

If you discover a security vulnerability or potential forensic integrity flaw within Drishtik:

1. **Do not create a public GitHub issue.**
2. Send a detailed report to the security team at `security@drishtik.local` (or the appointed security contact).
3. Include:
   - Description of the vulnerability or integrity defect.
   - Steps to reproduce using synthetic data.
   - Potential impact on evidence admissibility or system security.
4. The maintainers will acknowledge receipt within 48 hours and coordinate a private remediation plan.
