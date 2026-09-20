# ADR-0013: License Skoiv MTK Workbench under GNU GPL v3.0

## Status

Accepted

## Date

2026-09-20

## Deciders

Skoiv Labs maintainers / relevant contributors

## Context

Skoiv MTK Workbench is intended to be a free, open-source MediaTek recovery, diagnostics, backup, firmware-analysis, and learning workbench. One of the project's core goals is to make powerful recovery tooling available to users who may not have access to proprietary paid tools, while keeping the implementation transparent and explainable.

The initial repository scaffold recorded Apache License 2.0 as a preliminary preference. That choice favored permissive adoption and explicit patent terms, but it would also allow a third party to take substantial Workbench code, create a closed derivative, distribute it, and keep its modifications unavailable to recipients.

The project also builds around mtkclient as its MediaTek communication engine. mtkclient identifies itself as GPLv3 software. A Workbench distribution must respect the upstream license and must not imply that Skoiv Labs can relicense mtkclient.

The project therefore needs a license that:

1. preserves the freedom to use, study, modify, and redistribute the Workbench;
2. allows commercial use and paid repair/support services;
3. requires recipients of distributed covered modified versions to retain GPL freedoms and source access;
4. aligns naturally with the GPLv3 licensing model of mtkclient;
5. supports an open community where improvements to distributed derivatives remain available under the same license terms.

## Decision

Skoiv MTK Workbench will be licensed under the **GNU General Public License version 3.0 only** (`GPL-3.0-only`).

The repository root will contain the canonical GPLv3 text in `LICENSE`.

Project source files may use the SPDX identifier:

`SPDX-License-Identifier: GPL-3.0-only`

where source-level license headers are appropriate.

Third-party dependencies, firmware artifacts, documentation sources, sample binaries, and community-submitted material retain their own applicable copyright and license terms. The Workbench license does not relicense third-party material.

mtkclient remains an upstream GPLv3 project. Workbench integration must continue through the adapter boundary defined by ADR-0006 for maintainability, testing, safety, and upgrade isolation. The adapter is not treated as a mechanism for avoiding upstream license obligations.

## Decision drivers

- Preserve community freedom for distributed covered derivatives.
- Keep the tool free to use, study, modify, and redistribute.
- Permit commercial use, repair services, support, and paid distribution while preserving recipients' GPL rights.
- Align the project licensing model with the GPLv3 dependency at the center of MTK operations.
- Reduce ambiguity around distributing a Workbench package that includes or relies on mtkclient.
- Prevent a simple path from community-developed Workbench code to a closed black-box derivative that withholds corresponding source from its recipients.

## Alternatives considered

### Apache License 2.0

Apache-2.0 is permissive, commercially friendly, and includes explicit patent provisions. It would make adoption by proprietary products straightforward.

It was not selected because distributed proprietary derivatives could keep modifications closed, which conflicts with the project's goal of preserving community freedom around recovery tooling. It also creates a less straightforward overall licensing story when the distributed application tightly integrates GPLv3 mtkclient.

### MIT License

MIT is simple and highly permissive. It was not selected because it does not require distributed derivatives to preserve source availability or the same software freedoms for recipients.

### GNU Affero General Public License v3.0

AGPLv3 extends copyleft obligations to certain software offered for remote network interaction. Skoiv MTK Workbench is primarily a local desktop application, so this additional network-copyleft scope is not currently necessary.

### Keep Skoiv permissively licensed and execute mtkclient only as an external process

A process boundary is useful architecturally, but licensing should not be designed around assumptions that a subprocess boundary automatically removes GPL obligations. The project wants community-preserving copyleft independently of that question, so this was not selected as the licensing strategy.

## Consequences

### Positive

- Users may use, inspect, modify, and redistribute the Workbench under GPLv3.
- Commercial use remains allowed.
- Covered modified versions that are distributed must preserve applicable GPLv3 rights for recipients.
- The project's licensing philosophy matches its community-access mission.
- The relationship with mtkclient is easier to explain and maintain.
- Contributors know from the beginning that the project is strong-copyleft software.

### Negative / trade-offs

- Organizations that require incorporation into closed-source distributed products may be unable or unwilling to adopt Workbench code directly.
- Distribution and packaging require careful compliance with source, notice, and third-party license obligations.
- Proprietary plugin or extension models may require additional architectural and legal review before being introduced.

### Risks

- Contributors may incorrectly assume that GPL forbids commercial use. Project documentation should explicitly distinguish software freedom from zero price.
- Contributors may assume every file found in a firmware package or community repository can be redistributed under GPL. It cannot; third-party artifacts require separate rights and provenance review.
- Future architecture changes may alter how third-party GPL components are combined or distributed. Such changes require a new ADR and license review rather than modifying this ADR retroactively.

## Migration / rollout

1. Add the canonical GNU GPL v3.0 license text as `LICENSE`.
2. Replace the preliminary Apache-2.0 license-choice note with the accepted GPLv3 decision.
3. Add a License section to the project README.
4. Require new source code to be compatible with `GPL-3.0-only`.
5. Preserve third-party license notices and document bundled dependencies before binary releases begin.
6. Review release packaging before the first public binary release to ensure corresponding-source and notice obligations are satisfied.

## Compatibility impact

The decision does not change the v0.1 runtime architecture. It affects contribution, redistribution, packaging, future plugin design, and binary-release compliance.

Dependencies with incompatible licenses must not be introduced without explicit review.

## Safety impact

No direct device-safety behavior changes. The decision reinforces transparency by ensuring recipients of covered distributed versions retain access to corresponding source under GPLv3 terms.

## Supersedes

None

The earlier Apache-2.0 preference existed only in the preliminary `LICENSE-CHOICE.md` scaffold and was not an accepted ADR.

## Superseded by

None

## Related ADRs

- ADR-0004: Use Python worker for MTK and analysis
- ADR-0006: Access mtkclient through an adapter
- ADR-0007: Version 0.1 is device-read-only
- ADR-0009: Preserve raw evidence alongside abstractions

## Related implementation / PRs

- Initial repository licensing setup
