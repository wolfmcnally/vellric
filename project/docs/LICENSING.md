# Licensing and source

Vellric 0.2.0 is AGPL-3.0-only. [Full GNU text](../LICENSE), [NOTICE](../NOTICE) and the original Drawbridge/Starter MIT grants under LICENSES accompany the wheel/source. Those retained grants remain operative; no commercial Artifex grant is claimed.

The project wheel ships Vellric source, docs and notices. PyMuPDF/MuPDF and optional OCR dependencies/system engines install separately and keep their own AGPL/MPL/LGPL/Apache/BSD/MIT and component notices. The exact qualified inventory is [dependencies-qualified.json](dependencies-qualified.json); actual notice texts and source-download hashes are retained in the local release bundle. This is not a wholly permissive OCR stack. The optional `vision` extra installs the MIT-licensed `anthropic` package and its dependencies; that closure is locked in `uv.lock` but is not yet part of the qualified inventory.

The prepared release publishes matching project wheel/source/lock/build material. Its concrete sequence is in [release preparation](RELEASE-PREPARATION.md). A future environment/container that redistributes third-party binaries needs corresponding materials for those actual binaries; that is a separate artifact, not a theoretical hold on these project packages.

The Windows bundle built by `packaging/windows_bundle.py` is such an artifact: beside the project wheel it holds the unmodified binary wheels of PyMuPDF and the OCR extra's other dependencies, each with the license files its own wheel carries, and no assembled source or notice closure. It exists so that a user can install on their own machines where no package index is reachable, and the repository's workflow builds and installs it without publishing it. Giving the bundle to anyone else is redistribution of those binaries and needs the corresponding materials first.

Drawbridge retains MIT and invokes this independently installed complete-job CLI. It does not import Vellric or PyMuPDF. Its public PDF fixtures retain CC-BY-SA/IETF grants separately. Keep each package's source/NOTICE identities together when installing or distributing it.
