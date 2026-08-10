"""Phase 10 — validate the release-signing path with a disposable keystore.

Generates a temporary keystore OUTSIDE the checkout, builds a signed release
APK, verifies it with apksigner/aapt2, then removes every trace (keystore,
signing properties, temp dir). Never creates a production identity.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "android"
JBR = Path(os.environ.get("JAVA_HOME", "C:/Program Files/Android/Android Studio/jbr"))
KEYTOOL = JBR / "bin" / "keytool.exe"
ANDROID_HOME = Path(
    os.environ.get("ANDROID_HOME", "C:/Users/gustavo/AppData/Local/Android/Sdk")
)
APKSIGNER = ANDROID_HOME / "build-tools" / "35.0.0" / "apksigner.bat"
AAPT2 = ANDROID_HOME / "build-tools" / "35.0.0" / "aapt2.exe"
SIGNING_PROPS = ANDROID / "release-signing.properties"
OUTPUT = ANDROID / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"

ALIAS = "phase10-validation"
PASSWORD = "phase10-temp-password"


def run(
    command: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True)


def main() -> int:
    tmp_root = Path(tempfile.gettempdir()) / f"phase10-keystore-{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    keystore = tmp_root / "phase10-validation.jks"
    gradlew = str(ANDROID / "gradlew.bat")
    try:
        generated = run(
            [
                str(KEYTOOL),
                "-genkeypair",
                "-keystore",
                str(keystore),
                "-storepass",
                PASSWORD,
                "-keypass",
                PASSWORD,
                "-alias",
                ALIAS,
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "30",
                "-dname",
                "CN=Phase10 Validation,O=StreamDeck,L=Local,C=BR",
            ]
        )
        if generated.returncode != 0:
            print(f"KEYTOOL_FAILED rc={generated.returncode}")
            print(generated.stderr[-600:])
            return 1
        print("KEYTOOL=ok")

        os.environ["JAVA_HOME"] = str(JBR)
        os.environ["ANDROID_HOME"] = str(ANDROID_HOME)
        SIGNING_PROPS.write_text(
            "\n".join(
                [
                    f"storeFile={keystore.as_posix()}",
                    f"storePassword={PASSWORD}",
                    f"keyAlias={ALIAS}",
                    f"keyPassword={PASSWORD}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        build = run(
            [
                gradlew,
                ":app:assembleRelease",
                ":app:printReleaseSigningStatus",
                "--console=plain",
            ],
            cwd=ANDROID,
        )
        print("ASSEMBLE_RC=", build.returncode)
        status_lines = [
            line for line in build.stdout.splitlines() if "RELEASE_SIGNING" in line
        ]
        print(" | ".join(status_lines) or build.stdout[-500:])
        if build.returncode != 0:
            print(build.stdout[-800:], build.stderr[-400:])
            return 1

        if not OUTPUT.is_file():
            print(f"OUTPUT_MISSING {OUTPUT}")
            return 1
        print(f"APK={OUTPUT.name} bytes={OUTPUT.stat().st_size}")

        verify = run([str(APKSIGNER), "verify", "--print-certs", str(OUTPUT)])
        print("APKSIGNER_RC=", verify.returncode)
        fingerprint_lines = [
            line
            for line in (verify.stdout + verify.stderr).splitlines()
            if "SHA256" in line
        ]
        print(" | ".join(fingerprint_lines) or (verify.stdout + verify.stderr)[-600:])
        if verify.returncode != 0:
            return 1

        aapt = run(
            [
                str(AAPT2),
                "dump",
                "xmltree",
                "--file",
                "AndroidManifest.xml",
                str(OUTPUT),
            ]
        )
        merged = aapt.stdout + aapt.stderr
        for marker in [
            "versionName",
            "versionCode",
            "allowBackup",
            "usesCleartextTraffic",
            "dataExtractionRules",
        ]:
            hits = [line for line in merged.splitlines() if marker in line]
            print(f"{marker}: {' | '.join(hits[:1]) if hits else 'NOT FOUND'}")

        print("SIGNED_VALIDATION=ok")
        return 0
    finally:
        SIGNING_PROPS.unlink(missing_ok=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
        print("CLEANUP=done")


if __name__ == "__main__":
    raise SystemExit(main())
