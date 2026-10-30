"""Audit synchronized independent-runner capacity and exact recoveries."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics

from recoverml.core import digest


EXPECTED = {(1, 0), (2, 0), (2, 1), (4, 0), (4, 1), (4, 2), (4, 3)}
ROOT = Path(__file__).resolve().parents[1]


def audit(directory):
    directory = Path(directory)
    replicas = {}
    commits = set()
    starts = set()
    target_fingerprints = set()
    for path in directory.iterdir():
        if not path.is_dir() or not (path / "RUN_COMPLETE").is_file():
            continue
        config = json.loads((path / "config.json").read_bytes())
        identity = config["scenario"], config["replica"]
        if identity not in EXPECTED or identity in replicas:
            raise ValueError("Replica identity differs")
        if config["requests"] != 128 or config["repeats"] != 3 or config["versions"] != 16:
            raise ValueError("Replica protocol differs")
        provenance = json.loads((path / "provenance.json").read_bytes())
        commits.add(provenance["commit"])
        for name, sha in provenance["source_sha256"].items():
            if digest((ROOT / name).read_bytes()) != sha:
                raise ValueError("Replica source does not match audit checkout")
        starts.add(config["start_epoch_ns"])
        hashes = json.loads((path / "HASHES.json").read_bytes())
        if any(digest((path / name).read_bytes()) != sha for name, sha in hashes.items()):
            raise ValueError("Replica evidence file differs")
        summaries = json.loads((path / "summary.json").read_bytes())
        rows = [json.loads(line) for line in (path / "requests.jsonl").read_text().splitlines()]
        if len(summaries) != 3 or len(rows) != 384:
            raise ValueError("Replica request matrix differs")
        nodes = {node["id"]: node["blob"] for node in config["manifest"]["nodes"]}
        target_fingerprints.add(tuple(tuple(nodes[node] for node in config["manifest"]["targets"][str(i)]) for i in range(16)))
        by_repeat = defaultdict(list)
        for row in rows:
            by_repeat[row["repeat"]].append(row)
        for repeat, summary in enumerate(summaries):
            group = by_repeat[repeat]
            if len(group) != 128 or {row["request_id"] for row in group} != set(range(128)):
                raise ValueError("Replica request IDs differ")
            for row in group:
                targets = config["manifest"]["targets"][str(row["request_id"] % 16)]
                expected_hashes = {nodes[target]: nodes[target] for target in targets}
                if (not row["exact"] or row["target_ids"] != targets or
                    row["target_sha256"] != expected_hashes or
                    not summary["began_ns"] <= row["started_ns"] <= row["ended_ns"] <= summary["ended_ns"] or
                    abs(row["service_ms"] - (row["ended_ns"] - row["started_ns"]) / 1e6) > 1e-6):
                    raise ValueError("Replica exactness or timing differs")
            if summary["requests"] != 128 or summary["exact"] != 128:
                raise ValueError("Replica summary count differs")
            if abs(summary["throughput_rps"] - 128 / ((summary["ended_ns"] - summary["began_ns"]) / 1e9)) > 1e-5:
                raise ValueError("Replica throughput differs")
            if summary["scheduled_ns"] != config["start_epoch_ns"] + repeat * config["interval_s"] * 1_000_000_000:
                raise ValueError("Replica schedule differs")
        replicas[identity] = summaries
    if set(replicas) != EXPECTED or len(commits) != 1 or len(starts) != 1 or len(target_fingerprints) != 1:
        raise ValueError("Multi-runner matrix or source differs")
    scenarios = {}
    for count in (1, 2, 4):
        rates = []
        skews = []
        for repeat in range(3):
            group = [replicas[(count, replica)][repeat] for replica in range(count)]
            began = min(item["began_ns"] for item in group)
            ended = max(item["ended_ns"] for item in group)
            skew = (max(item["began_ns"] for item in group) - began) / 1e9
            if skew > 5:
                raise ValueError("Replicas did not start within five seconds")
            rates.append(count * 128 / ((ended - began) / 1e9))
            skews.append(skew)
        scenarios[count] = dict(repeat_throughput_rps=rates,
                                median_throughput_rps=statistics.median(rates),
                                maximum_start_skew_s=max(skews))
    baseline = scenarios[1]["median_throughput_rps"]
    for count in (1, 2, 4):
        scenarios[count]["capacity_ratio_to_one"] = scenarios[count]["median_throughput_rps"] / baseline
    return dict(status="PASS", source_commit=commits.pop(), replicas=7, trials=21,
                requests=7 * 3 * 128, exact=7 * 3 * 128, scenarios=scenarios,
                scope="Independent stateless GitHub runners with synchronized starts; no network request path or shared distributed store")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, indent=2))
