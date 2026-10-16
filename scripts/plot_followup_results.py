"""Render the full audited grids; no new measurement is produced."""
import argparse
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot(cloud, native, output):
    storage = json.loads(cloud.read_bytes())
    latency = json.loads(native.read_bytes())
    if storage['status'] != 'PASS' or latency['status'] != 'PASS':
        raise ValueError('Only complete passing audits can be plotted')
    comparisons = storage['phases']['shared']['comparisons']
    if len(comparisons) != 36 or len(latency['comparisons']) != 36:
        raise ValueError('The full fixed grids are required')
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.6), layout='constrained')
    for dataset, color in [('wine', '#0072B2'), ('breast_cancer', '#D55E00')]:
        rows = [r for r in comparisons if r['dataset'] == dataset and not r['concat_materialized']]
        xs = [4, 16, 64]
        medians = [statistics.median(r['percent_vs_local'] for r in rows if r['versions'] == x) for x in xs]
        axes[0].plot(xs, medians, '-o', color=color, label=dataset.replace('_', ' ').title() + ', fused views')
        for row in rows:
            axes[0].scatter(row['versions'], row['percent_vs_local'], color=color, alpha=.35, s=16)
    axes[0].axhline(0, color='#555555', linestyle='--', linewidth=1, label='Combined table: all 18 controls tie')
    axes[0].set(xscale='log', xticks=[4, 16, 64], xticklabels=['4', '16', '64'], ylim=(-3, 54),
                xlabel='Historical model versions', ylabel='Storage reduction versus local search (%)',
                title='Correlated-loss storage: 9 wins, 27 ties')
    axes[0].legend(fontsize=8, loc='upper left')
    for needed, color, label in [(True, '#0072B2', 'Recomputation required (18)'),
                                 (False, '#D55E00', 'All target files retained (18)')]:
        rows = [r for r in latency['comparisons'] if bool(r['downstream_targets']) == needed]
        axes[1].scatter([r['median_s']['RecoverML_native'] for r in rows],
                        [r['median_s']['DVC_native_batch'] for r in rows], c=color,
                        edgecolors='white', linewidths=.5, s=33, alpha=.8, label=label)
    maximum = max(max(r['median_s'].values()) for r in latency['comparisons']) * 1.08
    axes[1].plot([0, maximum], [0, maximum], '--', color='#555555', linewidth=1, label='Equal time')
    wins = latency['summary']['all']['RecoverML_faster']
    axes[1].set(xlim=(0, maximum), ylim=(0, maximum),
                xlabel='RecoverML: median time to verified files (s)',
                ylabel='Native DVC batch: median time (s)',
                title=f'Native CLI latency: RecoverML faster in {wins}/36')
    strata = latency['summary']
    axes[1].text(.04, .96, 'Median paired speedup:\n'
        f"{strata['recomputation_required']['median_dvc_to_recoverml_ratio']:.2f}x with recomputation\n"
        f"{strata['all_targets_retained']['median_dvc_to_recoverml_ratio']:.2f}x with retained files",
        transform=axes[1].transAxes, va='top', fontsize=8)
    axes[1].legend(fontsize=8, loc='lower right')
    for axis in axes:
        axis.grid(alpha=.2)
        axis.set_axisbelow(True)
    fig.suptitle('Fixed exploratory grids: three seeds, all cases retained', fontsize=13)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cloud', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plot(args.cloud, args.native, args.output)
