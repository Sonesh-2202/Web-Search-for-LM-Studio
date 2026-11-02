"""Write concise pytest failures to the GitHub Actions job summary."""

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> None:
    report = Path(sys.argv[1])
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not report.exists() or not summary_path:
        return

    root = ET.parse(report).getroot()
    cases = root.findall(".//testcase")
    failures = [failure for case in cases for failure in case.findall("failure") + case.findall("error")]
    if not failures:
        message = "## Pytest results\n\nAll tests passed.\n"
    else:
        lines = ["## Pytest failures", ""]
        for case in cases:
            for failure in case.findall("failure") + case.findall("error"):
                details = "\n".join(
                    part.strip()
                    for part in (failure.attrib.get("message", ""), failure.text or "")
                    if part.strip()
                )
                lines.extend((f"### `{case.attrib.get('name', 'unknown test')}`", "", "```text", details[:4000], "```", ""))
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    message = re.sub(r"\s+", " ", details).strip()[:1500]
                    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                    print(f"::error title=Pytest failure::{case.attrib.get('name', 'unknown test')}: {message}")
        message = "\n".join(lines)

    with Path(summary_path).open("a", encoding="utf-8") as summary:
        summary.write(message)


if __name__ == "__main__":
    main()
