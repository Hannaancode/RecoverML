"""Verify saved Milestone 2 performance evidence without changing it."""
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from recoverml.performance import audit

def main():
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory() as temp:
        evidence = Path(temp) / "performance"
        shutil.copytree(root / "results/milestone2/performance", evidence)
        result = audit(evidence)
        if (result["requests"], result["trials"], result["exact_requests"],
                result["resource_samples"], result["operation_records"]) != (5400, 54, 5400, 2129, 39600):
            raise ValueError("Published Milestone 2 evidence counts differ")
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
