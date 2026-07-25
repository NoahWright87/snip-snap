import argparse
import re
from pathlib import Path


def _to_file_version(version: str) -> tuple[int, int, int, int]:
    normalized = version.strip().lstrip("vV")
    core = normalized.split("-", 1)[0]
    if not re.fullmatch(r"\d+(?:\.\d+){0,3}", core):
        raise ValueError(f"unsupported version format: {version!r}")
    parts = [int(part) for part in core.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def build_version_info(version: str) -> str:
    file_version = _to_file_version(version)
    file_version_str = ".".join(str(p) for p in file_version)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={file_version},
    prodvers={file_version},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Noah Wright'),
            StringStruct('FileDescription', 'snip-snap'),
            StringStruct('FileVersion', '{file_version_str}'),
            StringStruct('InternalName', 'snip-snap'),
            StringStruct('OriginalFilename', 'snip-snap.exe'),
            StringStruct('ProductName', 'snip-snap'),
            StringStruct('ProductVersion', '{version}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a PyInstaller version metadata file.")
    parser.add_argument("--version", required=True, help="Version string (for example 1.2.3).")
    parser.add_argument("--output", required=True, help="Output file path.")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_version_info(args.version), encoding="utf-8")


if __name__ == "__main__":
    main()

