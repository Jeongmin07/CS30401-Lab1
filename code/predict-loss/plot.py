#!/usr/bin/env python3
"""Plot two static figures from compact summaries; no simulation or raw-log read.

python3 -B plot.py --summaries EXPORT --out NEW_FIGURES
Requires matplotlib. Each used summary and saved artifact has a SHA-256 receipt.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def require(condition, message):
    if not condition:
        raise ValueError(message)


def receipt(path):
    return {'path': str(path), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summaries', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), f'Refusing to overwrite: {args.out}')
    finite = ['loss-first-base', 'loss-first-legacy', 'loss-first-bounded', 'loss-middle-base', 'loss-middle-bounded']
    leo = ['leo10-base', 'leo10-forecast', 'leo10-late']
    data, inputs = {}, []
    for name in finite + leo:
        source = args.summaries / 'cases' / name / 'summary.json'
        data[name] = json.loads(source.read_text(encoding='utf-8'))
        require(data[name]['metrics']['case'] == name, f'Case identity mismatch: {source}')
        inputs.append({**receipt(source), 'case': name, 'full_analysis': data[name]['provenance']['full_analysis']})
    fct = [data[n]['metrics']['fct_s'] for n in finite]
    require(all(data[n]['metrics']['transfer_complete'] and data[n]['metrics']['receiver_bytes'] == data[n]['metrics']['expected_finite_bytes'] == 27600 and data[n]['metrics']['distinct_tagged_drops'] == 1 for n in finite), 'Expected completed 27,600-byte, one-actual-drop controls')
    require(all(isinstance(v, (float, int)) and math.isfinite(v) and v > 0 for v in fct), 'Invalid FCT')
    whole, event = [], []
    for name in leo:
        summary = data[name]
        require(summary['metrics']['duration_s'] == 200, f'Expected whole 200 seconds: {name}')
        matches = [w for w in summary['path_event_windows'] if math.isclose(w['window_start_s'], 25.7, abs_tol=1e-9) and math.isclose(w['window_end_s'], 28.2, abs_tol=1e-9)]
        require(len(matches) == 1, f'Expected one exact [25.7,28.2) window: {name}')
        whole.append(summary['metrics']['receiver_goodput_mbps'])
        event.append(matches[0]['flows'].get('0', {}).get('receiver_application_goodput_mbps', 0))
    require(all(math.isfinite(v) and v > 0 for v in whole + event), 'Invalid LEO receiver goodput')
    percent = [100 * (v / event[0] - 1) for v in event]
    args.out.mkdir(parents=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42})
    blue, gray, green, orange = '#0072B2', '#777777', '#009E73', '#D55E00'
    outputs = []

    def save(fig, stem):
        for extension in ('png', 'pdf'):
            target = args.out / f'{stem}.{extension}'
            fig.savefig(target, dpi=220, bbox_inches='tight')
            outputs.append(receipt(target))
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.1))
    positions, colors = [0, 1, 2, 4, 5], [blue, gray, green, blue, green]
    ax.bar(positions, fct, color=colors, width=.72)
    for x, value in zip(positions, fct):
        ax.text(x, value + max(fct) * .025, f'{value:.9f}', ha='center', va='bottom', fontsize=9)
    ax.set(xticks=[1, 4.5], xticklabels=['First segment lost', 'Middle segment lost'], ylim=(0, max(fct) * 1.28),
           ylabel='Receiver completion time from application start (s)', title='Actual-loss controls: 20 MSS = 27,600 bytes')
    ax.legend(handles=[Patch(color=c, label=l) for c, l in zip([blue, gray, green], ['Baseline K3', 'Legacy K20', 'Bounded K20'])], loc='upper right', frameon=False)
    ax.grid(axis='y', alpha=.2)
    fig.tight_layout()
    save(fig, 'finite-loss-fct')

    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.0))
    labels, colors = ['Baseline', 'Forecast', 'Late +300 ms'], [blue, green, orange]
    axes[0].bar(range(3), whole, color=colors, width=.65)
    for x, value in enumerate(whole):
        axes[0].text(x, value + max(whole) * .02, f'{value:.6f}', ha='center', va='bottom', fontsize=9)
    axes[0].set(ylim=(0, max(whole) * 1.18), ylabel='Receiver application goodput (Mbit/s)', title='Whole run [0, 200) s')
    axes[1].bar(range(3), percent, color=colors, width=.65)
    padding = max(1.0, max(abs(v) for v in percent) * .3)
    for x, (value, goodput) in enumerate(zip(percent, event)):
        axes[1].text(x, value + (padding * .08 if value >= 0 else -padding * .08), f'{value:+.3f}%\n{goodput:.6f} Mbit/s', ha='center', va='bottom' if value >= 0 else 'top', fontsize=9)
    axes[1].set(ylim=(min(0, min(percent)) - padding, max(0, max(percent)) + padding), ylabel='Goodput change relative to baseline (%)', title='First event window [25.7, 28.2) s')
    axes[1].axhline(0, color='#444444', linewidth=.8)
    for ax in axes:
        ax.set_xticks(range(3), labels)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('LEO CUBIC: 10 Mbit/s, 100-packet queue; matched receiver metrics')
    fig.tight_layout()
    save(fig, 'leo10-goodput')
    (args.out / 'plot-receipt.json').write_text(json.dumps({'tool': receipt(Path(__file__)), 'matplotlib_version': matplotlib.__version__, 'inputs': inputs, 'outputs': outputs,
        'plotted_values': {'finite_cases': finite, 'fct_s': fct, 'leo_cases': leo, 'whole_goodput_mbps': whole, 'event_goodput_mbps': event, 'event_change_percent': percent},
        'scope': 'Single deterministic matched runs, no statistical repetitions. FCT includes connection setup; CA_LOSS is not asserted to be an RTO. Absolute goodput bars start at zero; event percentages explicitly normalize to the baseline in the same 2.5-second window.'}, indent=2) + '\n', encoding='utf-8')
    print(args.out)


if __name__ == '__main__':
    main()
