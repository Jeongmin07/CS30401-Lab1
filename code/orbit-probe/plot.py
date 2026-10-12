#!/usr/bin/env python3
"""Plot the valid V2 estimator/probe timing and actual receiver-byte tradeoff."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def receipt(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def read(path):
    with path.open(newline='') as source:
        return list(csv.DictReader(source))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--truth', type=Path, default=Path(__file__).resolve().parents[1] / 'kim-study/path_truth_200s.csv')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Output directory must be new')
    records = json.loads((a.evidence / 'summary.json').read_text())['cases']
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 5.8), sharex=True)
    inputs = [receipt(a.evidence / 'summary.json'), receipt(a.truth)]
    colors = ['#0072B2', '#D55E00']
    for record, color in zip(records, colors):
        folder = a.evidence / 'cases' / record['case']
        state, app = folder / 'bbr_state.csv', folder / 'bbr_app_rx.csv'
        inputs.extend([receipt(state), receipt(app)])
        manifest = json.loads((folder / 'manifest.json').read_text())
        actual = manifest['outputs']
        if receipt(state)['sha256'] != actual['logs_ns3/bbr_state.csv']['sha256'] or receipt(app)['sha256'] != actual['logs_ns3/bbr_app_rx_node_1585.csv']['sha256']:
            raise ValueError('Plot source differs from execution receipt')
        rows = read(state)
        label = 'Policy ON' if manifest['definition']['policy'] else 'Policy OFF'
        axes[0].step([int(r['time_ns']) / 1e9 for r in rows], [int(r['rtprop_ns']) / 1e6 for r in rows], where='post', color=color, label=label)
        bins = collections.Counter()
        total = 0
        for row in read(app):
            if row['flow_id'] != '0' or int(row['bin_end_ns']) - int(row['bin_start_ns']) != 100_000_000:
                raise ValueError('Unsupported receiver attribution/bin')
            value = int(row['app_bytes']); total += value
            bins[int(row['bin_start_ns']) // 1_000_000_000] += value
        if total != record['receiver_total_app_bytes_by_flow']['0']:
            raise ValueError('Receiver bin sum mismatch')
        axes[1].step(list(range(105, 140)), [bins[t] * 8 / 1e6 for t in range(105, 140)], where='post', color=color, label=label)
        for interval in record['exact_probe_intervals']:
            axes[0].axvspan(interval['start_ns'] / 1e9, interval['end_ns'] / 1e9, color=color, alpha=.12)
            axes[1].axvspan(interval['start_ns'] / 1e9, interval['end_ns'] / 1e9, color=color, alpha=.12)
    truth = read(a.truth)
    axes[0].plot([float(r['t_s']) for r in truth], [float(r['rtt_prop_ms']) for r in truth], color='#333333', linestyle='--', label='Nominal geometric propagation RTT')
    axes[0].set(ylabel='Time (ms)', ylim=(84, 104), title='RTprop estimator and geometry reference are different quantities')
    axes[0].legend(frameon=False, fontsize=9, loc='upper right')
    axes[1].set(xlim=(116.6, 136.6), ylim=(0, 110), xlabel='Simulation time (s)', ylabel='Receiver application goodput\n(Mbit/s, 1-second bins)', title='ProbeRTT residence shaded; identical nominal network conditions')
    for ax in axes:
        ax.axvline(121.6, color='#555555', linestyle=':', linewidth=1)
        ax.grid(alpha=.2)
    fig.tight_layout()
    a.out.mkdir(parents=True)
    outputs = []
    for extension in ('png', 'pdf'):
        target = a.out / ('v2-timing-tradeoff.' + extension)
        fig.savefig(target, dpi=220, bbox_inches='tight'); outputs.append(receipt(target))
    plt.close(fig)
    (a.out / 'plot-receipt.json').write_text(json.dumps({'inputs': inputs, 'outputs': outputs, 'tool': receipt(Path(__file__)), 'matplotlib': matplotlib.__version__,
        'limits': 'RTprop uses sparse cached ACK-driven samples held to next row. Geometry is nominal RTT at snapshot time, not a tagged packet path or measured RTT. Goodput bins use receiver application bytes; shading uses exact instrumented ProbeRTT entry/completion.'}, indent=2) + '\n')
    print(a.out)


if __name__ == '__main__':
    main()
