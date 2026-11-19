# Offline Linux arm64 qualification

Use a locally staged arm64 image built from Python 3.12.12 on Debian Bookworm slim. Set `VELLRIC_ARM64_IMAGE` to its immutable `sha256:…` image ID. Supply two absolute directories through `VELLRIC_QUAL_INPUTS` and `VELLRIC_QUAL_OUTPUT`. The output directory must be empty.

The input directory must contain the Tesseract 5.5.2 source tarball, `eng.traineddata` and `osd.traineddata` from tessdata_fast 4.1.0, and `debs/` containing the pinned local arm64 build and runtime closure. The Bookworm record used Leptonica 1.82.0, Ghostscript 10.0.0~dfsg-11+deb12u8 and qpdf 11.3.0-1+deb12u1. Include the compiler, make, pkg-config, autoconf, automake, libtool and Leptonica development headers. Supply `wheels/`, `build-wheels.txt` and `runtime-wheels.txt` with the locked build and runtime dependency wheels and per-wheel SHA-256 requirements. The runtime list includes the exact locked Conric source built into a wheel. Record the source commit with its wheel hash. Supply `SHA256SUMS` covering these staging inputs. Package acquisition and image staging must already be complete.

From the Vellric repository root, record the candidate identity and exact image identity:

```sh
./bin/kickoff-tree-id
```

```sh
docker image inspect --format '{{.Id}} {{.Os}}/{{.Architecture}}' "$VELLRIC_ARM64_IMAGE"
```

Run the qualification in the disposable container. Fixture and source bytes are mounted read-only. Provisioning, wheel installation and conversions share the disabled-network venue.

```sh
docker run --rm --init --pull=never --platform linux/arm64 --network none \
  --mount "type=bind,src=$PWD/project,dst=/src,readonly" \
  --mount "type=bind,src=$VELLRIC_QUAL_INPUTS,dst=/inputs,readonly" \
  --mount "type=bind,src=$VELLRIC_QUAL_OUTPUT,dst=/proof" \
  "$VELLRIC_ARM64_IMAGE" bash -euxo pipefail -c '
    test "$(uname -m)" = aarch64
    test "$(python -c "import sys; print(sys.version.split()[0])")" = 3.12.12
    cd /inputs
    sha256sum -c SHA256SUMS
    echo "6235ea0dae45ea137f59c09320406f5888383741924d98855bd2ce0d16b54f21  tesseract-5.5.2.tar.gz" | sha256sum -c
    echo "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2  eng.traineddata" | sha256sum -c
    echo "9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff  osd.traineddata" | sha256sum -c
    dpkg -i debs/*.deb
    mkdir /proof/build /proof/wheel /proof/work
    tar -xzf /inputs/tesseract-5.5.2.tar.gz -C /proof/build
    cd /proof/build/tesseract-5.5.2
    ./autogen.sh
    ./configure --prefix=/proof/native --disable-shared --enable-static --disable-openmp --disable-doc
    make -j2
    make install
    install -m 644 /inputs/eng.traineddata /inputs/osd.traineddata /proof/native/share/tessdata/
    cd /inputs
    export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 SOURCE_DATE_EPOCH=1609459200
    python -m pip install --no-deps --require-hashes --find-links /inputs/wheels -r build-wheels.txt
    cp -a /src /proof/build/project
    python -m pip wheel --no-deps --no-build-isolation -w /proof/wheel /proof/build/project
    python -m venv /proof/venv
    /proof/venv/bin/python -m pip install --no-deps --require-hashes --find-links /inputs/wheels -r runtime-wheels.txt
    /proof/venv/bin/python -m pip install --no-deps /proof/wheel/vellric-*.whl
    /proof/venv/bin/python -m pip check
    /proof/venv/bin/python -I -c "import vellric; assert vellric.__file__.startswith(\"/proof/venv/\")"
    export HOME=/proof/work TMPDIR=/proof/work XDG_CACHE_HOME=/proof/work
    cd /proof
    tools=/proof/venv/bin:/proof/native/bin:/usr/local/bin:/usr/bin:/bin
    tessdata=/proof/native/share/tessdata
    app=/proof/venv/bin/vellric
    "$app" doctor --json --path "$tools" --temp-dir /proof/work --tessdata-dir "$tessdata" > doctor.json
    cat > ocr.yaml <<EOF
vellric:
  path: "$tools"
  temp_dir: /proof/work
  local_only: true
  status_json: true
  progress: none
  ocr:
    mode: auto
    preflight: on
    language: eng
    tessdata_dir: "$tessdata"
EOF
    printf "vellric:\n  ocr: {mode: never, preflight: off}\n" > native.yaml
    samples=/src/docs/samples/inputs
    public=/src/tests/fixtures
    "$app" convert "$samples/native-report.pdf" --out native --config ocr.yaml --config native.yaml > native.status
    "$app" convert "$samples/mixed-rotated-stale.pdf" --out mixed --config ocr.yaml > mixed.status
    "$app" convert "$samples/tall-scroll.pdf" --out scroll --config ocr.yaml > scroll.status
    "$app" convert "$public/Fake_Doc_watermarked.pdf" --out public-doc --config ocr.yaml > public-doc.status
    "$app" convert "$public/Fake_Math_Doc_watermarked.pdf" --out public-math --config ocr.yaml > public-math.status
    {
      uname -m
      ldd --version
      /proof/venv/bin/python --version
      /proof/venv/bin/python -m pip freeze
      /proof/native/bin/tesseract --version
      gs --version
      qpdf --version
      pkg-config --modversion lept
      dpkg-query -W
      sha256sum /proof/wheel/*.whl /proof/native/bin/tesseract /proof/native/share/tessdata/*.traineddata
    } > components.txt
  '
```

Inspect the five status and manifest pairs. Require `complete` at `published`, SHA-256 equal to each read-only source, and page counts of 2, 3, 1, 4 and 4 respectively. The native result matches the native word and typography golden. The mixed result recognizes pages 2 and 3 and excludes stale text. The scroll result contains all 59 expected lines across five bands. Both public cases have four recognized pages and match the reviewed OCR text on the same native toolchain. Record any genuine platform result separately from the historical numbers.

Keep `doctor.json`, `components.txt`, status files, source and output hashes and candidate/image identities with the gate evidence. Doctor must report Tesseract 5.5.2, PyMuPDF 1.28.2 and OCRmyPDF 17.7.0, available Ghostscript, and no missing language data. The vision stage must be absent. Use the package and fixture checks in the repository gates for additional native and OCR coverage.

For Amazon Linux 2023, stage the arm64 glibc package and development closure for that distribution. Build Tesseract 5.5.2 from the same verified source and data, with Leptonica development headers and the matching Leptonica runtime, Ghostscript and qpdf. Record the chosen package or source identities and verify Python and wheel glibc compatibility inside that image. A Bookworm result qualifies the Bookworm environment.
