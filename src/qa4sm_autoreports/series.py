# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright (c) 2026 TU Wien & AWST
# SPDX-FileCopyrightText: For a full list of authors, see the AUTHORS file.

import warnings
import numpy as np
from pathlib import Path
from typing import Union
import os
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
import matplotlib.transforms as transforms

from qa4sm_autoreports.data import Data
from qa4sm_autoreports.report import AutoReportCreator
from qa4sm_api.client_api import Connection


class AutoReportSeries:

    def __init__(self, series_root, reports=None, connection=None):
        """
        Cross-report collection with the same validation settings, datasets,
        report template etc.

        Parameters
        ----------
        series_root: str or Path
            Root directory of local series run results
        reports: list[str] or int
            Subset of local validation report names (folders in series_root)
            to load only.
            If an int is passed, we load last n reports only
        connection: Connection, optional
            Connection to use for all reports. If None, connections will be
            created based on the instance in each report's config file.
        """
        self.series_root = Path(series_root)
        self.name = self.series_root.name
        self.connection = connection

        if not self.series_root.exists():
            raise ValueError(f"series_root {self.series_root} does not exist.")

        self.reports = self._load_local_reports(reports)

    def _load_local_reports(self, subset=None):
        """
        Load report series from all report folders in the series_root
        directory.

        Parameters
        ----------
        subset: list[str, ...] or int
            Subset of local validation report names (folders in series_root)
            to load only.
            If subset is an int, we load the last n reports only.

        Returns
        -------
        reports: dict[str, AutoReportCreator]
            Report names and their corresponding AutoReportCreator objects.
        """
        if isinstance(subset, int):
            dirs = []
            for f in sorted(self.series_root.iterdir()):
                if f.is_dir():
                    dirs.append(f)
            subset = dirs[::-1][:subset]

        reports = {}
        for f in sorted(self.series_root.iterdir()):
            if f.is_dir():
                if subset is not None:
                    if f.name not in subset:
                        continue
                r = AutoReportCreator.from_results(
                    report_root=self.series_root / f.name,
                    connection=self.connection)
                name = r.name
                reports[name] = r

        return reports

    def __len__(self) -> int:
        return len(self.reports)

    def __repr__(self):
        # List reports in this series and their status (not loaded, staged,
        s = ('AutoReportSeries\n'
             '----------------\n')
        i = 0
        for name, r in self.reports.items():  # type: AutoReportCreator
            if isinstance(r, str):
                status = "DUMMY REPORT"
            else:
                status = r._STATUS_LUT[r.status]
                name = r.name
            s += f"Report {i} [{status}]: {str(name)}\n"
            i += 1

        if i == 0:
            s += 'no reports in this series found\n...\n'
        asd = f"Local --> {self.series_root}>"
        s += '_' * len(asd) + "\n"
        s += asd

        return s

    def __getitem__(self, item: Union[int, str]) -> AutoReportCreator:
        # Load and return one report from the series by name or id
        name = self._name(item)
        self._load_by_name(name)
        return self.reports[name]

    def _name(self, r: Union[int, str]) -> str:
        # Get report name from id or name
        if isinstance(r, int):
            name = list(self.reports.keys())[r]
        elif isinstance(r, str):
            if r not in list(self.reports.keys()):
                raise KeyError(f"The report '{r}' is not part of "
                               f"the collection")
            else:
                name = r  # pass
        else:
            raise ValueError(f"Pass either report ID or a "
                             f"name from {list(self.reports.keys())}")
        return name

    def _load_by_name(self, name):
        # (Re)load a single report by name from the list
        r = AutoReportCreator.from_results(
            report_root=self.series_root / name, connection=self.connection)

        self.reports[r.name] = r

    def reports_complete(self) -> bool:
        """
        Check whether all reports in the collection are complete
        i.e, collected.

        Returns
        -------
        status: bool,
            True if all are done -> Series up-to-date
        """
        s = []
        for name, report in self.reports.items():
            if report.status >= 2:
                s.append(True)
            else:
                s.append(False)

        return bool(np.all(s))

    def new_report(self,
                   report_name,
                   config_template_path,
                   override_params=None,
                   instance="qa4sm.eu",
                   token=None):
        """
        Start a new validation report from config templates on the chosen
        instance, download and collect all results.

        Parameters
        ----------
        report_name: str
            Name of the report (will be added to the list)
        config_template_path: Path or str
            Path where the .json templates are stored
        override_params: dict, optional
            Params to override settings in config file
        instance: str, optional
            Instance to use for the report
        token: str, optional
            API token for authentication. If None, uses the connection from
            the series if available, otherwise creates a new connection without
            token.
        """
        if report_name in self.reports:
            raise KeyError(f"Report {report_name} already exists")

        if token is None and self.connection is not None:
            connection = self.connection
        else:
            connection = Connection(instance=instance, token=token)

        report = AutoReportCreator.from_scratch(
            self.series_root / report_name,
            config_template_path,
            connection=connection)

        if override_params is not None:
            report.override_params(**override_params)
            for run in report.runs.values():
                run.config.dump(run.local_root / f'config-{instance}.json')

        self.reports[report.name] = report

        return report

    def delete_report(self, report_name, remote=True):
        """
        Delete report from series. By default, also deletes the online runs and
        local copies of the validation runs.

        Parameters
        ----------
        report_name: str, int
            Name of the report to delete from the series
        remote: bool, optional
            Remove the online version of the respective validation runs
        """
        self.reports[report_name].delete(remote=remote)
        self.reports = self._load_local_reports(list(self.reports.keys()))

    @staticmethod
    def _select_epochs(epochs: list, ref_epoch: int, n_epoch: int) -> list:
        """
        Select a subset of epochs relative to a reference epoch.

        Parameters
        ----------
        epochs: list
            Sorted list of epoch strings, ordered from earliest to latest.
        ref_epoch: int
            Reference epoch index. Supports negative indexing (e.g. -2 selects
            the second-to-last epoch).
        n_epoch: int
            Total number of epochs to return, counting backwards from and
            including the reference epoch (e.g., n_epoch=3 returns the reference
            plus the 2 epochs preceding it).

        Returns
        -------
        epochs: list
            Subset of ``epochs`` of length ``min(n_epoch, ref_idx + 1)``,
            ending at and including the reference epoch.
        """
        ref_idx = ref_epoch if ref_epoch >= 0 else len(epochs) + ref_epoch
        start_idx = max(0, ref_idx -
                        (n_epoch - 1))  # -1 because ref counts as one
        return epochs[start_idx:ref_idx + 1]

    @staticmethod
    def _epoch_label(name: str) -> str:
        """
        Short x-axis label for a report name. Report names are either a
        date (e.g. "2026-02-28") or a period ("2025-12-01_to_2026-02-28");
        in both cases the (end) month is used, e.g. "2026-02".
        Other names are returned unchanged.
        """
        end = str(name).split('_to_')[-1]
        try:
            return pd.to_datetime(end).strftime('%Y-%m')
        except (ValueError, TypeError):
            return str(name)

    @staticmethod
    def _pretty_pair(metric: str) -> str:
        """
        "R_between_0-SMOS_L2_and_1-ERA5_LAND" -> "SMOS L2 vs. ERA5 LAND"
        """
        if '_between_' not in metric:
            return metric
        pair = metric.split('_between_', 1)[1]
        parts = [p.split('-', 1)[-1] for p in pair.split('_and_')]
        return " vs. ".join(p.replace('_', ' ') for p in parts)

    @staticmethod
    def _select_run(datasets: dict, run: str):
        """
        Dataset of the run `run` in the datasets of one report. The run name
        can be given in full or as a suffix (e.g. 'Run1'), as run names
        often contain the report name. None if no / no unique match.
        """
        if run in datasets:
            return datasets[run]
        matches = [k for k in datasets if str(k).endswith(run)]
        return datasets[matches[0]] if len(matches) == 1 else None

    def _load_metric(self, report, metric, run=None, tsw='bulk',
                     p_mask_var=None, p_mask_thres=0.05,
                     preprocess=None) -> Union[pd.Series, None]:
        """
        Load the (masked) metric values for a single report. The returned
        Series is indexed by location (lat, lon[, depth]) so that values can
        be compared at common locations between reports.
        Returns None if the metric is not available in the report.
        """
        datasets = self.reports[report].open_datasets()
        if run is not None:
            dat = self._select_run(datasets, run)
            if (dat is not None) and (metric not in dat):
                dat = None
        else:
            dat = None
            for _, d in datasets.items():
                if metric in d:
                    dat = d
                    break

        if dat is None:
            return None

        if 'tsw' in dat.dims:
            dat = dat.sel(tsw=tsw)

        if preprocess is not None:
            dat = preprocess(dat)

        cols = [metric]
        if p_mask_var is not None:
            cols.append(p_mask_var)

        # Location identifiers. In situ results also have a sensor depth
        # (multiple sensors at the same location are possible)
        if 'lat' in dat.variables and 'lon' in dat.variables:
            loc_vars = ['lat', 'lon']
        elif 'latitude' in dat.variables and 'longitude' in dat.variables:
            loc_vars = ['latitude', 'longitude']
        else:
            loc_vars = []
        if 'instrument_depthfrom' in dat.variables:
            loc_vars.append('instrument_depthfrom')

        df = pd.DataFrame({c: np.asarray(dat[c].values).flatten()
                           for c in cols + loc_vars})

        if p_mask_var is not None:
            df = df.loc[df[p_mask_var] <= p_mask_thres, :]

        df = df.dropna(subset=[metric])

        if len(loc_vars) > 0:
            df[loc_vars] = df[loc_vars].round(4)
            # In case of duplicate locations (multiple sensors), use median
            ser = df.groupby(loc_vars)[metric].median()
        else:
            ser = df[metric].reset_index(drop=True)

        return ser

    @staticmethod
    def _paired_difference(current: pd.Series, other: pd.Series) -> dict:
        """
        Compare the metric at common locations between two reports.
        This is independent of changes in the sample (e.g. stations that
        become (in)active, or locations masked due to frozen soils in winter).

        Returns
        -------
        stats: dict
            n_common: number of common locations
            median_diff: median of (current - other) at common locations
        """
        res = {'n_common': 0, 'median_diff': None}
        if (current is None) or (other is None):
            return res
        if not isinstance(current.index, pd.MultiIndex):
            return res  # no location info -> can't pair
        common = current.index.intersection(other.index)
        res['n_common'] = int(len(common))
        if len(common) == 0:
            return res
        diff = (current.loc[common] - other.loc[common]).dropna()
        if len(diff) > 0:
            res['median_diff'] = float(diff.median())
        return res

    def track_metric(self,
                     metric,
                     ref_epoch=-1,
                     n_epochs=10,
                     run=None,
                     path_out=None,
                     pretty_name='ubRMSD',
                     corridor_alpha=0.05,
                     corridor_bounds=None,
                     unit='m³m⁻³',
                     p_mask_var=None,
                     p_mask_thres=0.05,
                     tsw='bulk',
                     series_tracking_stats_csv_table=True,
                     preprocess=None,
                     min_history=3,
                     yoy_offset=None,
                     title=None):
        """
        Create metric tracking data and plot.

        The median of the metric across all locations of the reference
        report is compared against the medians of the previous reports
        (expected range). In addition, the metric is compared at common
        locations against the previous report and against the report from
        one year before (if available), which is independent of changes in
        the spatial sample and of seasonal effects.

        Parameters
        ----------
        metric: str, optional
            Metric to track across the epochs.
            e.g. R_between_0-ISMN_and_1-C3S_combined
        ref_epoch: int or str, optional
            Reference epoch, i.e. latest one. -1 uses the last report (ordered
            by name).
            A number refers to the repoch index, a string to the report name
        n_epochs: int, optional
            Number of epochs BEFORE the reference epochs to include (includes
            the reference).
        run: str, optional
            If the metric should be used from a certain run (from all reports),
            indicate the run name here, or the end of the run name (e.g.
            'Run1', when the run names contain the report name). None means
            we search the metric in all runs, and use the first one if it's
            contained in multiple runs for a single report.
        path_out: str or path
            Where the stored files are stored. None will store all results
            in the folder of the reference epoch.
        pretty_name: str, optional
            Display name of the metric, e.g. ubRMSD
        corridor_alpha: int, optional
            Percentile above/below which a median is considered outside the expected
            interval. Passing None means to not use the corridors.
            Only used when no `corridor_bounds` are passed.
        corridor_bounds: tuple or None, optional (default: None)
            Predefined (lower, upper) thresholds for the expected range of
            the median metric. Either side can be None for a one-sided
            check, e.g. (0.5, None) to only flag medians below 0.5.
            If passed, these are used instead of deriving the range from the
            previous reports (`corridor_alpha` and `min_history` are then
            ignored for the status). None (default) derives the range from
            the medians of the previous reports.
        unit: str, optional
            Pretty unit, no brackets, e.g m³m⁻³
        p_mask_var: str, optional
            To mask data points where p>thres, pass the p variable name here.
            The same can be achieved via the preprocess function.
        p_mask_thres: float, optional
            The p value threshold used for masking, only used when p_mask_var
            is passed.
        tsw: str, optional
            Temporal sub-window to use (netcdf dimension). Default is "bulk"
        series_tracking_stats_csv_table: bool, optional
            Create a .csv table containing the tracking stats that can also
            be imported in Latex.
        preprocess: Callable, optional
            Apply to dataset after loading, can be used for e.g. p value masking.
            Must take and return a dataset. Example::

                lambda ds: ds
        min_history: int, optional (default: 3)
            Minimum number of previous reports (with valid results) that are
            required to derive the expected range. With fewer reports, no
            tracking status is assigned ("none").
        yoy_offset: int or None, optional (default: None)
            Number of reports between the reference report and the report
            covering the same period one year before (e.g. 12 for monthly
            reports), to also compare at common locations against that
            report. None (default) skips the year-over-year comparison.
        title: str, optional
            Plot title. By default derived from the metric name.
        """
        all_reports = list(self.reports.keys())
        if isinstance(ref_epoch, str):
            ref_epoch = all_reports.index(ref_epoch)
        ref_idx = ref_epoch if ref_epoch >= 0 else len(all_reports) + ref_epoch

        reports = self._select_epochs(all_reports, ref_epoch, n_epochs)
        path_out = Path(path_out or self.series_root / reports[-1] / "tracking")
        os.makedirs(path_out, exist_ok=True)
        fname = path_out / f"tracking_{metric}.yml"

        sd = Data().from_yml(fname) if os.path.isfile(fname) else Data()

        load_kwargs = dict(run=run, tsw=tsw, p_mask_var=p_mask_var,
                           p_mask_thres=p_mask_thres, preprocess=preprocess)

        series_stats = {}
        values = {}
        for report in reports:
            ser = self._load_metric(report, metric, **load_kwargs)
            values[report] = ser

            box_stats = {
                'q5': np.nan,
                'q25': np.nan,
                'q50': np.nan,
                'q75': np.nan,
                'q95': np.nan,
                'mean': np.nan,
                'std': np.nan,
                'n': 0
            }

            if ser is None:
                warnings.warn(f"Metric {metric} not found in report {report}. "
                              f"Report is treated as missing.")
            else:
                box_stats['n'] = int(len(ser.values))
                if len(ser.values) > 0:
                    for q in ['q5', 'q25', 'q50', 'q75', 'q95']:
                        box_stats[q] = float(ser.quantile(float(q[1:]) / 100))
                    box_stats['mean'] = float(ser.mean())
                    box_stats['std'] = float(ser.std())

            series_stats[report] = box_stats

        ref_report = reports[-1]
        if values[ref_report] is None:
            raise KeyError(f"Metric {metric} not found in any run of the "
                           f"reference report {ref_report}.")

        # ---- Expected range from previous medians -----------------------
        meds = np.array([series_stats[r]['q50'] for r in reports])
        current_med = meds[-1]
        hist = meds[:-1][np.isfinite(meds[:-1])]

        tracking = {
            'tracking_status': 'none',
            'tracking_color': 'gray',
            'metric': metric,
            'pretty_name': pretty_name,
            'unit': unit,
            'reference_report': ref_report,
            'current_median': float(current_med) if np.isfinite(current_med) else None,
            'current_n': int(series_stats[ref_report]['n']),
            'n_history': int(len(hist)),
            'min_history': int(min_history),
            'alpha': corridor_alpha if corridor_bounds is None else None,
            # 'fixed': predefined bounds, 'history': derived from prev. reports
            'corridor_source': 'history' if corridor_bounds is None else 'fixed',
            # p-value threshold for masking (None: no masking applied)
            'p_mask_thres': p_mask_thres if p_mask_var is not None else None,
            'expected_lower': None,
            'expected_upper': None,
            'previous_report': None,
            'previous_median': None,
            'delta_previous': None,
        }

        lower, upper = None, None
        if corridor_bounds is not None:
            if len(corridor_bounds) != 2:
                raise ValueError("corridor_bounds must be a (lower, upper) "
                                 "tuple, either side can be None.")
            lower, upper = [None if b is None else float(b)
                            for b in corridor_bounds]
            if (lower is None) and (upper is None):
                raise ValueError("At least one of the corridor_bounds "
                                 "must not be None.")
            if (lower is not None) and (upper is not None) and lower > upper:
                raise ValueError(f"Lower corridor bound {lower} is larger "
                                 f"than upper bound {upper}.")
        elif (corridor_alpha is not None) and np.isfinite(current_med) \
                and (len(hist) >= max(min_history, 2)):
            mu, sigma = stats.norm.fit(hist)
            if np.isfinite(mu) and np.isfinite(sigma):
                upper = float(stats.norm.ppf(1 - corridor_alpha, loc=mu, scale=sigma))
                lower = float(stats.norm.ppf(corridor_alpha, loc=mu, scale=sigma))

        if ((lower is not None) or (upper is not None)) \
                and np.isfinite(current_med):
            tracking['expected_lower'] = lower
            tracking['expected_upper'] = upper
            if ((upper is not None) and (current_med > upper)) or \
                    ((lower is not None) and (current_med < lower)):
                tracking['tracking_status'] = "not ok"
                tracking['tracking_color'] = "red"
            else:
                tracking['tracking_status'] = "ok"
                tracking['tracking_color'] = "green"

        # ---- Comparison against previous report ---------------------------
        prev = [r for r in reports[:-1] if np.isfinite(series_stats[r]['q50'])]
        if len(prev) > 0:
            p = prev[-1]
            tracking['previous_report'] = p
            tracking['previous_median'] = float(series_stats[p]['q50'])
            if np.isfinite(current_med):
                tracking['delta_previous'] = float(current_med - series_stats[p]['q50'])
            tracking['paired_previous'] = {
                'report': p,
                **self._paired_difference(values[ref_report], values[p])}
        else:
            tracking['paired_previous'] = {
                'report': None,
                **self._paired_difference(None, None)}

        # ---- Comparison against the same period one year before ------------
        yoy = {'report': None, **self._paired_difference(None, None)}
        if (yoy_offset is not None) and (ref_idx - yoy_offset >= 0):
            yoy_report = all_reports[ref_idx - yoy_offset]
            if yoy_report in values:
                yoy_ser = values[yoy_report]
            else:
                yoy_ser = self._load_metric(yoy_report, metric, **load_kwargs)
            yoy = {'report': yoy_report,
                   **self._paired_difference(values[ref_report], yoy_ser)}
        tracking['paired_yoy'] = yoy

        tracking['summary'] = self._tracking_summary(tracking)

        sd.data['series'] = series_stats
        sd.data['tracking'] = tracking

        if series_tracking_stats_csv_table:
            _df = pd.DataFrame.from_dict(series_stats).T
            _df["n"] = _df["n"].astype(int)
            _df.index = [self._epoch_label(i) for i in _df.index]
            _df.to_csv(path_out / f"stats_{metric}.csv", sep=';',
                       float_format="%.2f", na_rep='--')

        fig = self._plot_tracking(series_stats, tracking, n_epochs,
                                  title=title or self._pretty_pair(metric))
        fig.savefig(path_out / f"tracking_{metric}.png", bbox_inches='tight',
                    dpi=200)
        plt.close(fig)
        sd.dump(fname, overwrite=True)

        return sd

    @staticmethod
    def _fmt(v, digits=None, sign=False) -> str:
        """
        Format a number for the summary text. Without `digits`, the number
        of decimals depends on the magnitude (metrics like R / ubRMSD: 3,
        counts like the number of observations: 0 or 1).
        """
        if v is None:
            return "--"
        if digits is None:
            a = abs(v)
            digits = 0 if a >= 100 else 1 if a >= 10 else 3
        return f"{v:{'+' if sign else ''}.{digits}f}"

    def _tracking_summary(self, t: dict) -> str:
        """
        Short plain-text description of the tracking result that can be
        used directly in the report.
        """
        name = t['pretty_name']
        if t['current_median'] is None:
            return f"No valid {name} values are available for this report."

        s = f"Median {self._fmt(t['current_median'])} " \
            f"(n={t['current_n']})"

        if t['tracking_status'] == 'none':
            if (t.get('corridor_source', 'history') == 'history') and \
                    (t['n_history'] < t['min_history']):
                s += (f", not classified: {t['n_history']} of "
                      f"{t['min_history']} required previous reports "
                      f"available")
        else:
            within = "within" if t['tracking_status'] == 'ok' else "OUTSIDE"
            lo, hi = t['expected_lower'], t['expected_upper']
            if lo is None:
                rng = f"(≤ {self._fmt(hi)})"
            elif hi is None:
                rng = f"(≥ {self._fmt(lo)})"
            else:
                rng = f"[{self._fmt(lo)}, {self._fmt(hi)}]"
            s += f", {within} the expected range {rng}"
        s += "."

        pp = t.get('paired_previous', {})
        if pp.get('median_diff') is not None:
            s += (f" Change at the {pp['n_common']} locations shared with "
                  f"the previous report: {self._fmt(pp['median_diff'], sign=True)}.")

        yy = t.get('paired_yoy', {})
        if yy.get('median_diff') is not None:
            s += (f" Change at the {yy['n_common']} locations shared with "
                  f"the report one year before: {self._fmt(yy['median_diff'], sign=True)}.")
        return s

    def _plot_tracking(self, series_stats: dict, tracking: dict,
                       n_epochs: int, title: str):
        """
        Box plot (Q5/Q25/median/Q75/Q95) per report, with the medians
        connected and the expected median range of the reference report.
        The x axis always has n_epochs slots; reports are placed from the
        right (current report last), i.e. empty slots on the left are filled
        by later reports.
        """
        names = list(series_stats.keys())
        status_color = {'ok': '#2e7d32', 'not ok': '#c62828',
                        'none': '#757575'}[tracking['tracking_status']]

        bxpstats = []
        for name in names:
            s = series_stats[name]
            bxpstats.append({
                'label': self._epoch_label(name),
                'whislo': s['q5'], 'whishi': s['q95'], 'med': s['q50'],
                'q1': s['q25'], 'q3': s['q75'], 'fliers': [],
            })

        n_slots = max(n_epochs, len(names))
        offset = n_slots - len(names)  # empty slots on the left
        width = max(6.0, 0.45 * n_slots + 1.5)
        fig, ax = plt.subplots(figsize=(width, 3.0))
        positions = np.arange(len(names)) + 1 + offset

        bp = ax.bxp(bxpstats, positions=positions, showfliers=False,
                    patch_artist=True, widths=0.55,
                    medianprops=dict(color='black', linewidth=1.5))
        for i, box in enumerate(bp['boxes']):
            current = i == len(names) - 1
            box.set_facecolor(status_color if current else '#cfd8dc')
            box.set_alpha(0.6 if current else 1.0)
            box.set_edgecolor('black')

        meds = np.array([s['q50'] for s in series_stats.values()])
        ax.plot(positions, meds, color='#37474f', lw=1, ls='-', marker='o',
                ms=3, zorder=3, label='Median')

        lo, hi = tracking['expected_lower'], tracking['expected_upper']
        if (lo is not None) or (hi is not None):
            # One-sided bounds: shade up to the current axis limit
            ylim = ax.get_ylim()
            ax.axhspan(ylim[0] if lo is None else lo,
                       ylim[1] if hi is None else hi,
                       color=status_color, alpha=0.15, zorder=0,
                       label='Expected median range')
            for v in (lo, hi):
                if v is not None:
                    ax.axhline(v, color=status_color, lw=0.8, ls='--',
                               zorder=0)
            if (lo is None) or (hi is None):
                ax.set_ylim(ylim)

        labels = []
        for name in names:
            n = series_stats[name]['n']
            labels.append(f"{self._epoch_label(name)}\nn={int(n)}"
                          if n > 0 else f"{self._epoch_label(name)}\nno data")
        ax.set_xticks(np.arange(n_slots) + 1)
        ax.set_xticklabels([''] * offset + labels, rotation=90, fontsize=8)
        ax.get_xticklabels()[-1].set_fontweight("bold")
        ax.get_xticklabels()[-1].set_color(status_color)
        ax.set_xlim(0.4, n_slots + 0.6)

        unit = tracking['unit']
        ylabel = tracking['pretty_name'] if unit in (None, '', '-') \
            else f"{tracking['pretty_name']} [{unit}]"
        ax.set_ylabel(ylabel)
        ax.set_title(f"{tracking['pretty_name']}: {title}", fontsize=11,
                     loc='left')
        ax.grid(axis='y', alpha=0.3)
        # legend above the axes (right of the title), not covering boxes
        ax.legend(loc='lower right', bbox_to_anchor=(1.0, 1.0), ncol=2,
                  fontsize=8, frameon=False, borderaxespad=0.2)
        ax.spines[['top', 'right']].set_visible(False)

        return fig

    def _count_locations(self, report, status_var, good_status=0,
                         run=None, tsw='bulk'):
        """
        Number of locations where the status variable indicates a good
        result (status == good_status), and the number of tested locations,
        in a single report. (None, None) if the status variable is not
        available in the report.
        """
        datasets = self.reports[report].open_datasets()
        if run is not None:
            dat = self._select_run(datasets, run)
            candidates = [] if dat is None else [dat]
        else:
            candidates = list(datasets.values())
        for dat in candidates:
            if status_var in dat:
                if 'tsw' in dat.dims:
                    dat = dat.sel(tsw=tsw)
                vals = np.asarray(dat[status_var].values).flatten()
                return int(np.sum(vals == good_status)), int(vals.size)
        return None, None

    def _label_status_vars(self, status_vars) -> dict:
        """
        Normalise the status variables passed to track_spatial_coverage to
        an (ordered) dict of unique label -> status variable.
        """
        if isinstance(status_vars, dict):
            items = list(status_vars.items())
        else:
            items = [(self._pretty_pair(v), v) if isinstance(v, str)
                     else tuple(v) for v in status_vars]
        labelled = {}
        for label, var in items:
            if label in labelled:
                raise ValueError(
                    f"Duplicate coverage label '{label}' (for {var} and "
                    f"{labelled[label]}). Labels must be unique.")
            labelled[label] = var
        return labelled

    def track_spatial_coverage(self,
                               status_vars,
                               ref_epoch=-1,
                               n_epochs=10,
                               path_out=None,
                               tsw='bulk',
                               good_status=0,
                               log_scale=False,
                               name='coverage'):
        """
        Track the spatial coverage, i.e. the number of locations where the
        validation was successful (status variable == good_status, 0 means
        GOOD in QA4SM), across reports. This is informative only (no
        expected range / tracking status).

        Creates
        - <name>.png: grouped bar plot, one bar per dataset and report
        - <name>.yml: counts per report and dataset, and a short summary
        - stats_<name>.csv: table of the counts (for LaTeX)

        Parameters
        ----------
        status_vars: list or dict[str, str]
            Status variables in the validation results, one bar each. The
            coverage of each bar is the number of locations where the status
            variable equals `good_status`. Either
            - a list of status variable names, labels are derived from the
              dataset pair, e.g.
              ['status_between_0-ERA5_LAND_and_1-C3S_combined',
               'status_between_0-ERA5_LAND_and_2-C3S_active']
              -> 'ERA5 LAND vs. C3S combined', 'ERA5 LAND vs. C3S active'
            - a list of (label, status variable) tuples
            - a dict label -> status variable name (labels must be unique,
              use one of the list options to use the same reference
              dataset for multiple bars).
        ref_epoch: int or str, optional
            Reference (latest) report, name or index.
        n_epochs: int, optional
            Number of reports to include (incl. the reference report).
        path_out: str or Path, optional
            Output directory. By default the tracking folder of the reference
            report.
        tsw: str, optional
            Temporal sub-window to use. Default is "bulk".
        good_status: int, optional (default: 0)
            Status value that marks a successful (GOOD) validation result.
        log_scale: bool, optional (default: False)
            Use a logarithmic y axis. Useful when the datasets have very
            different numbers of locations (e.g. in situ vs. gridded).
        name: str, optional
            Base name of the output files.
        """
        all_reports = list(self.reports.keys())
        if isinstance(ref_epoch, str):
            ref_epoch = all_reports.index(ref_epoch)
        reports = self._select_epochs(all_reports, ref_epoch, n_epochs)
        path_out = Path(path_out or self.series_root / reports[-1] / "tracking")
        os.makedirs(path_out, exist_ok=True)

        status_vars = self._label_status_vars(status_vars)

        series = {}
        for report in reports:
            series[report] = {}
            for label, status_var in status_vars.items():
                n_valid, n_total = self._count_locations(
                    report, status_var, good_status=good_status, tsw=tsw)
                series[report][label] = {'n_valid': n_valid, 'n_total': n_total}

        # ---- summary: change against the previous report ------------------
        ref = reports[-1]
        summary = {}
        texts = []
        for label in status_vars.keys():
            cur = series[ref][label]['n_valid']
            prev_reports = [r for r in reports[:-1]
                            if series[r][label]['n_valid'] is not None]
            prev = series[prev_reports[-1]][label]['n_valid'] \
                if len(prev_reports) > 0 else None
            summary[label] = {
                'current': cur,
                'current_total': series[ref][label]['n_total'],
                'previous': prev,
                'previous_report': prev_reports[-1] if prev_reports else None,
                'change': (cur - prev) if (cur is not None and prev is not None) else None,
            }
            if cur is None:
                texts.append(f"{label}: no results")
            elif prev is None:
                texts.append(f"{label}: {cur} locations")
            else:
                texts.append(f"{label}: {cur} locations ({cur - prev:+d})")
        summary_text = ("Locations with GOOD validation status in this "
                        "report (change compared to the previous report): " + "; ".join(texts) + ".")

        data = Data()
        data.add(series, 'series')
        data.add({'datasets': summary, 'summary': summary_text}, 'coverage')
        data.dump(path_out / f"{name}.yml", overwrite=True)

        # ---- csv table: one row per report, one column per dataset --------
        df = pd.DataFrame({
            label: [series[r][label]['n_valid'] for r in reports]
            for label in status_vars.keys()},
            index=[self._epoch_label(r) for r in reports]).astype('Int64')
        df.to_csv(path_out / f"stats_{name}.csv", sep=';', na_rep='--')

        # ---- grouped bar plot ---------------------------------------------
        labels = list(status_vars.keys())
        n = len(labels)
        # n_epochs slots, reports placed from the right (as in track_metric)
        n_slots = max(n_epochs, len(reports))
        offset = n_slots - len(reports)
        x = np.arange(len(reports)) + offset
        width = 0.8 / n
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b']
        figw = max(6.0, 0.45 * max(n_epochs, len(reports)) + 1.5)
        fig, ax = plt.subplots(figsize=(figw, 3.2))
        for i, label in enumerate(labels):
            vals = np.array([series[r][label]['n_valid']
                             if series[r][label]['n_valid'] is not None
                             else np.nan for r in reports], dtype=float)
            pos = x - 0.4 + width * (i + 0.5)
            bars = ax.bar(pos, vals, width=width * 0.95, label=label,
                          color=colors[i % len(colors)], zorder=2)
            for b, v in zip(bars, vals):
                if np.isfinite(v):
                    ax.text(b.get_x() + b.get_width() / 2, v, f"{int(v)}",
                            ha='center', va='bottom', fontsize=5.5,
                            rotation=90)
        ax.set_xticks(np.arange(n_slots))
        ticklabels = [''] * offset + [self._epoch_label(r) for r in reports]
        ax.set_xticklabels(ticklabels, rotation=90, fontsize=8)
        ax.get_xticklabels()[-1].set_fontweight('bold')
        ax.set_xlim(-0.6, n_slots - 0.4)
        ymax = np.nanmax([series[r][l]['n_valid'] or np.nan
                          for r in reports for l in labels] + [np.nan])
        if log_scale:
            ax.set_yscale('log')
            if np.isfinite(ymax):
                # bars start at 1, top: space for value labels
                ax.set_ylim(bottom=1, top=ymax * 4)
        elif np.isfinite(ymax):
            ax.set_ylim(bottom=0, top=ymax * 1.15)  # space for value labels
        ax.set_ylabel("GOOD locations" + (" (log scale)" if log_scale else ""))
        # legend in its own row between the axes and the title (long
        # dataset labels would otherwise overlap the title)
        ax.set_title("Spatial coverage: locations with GOOD status",
                     fontsize=11, loc='left', pad=20)
        ax.grid(axis='y', alpha=0.3, zorder=0)
        ax.legend(loc='lower left', bbox_to_anchor=(0.0, 1.0), ncol=n,
                  fontsize=8, frameon=False, borderaxespad=0.2)
        ax.spines[['top', 'right']].set_visible(False)
        fig.savefig(path_out / f"{name}.png", bbox_inches='tight', dpi=200)
        plt.close(fig)

        return data