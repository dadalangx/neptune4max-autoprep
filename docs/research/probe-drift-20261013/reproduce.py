"""Offline reanalysis and English figures. No printer, SSH, or network access.

Run with Python 3.12 and the packages in requirements.txt.
All source CSV files are retained; no samples are removed.
"""
from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import math
import statistics
import re

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
FIG = ROOT / 'figures'
FIG.mkdir(exist_ok=True)
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 11,
    'axes.titlesize': 13, 'axes.labelsize': 11,
    'axes.spines.top': False, 'axes.spines.right': False,
    'figure.facecolor': 'white', 'axes.facecolor': '#fbfcfe',
    'grid.alpha': .22, 'legend.frameon': False,
    'svg.fonttype': 'none', 'savefig.dpi': 170,
})
BLUE, ORANGE, GREEN, PURPLE = '#1764ab', '#ce650b', '#16845b', '#8753ad'


def read(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def vector(rows, key):
    return np.asarray([float(row[key]) for row in rows])


def close(actual, expected, tolerance=1e-10):
    assert abs(actual - expected) < tolerance, (actual, expected)


def metrics(values):
    x = np.asarray(values)
    return dict(max_abs_mm=float(np.max(np.abs(x))),
                range_mm=float(np.ptp(x)),
                rmse_from_initial_reference_mm=float(np.sqrt(np.mean(x*x))),
                final_delta_mm=float(x[-1]),
                mean_delta_mm=float(np.mean(x)),
                p95_abs_mm=float(np.percentile(np.abs(x), 95)))


def verify_triplets(points, raw):
    groups = defaultdict(list)
    for item in raw:
        assert item['accepted'] == 'True'
        assert int(item['attempt']) == 0
        groups[(item['phase'], int(item['point_index']))].append(float(item['raw_z_mm']))
    assert len(groups) == len(points)
    for row in points:
        assert row['valid'] == 'True' and int(row['retry_count']) == 0
        samples = groups[(row['phase'], int(row['point_index']))]
        assert len(samples) == (1 if row['phase'] == 'cold_arrival' else 3)
        close(statistics.median(samples), float(row['median_z_mm']))
        close(max(samples)-min(samples), float(row['raw_accepted_range_mm']))
        assert max(samples)-min(samples) <= .03 + 1e-10


def finish(fig, name, title, caption):
    fig.suptitle(title, fontsize=16, fontweight='bold', x=.07, ha='left', y=.98)
    fig.text(.07, .018, caption, ha='left', va='bottom', fontsize=9, color='#465364')
    for ax in fig.axes:
        ax.grid(True)
    fig.tight_layout(rect=(.015, .075, .99, .93), h_pad=2.2, w_pad=2)
    for text in fig.findobj(matplotlib.text.Text):
        assert not re.search('[\u4e00-\u9fff]', text.get_text())
    fig.savefig(FIG / (name + '.png'))
    fig.savefig(FIG / (name + '.svg'), metadata={'Date': None})
    plt.close(fig)


manifest = json.loads((ROOT / 'source-manifest.json').read_text(encoding='utf-8'))
for record in manifest['files']:
    file = ROOT / record['file']
    assert hashlib.sha256(file.read_bytes()).hexdigest() == record['sha256'], file

warm = read('warming.csv')
cool = read('interrupted-cooling.csv')
summary = {'scope': 'One Neptune 4 Max; observational runs on 2026-10-13',
           'new_printer_experiments_performed': False,
           'sensor_body_temperature_measured': False,
           'spatial_accuracy_ground_truth_measured': False,
           'source_file_hashes_verified': len(manifest['files'])}
for name, rows in [('warming', warm), ('interrupted_cooling', cool)]:
    assert len(rows) == 61 and all(row['valid'] == 'True' for row in rows)
    z = vector(rows, 'raw_trigger_z_mm')
    delta = z - z[0]
    np.testing.assert_allclose(delta, vector(rows, 'delta_from_baseline_mm'), atol=1e-12)
    summary[name] = dict(samples=len(rows), duration_s=float(rows[-1]['actual_trigger_elapsed_s']),
                         initial_z_mm=float(z[0]), final_z_mm=float(z[-1]), **metrics(delta),
                         bed_range_c=[float(vector(rows, 'bed_actual_c').min()), float(vector(rows, 'bed_actual_c').max())],
                         nozzle_range_c=[float(vector(rows, 'nozzle_actual_c').min()), float(vector(rows, 'nozzle_actual_c').max())])
close(summary['warming']['final_delta_mm'], .29)
close(summary['interrupted_cooling']['final_delta_mm'], -.2125)

fig, axs = plt.subplots(2, 2, figsize=(13.8, 8.6))
for ax, rows, title, color in [(axs[0, 0], warm, 'Near-bed dwell: 61 single probes', BLUE),
                               (axs[0, 1], cool, 'High-park cooling: 61 single probes', ORANGE)]:
    t = vector(rows, 'actual_trigger_elapsed_s')
    d = vector(rows, 'delta_from_baseline_mm')
    ax.plot(t, d, 'o-', color=color, ms=3, lw=1.5)
    ax.axhline(0, color='#66717f', lw=.8)
    ax.set(title=title, xlabel='Elapsed time from first trigger (s)', ylabel='Trigger-height change (mm)')
    ax.text(.04 if d[-1] > 0 else .96, .86, f'Final change: {d[-1]:+.4f} mm',
            transform=ax.transAxes, ha='left' if d[-1] > 0 else 'right', color=color, fontweight='bold')
    ax.set_xlim(0, 920)
for rows, label, color in [(warm, 'Near-bed dwell', BLUE), (cool, 'Interrupted high-park cooling', ORANGE)]:
    t = vector(rows, 'actual_trigger_elapsed_s')
    axs[1, 0].plot(t, vector(rows, 'bed_actual_c'), color=color, label=label)
    axs[1, 1].plot(t, vector(rows, 'nozzle_actual_c'), color=color, label=label)
axs[1, 0].set(title='Recorded bed temperature', xlabel='Elapsed time within each phase (s)', ylabel='Bed temperature (deg C)')
axs[1, 1].set(title='Recorded nozzle temperature', xlabel='Elapsed time within each phase (s)', ylabel='Nozzle temperature (deg C)')
axs[1, 0].legend(fontsize=9, loc='lower right')
finish(fig, '01-thermal-history', 'Trigger height changed despite controlled bed and nozzle setpoints',
       'Bed target 60 deg C; nozzle target 140 deg C. Each phase uses its own baseline. Cooling returns to the bed every 15 s.\n'
       'One run per phase. Probe-body temperature and independent physical displacement were not measured.')

waits = {}
for seconds, prefix in [(300, 'wait-300'), (480, 'wait-480')]:
    allpoints, raw = read(prefix+'-points.csv'), read(prefix+'-raw-probes.csv')
    verify_triplets(allpoints, raw)
    scans = [row for row in allpoints if row['phase'] == 'scan']
    baseline = next(row for row in allpoints if row['phase'] == 'baseline')
    assert len(scans) == 90 and len(raw) == 274
    d = vector(scans, 'median_z_mm') - float(baseline['median_z_mm'])
    np.testing.assert_allclose(d, vector(scans, 'delta_mm'), atol=1e-12)
    waits[seconds] = scans
    summary[prefix] = dict(points=90, accepted_probe_groups=90, scan_raw_probes=270,
                           retry_groups=0, duration_after_baseline_s=float(scans[-1]['elapsed_s']),
                           baseline_z_mm=float(baseline['median_z_mm']), **metrics(d),
                           max_triplet_range_mm=float(vector(scans, 'raw_accepted_range_mm').max()))
close(summary['wait-300']['max_abs_mm'], .055)
close(summary['wait-480']['max_abs_mm'], .0125)

fig, axs = plt.subplots(2, 1, figsize=(13.8, 8.3), sharex=True)
for seconds, color in [(300, BLUE), (480, ORANGE)]:
    rows = waits[seconds]
    t = vector(rows, 'elapsed_s')
    axs[0].plot(t, vector(rows, 'delta_mm'), 'o-', ms=3, lw=1.3, color=color, label=f'{seconds // 60}-minute near-bed wait')
    axs[1].plot(t, vector(rows, 'raw_accepted_range_mm'), '.', ms=4.5, color=color, label=f'{seconds // 60}-minute wait: range within each triplet')
axs[0].axhspan(-.02, .02, color=GREEN, alpha=.08, label='Exploratory +/-0.020 mm baseline band')
axs[0].axhline(0, color='#66717f', lw=.7)
axs[0].set(ylabel='Median change from own baseline (mm)', title='90 fixed-XY scan samples per run; three probes per sample')
axs[0].legend(loc='upper left', fontsize=9)
axs[1].axhline(.03, color='#a83030', ls='--', label='Configured triplet tolerance: 0.030 mm')
axs[1].set(xlabel='Elapsed time after post-wait baseline (s)', ylabel='Within-triplet range (mm)',
           title='All triplets passed, but the 5-minute run still drifted between groups', ylim=(-.001, .036))
axs[1].legend(loc='upper right', fontsize=9, frameon=True, framealpha=.96, facecolor='white')
finish(fig, '02-five-vs-eight-minutes', 'Short-term sample agreement does not guarantee long-term stability',
       'Same nominal reset: Z100, auxiliary fan on 60 s / off 300 s. Bed 60 deg C; nozzle 140 deg C. One run per wait.\n'
       'XY remained fixed; omitted travel was simulated with dwells. Host logging extended each scan to about 440 s.')

allpoints, raw = read('reference-180-points.csv'), read('reference-180-raw-probes.csv')
verify_triplets(allpoints, raw)
scans = [row for row in allpoints if row['phase'] == 'scan']
refs = [row for row in allpoints if row['phase'] == 'reference']
baseline = next(row for row in allpoints if row['phase'] == 'baseline')
b = float(baseline['median_z_mm'])
t, z = vector(scans, 'elapsed_s'), vector(scans, 'median_z_mm')
rt = np.r_[0., vector(refs, 'elapsed_s')]
rd = np.r_[0., vector(refs, 'median_z_mm') - b]
assert len(scans) == 90 and len(refs) == 18 and len(raw) == 328
assert [int(row['point_index']) for row in refs] == list(range(5, 91, 5))
assert np.all(np.diff(t) > 0) and np.all(np.diff(rt) > 0)
for i, stamp in enumerate(t):
    k = i//5
    assert rt[k] < stamp < rt[k+1]
uncorrected = z-b
interpolated = uncorrected - np.interp(t, rt, rd)
block_constant = uncorrected - np.repeat(rd[1:], 5)
archived = read('reference-180-interpolated.csv')
np.testing.assert_allclose(interpolated, vector(archived, 'interpolated_corrected_delta_mm'), atol=1e-12)
summary['reference-180'] = dict(points=90, extra_reference_groups=18, baseline_groups=1,
                               scan_raw_probes=270, extra_reference_raw_probes=54,
                               total_raw_probes_including_baseline_and_arrival=328,
                               duration_after_baseline_s=float(rt[-1]),
                               raw=metrics(uncorrected), block_constant=metrics(block_constant),
                               time_interpolated=metrics(interpolated),
                               max_scan_triplet_range_mm=float(vector(scans, 'raw_accepted_range_mm').max()),
                               max_reference_triplet_range_mm=float(vector(refs, 'raw_accepted_range_mm').max()))
close(summary['reference-180']['raw']['max_abs_mm'], .1225)
close(summary['reference-180']['time_interpolated']['max_abs_mm'], .015426569769965912)
close(summary['reference-180']['time_interpolated']['rmse_from_initial_reference_mm'], .0031333205566214254)

fig, axs = plt.subplots(2, 1, figsize=(13.8, 8.4), sharex=True, gridspec_kw={'height_ratios':[1.25, 1]})
axs[0].plot(t, uncorrected, 'o-', color=BLUE, ms=3, lw=1, label='90 independent scan medians (uncorrected)')
axs[0].plot(rt, rd, 's--', color=ORANGE, ms=5, lw=1.3, label='Initial baseline + 18 independent reference medians')
axs[0].set(title='After a 3-minute near-bed wait: all observations at the same physical XY', ylabel='Change from initial baseline (mm)')
axs[0].legend(loc='lower right', fontsize=9)
axs[1].plot(t, block_constant, color=PURPLE, lw=.9, alpha=.7, label='Subtract end-of-block reference')
axs[1].plot(t, interpolated, 'o-', color=GREEN, ms=3, lw=1.1, label='Subtract time-interpolated reference')
axs[1].axhspan(-.02, .02, color=GREEN, alpha=.06)
axs[1].axhline(0, color='#66717f', lw=.7)
axs[1].set(title='Residuals of the scan samples, not residuals of reference points against themselves',
           xlabel='Elapsed time after initial baseline (s)', ylabel='Corrected baseline residual (mm)', ylim=(-.023, .023))
axs[1].legend(loc='lower left', fontsize=9)
finish(fig, '03-independent-reference-correction', 'Independent center references reduced fixed-location baseline disagreement',
       'Same 90 raw samples before and after correction; no points deleted. No extrapolation; each sample is bracketed by references.\n'
       'Fixed-XY consistency test only: this does not establish spatial mesh accuracy or separate electrical drift from physical motion.')

fig, axs = plt.subplots(1, 3, figsize=(13.8, 5.4))
labels = ['Raw', 'Block-end\nsubtraction', 'Time\ninterpolation']
series = [uncorrected, block_constant, interpolated]
for ax, key, label in [(axs[0], 'max_abs_mm', 'Maximum absolute baseline residual (mm)'),
                       (axs[1], 'rmse_from_initial_reference_mm', 'RMSE from initial baseline (mm)'),
                       (axs[2], 'range_mm', 'Peak-to-peak residual (mm)')]:
    values = [metrics(s)[key] for s in series]
    ax.bar(labels, values, color=[BLUE, PURPLE, GREEN], width=.65)
    ax.set(title=label.replace(' (mm)', ''), ylabel='mm', ylim=(0, max(values)*1.22))
    for i, value in enumerate(values):
        ax.text(i, value+max(values)*.025, f'{value:.6f}', ha='center', fontsize=10)
finish(fig, '04-correction-metrics', 'Measured benefit and remaining error: the same 90 fixed-XY samples',
       'Time interpolation reduced RMSE and peak-to-peak residual versus block-end subtraction, but its maximum residual was slightly larger.\n'
       'These are baseline-consistency metrics, not independently measured absolute accuracy or an OrcaSlicer A/B comparison.')

realrefs = read('real-xy-center-references.csv')
realmesh = read('real-xy-mesh-points.csv')
rrt = vector(realrefs, 'seconds_from_baseline')
rrd = vector(realrefs, 'drift_from_baseline_mm')
st = vector(realmesh, 'seconds_from_baseline')
applied = vector(realmesh, 'applied_reference_drift_mm')
np.testing.assert_allclose(np.interp(st, rrt, rrd), applied, atol=1e-9)
np.testing.assert_allclose(vector(realmesh, 'raw_z_mm')-applied, vector(realmesh, 'corrected_z_mm'), atol=1e-9)
assert len(realmesh) == 16 and len(realrefs) == 5
summary['real-xy-integration'] = dict(mesh_points=16, total_reference_groups_including_baseline=5,
                                    max_applied_correction_mm=float(applied.max()),
                                    final_reference_change_mm=float(rrd[-1]),
                                    scan_and_reference_duration_s=float(rrt[-1]),
                                    maximum_reference_change_mm=float(rrd.max()),
                                    verification='Interpolation and CSV arithmetic verified; historical native-matrix audit passed',
                                    independent_spatial_accuracy_test=False)
fig, ax = plt.subplots(figsize=(13.8, 5.3))
ax.plot(rrt, rrd, 's-', color=ORANGE, ms=7, label='Independent center references')
ax.plot(st, applied, 'o', color=BLUE, ms=5, label='Interpolated correction applied at each actual XY point')
for row in realrefs:
    ax.annotate('after '+row['after_point'],
                (float(row['seconds_from_baseline']), float(row['drift_from_baseline_mm'])),
                xytext=(0, 12), textcoords='offset points', ha='center', fontsize=9)
ax.set(xlabel='Klipper print time after baseline (s)', ylabel='Reference change / applied correction (mm)',
       title='4 x 4 spatial mesh; references after points 5, 10, 15 and 16', ylim=(-.001, .023))
ax.legend(loc='lower right', fontsize=10)
finish(fig, '05-real-xy-integration', 'Real-XY run verified integration, not ground-truth mesh improvement',
       'Bed 60 deg C; nozzle 140 deg C; actual near-bed wait 180.333 s. Scan and references: 72.495 s.\n'
       'Reference drift reached +0.0175 mm. There is no independent true-bed reference or paired uncorrected spatial scan in this run.')

(ROOT / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'verified': True, 'source_files': len(manifest['files']), 'figures': 5,
                  'warming_final_delta_mm': summary['warming']['final_delta_mm'],
                  'cooling_final_delta_mm': summary['interrupted_cooling']['final_delta_mm'],
                  'raw_reference_trial': summary['reference-180']['raw'],
                  'corrected_reference_trial': summary['reference-180']['time_interpolated']}, indent=2))
