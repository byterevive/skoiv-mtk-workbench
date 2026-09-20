# License Choice

## Current decision

Skoiv MTK Workbench is licensed under the **GNU General Public License v3.0 only** (`GPL-3.0-only`).

The canonical license terms are in the repository root `LICENSE` file.

This decision is documented in [ADR-0013](docs/adr/0013-license-skoiv-mtk-workbench-under-gplv3.md).

## Why this changed

The initial scaffold recorded Apache License 2.0 as a preliminary preference because it is permissive and includes explicit patent provisions. Before implementation began, the project reviewed the license and community model of its core MediaTek dependency, mtkclient, which is distributed under GPLv3.

Skoiv Labs also decided that the Workbench should preserve user and community freedom when covered modified versions are distributed, rather than allowing the project to be converted into a closed derivative while keeping community improvements unavailable to recipients.

The preliminary Apache-2.0 preference is therefore retired. The project now uses GPLv3 as documented by ADR-0013.

## Third-party software

Third-party components retain their own copyright and license terms. Skoiv MTK Workbench does not relicense mtkclient or other dependencies. Distribution packaging must preserve all notices and source-availability obligations that apply to bundled dependencies.
