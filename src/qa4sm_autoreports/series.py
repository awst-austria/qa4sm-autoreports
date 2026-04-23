import warnings

import numpy as np
from pathlib import Path
import shutil
from typing import Union
import time
import os
import pandas as pd
from qa4sm_autoreports.data import Data
import matplotlib.pyplot as plt

from qa4sm_autoreports.report import AutoReportCreator
from qa4sm_api.client_api import Connection


class AutoReportSeries:
    def __init__(self, series_root, reports=None):
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
        """
        self.series_root = Path(series_root)
        self.name = self.series_root.name

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
                    report_root=self.series_root / f.name)
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
                status = r.status
                name = r.name
            s += f"Validation Report {i+1} [{status}]: {str(name)}\n"
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
            report_root=self.series_root / name,
        )

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
            if report.status.lower() == 'collected':
                s.append(True)
            else:
                s.append(False)

        return bool(np.all(s))

    def load_reports(self, reports=None):
        """
        Load one or multiple reports from the list
        (change their status from [NOT LOADED])

        Parameters
        ----------
        reports: int or str or List[int, str]
            Report name(s) or id(s) from the list to load.
        """
        if reports is None:
            reports = np.array(list(self.reports.keys()))

        reports = np.atleast_1d(reports).tolist()

        for r in reports:
            self._load_by_name(self._name(r))

    def new_report(self, report_name, config_template_path,
                   override_params=None, instance="qa4sm.eu"):
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
        """
        if report_name in self.reports:
            raise KeyError(f"Report {report_name} already exists")

        connection = Connection(instance=instance)

        report = AutoReportCreator.from_scratch(
            self.series_root / report_name, config_template_path,
            connection=connection)

        if override_params is not None:
            report.override_params(**override_params)

        assert report.verify_dataset_availability(), \
            "Dataset availability check failed."

        self.reports[report.name] = report

        return report

    @staticmethod
    def _select_epochs(epochs: list, ref_epoch: int, n_epoch: int) -> list:
        """
        Select a subset of epochs relative to a reference epoch.

        Parameters
        ----------
        epochs : list
            Sorted list of epoch strings, ordered from earliest to latest.
        ref_epoch : int
            Reference epoch index. Supports negative indexing (e.g. -2 selects
            the second-to-last epoch).
        n_epoch : int
            Total number of epochs to return, counting backwards from and
            including the reference epoch (e.g. n_epoch=3 returns the reference
            plus the 2 epochs preceding it).

        Returns
        -------
        list
            Subset of ``epochs`` of length ``min(n_epoch, ref_idx + 1)``,
            ending at and including the reference epoch.
        """
        ref_idx = ref_epoch if ref_epoch >= 0 else len(epochs) + ref_epoch
        start_idx = max(0, ref_idx - (n_epoch - 1))  # -1 because ref counts as one
        return epochs[start_idx: ref_idx + 1]

    def track_metrics(self,
                      metric,
                      ref_epoch=-1,
                      n_epochs=10,
                      run=None,
                      path_out=None,
                      pretty_name='ubRMSD',
                      unit='m³m⁻³',
                      p_mask_var=None,
                      p_mask_thres=0.05,
                      tsw='bulk', preprocess=None):
        """
        Create metric tracking data and plot

        Parameters
        ----------
        metric: str, optional
            Metric to track across the epochs. e.g. R_between_0-ISMN_and_1-C3S_combined
        ref_epoch: int, optional
            Reference epoch, i.e. latest one. -1 uses the last report (ordered
            by name).
        n_epochs: int, optional
            Number of epochs BEFORE the reference epochs to include (includes
            the reference).
        run: str, optional
            If the metric should be used from a certain run (from all reports),
            indicate the run name here. None means we search the metric in all
            runs, and use the first one if it's contained in multiple runs
            for a single report.
        path_out: str or path
            Where the stored files are stored. None will store all results
            in the folder of the reference epoch.
        pretty_name: str, optional
            Display name of the metric, e.g. ubRMSD
        unit: str, optional
            Pretty unit, no brackets, e.g m³m⁻³
        p_mask_var: str, optional
            To mask data points where p>thres, pass the p variable name here.
            The same can be achieved via the preprocess function.
        p_mask_thres: float, optional
            The p value thereshold used for masking, only used when p_mask_var
            is passed.
        tsw: int
            Temporal subwindow to use
        preprocess: Callable, optional
            Apply to dataset after loading, can be used for e.g. p value masking
            must take and return a dataset. e.g.
                def _p(ds): ...; return ds
        """
        reports = self._select_epochs(list(self.reports.keys()), ref_epoch, n_epochs)
        path_out = path_out or self.series_root / reports[-1] / "tracking"
        os.makedirs(path_out, exist_ok=True)
        fname = path_out / f"data_tracking_{pretty_name}.yml"

        sd = Data().from_yml(fname) if os.path.isfile(fname) else Data()

        all_stats = {}
        for report in reports:
            ds = self.reports[report].open_datasets()
            dat = None
            if run is not None:
                dat = ds[run]
            else:
                for n, d in ds.items():
                    if metric in d:
                        dat = d.sel(tsw=tsw)
                        break

            if preprocess is not None:
                dat = preprocess(dat)

            if dat is None:
                raise KeyError(f"Metric {metric} not found in any run nc.")

            stats = {'q5': np.nan, 'q25': np.nan, 'q50': np.nan,
                     'q75': np.nan, 'q95': np.nan,
                     'mean': np.nan, 'std': np.nan, 'n': np.nan}

            ser = dat.to_pandas()
            if p_mask_var is not None:
                ser = ser.loc[ser[p_mask_var] <= p_mask_thres, :]

            ser = ser[metric].dropna()

            stats['n'] = len(ser.values)
            for q in ['q25', 'q50', 'q75']:
                try:
                    quant = float(ser.quantile(float(q[1:]) / 100))
                    stats[q] = quant
                except Exception:
                    warnings.warn(f"Quantile {q} could not be computed.")
            try:
                stats['mean'] = float(ser.mean())
                stats['std'] = float(ser.std())
            except Exception:
                warnings.warn("Mean could not be computed.")

            all_stats[report] = stats


        other_stats = {
            'tracking_status': 'green'
        }

        sd.add(other_stats, section='results')
        sd.add(all_stats, section='tracking')

        sd.dump(fname, overwrite=True)

        df = pd.DataFrame.from_dict(sd.data['tracking'])

        bxpstats = []

        names = list(df.columns.values)

        if len(names) < n_epochs:
            names = [None] * (n_epochs - len(names)) + names

        for name in names:
            bxpstats.append({
                'label': name,
                'whislo': df.loc["q5", name] if name is not None else np.nan,
                'whishi': df.loc["q95", name] if name is not None else np.nan,
                'med': df.loc["q50", name] if name is not None else np.nan,
                'q1': df.loc["q25", name] if name is not None else np.nan,
                'q3': df.loc["q75", name] if name is not None else np.nan,
                'fliers': [],
            })

        fig, ax = plt.subplots(figsize=(6, 4))

        positions = np.arange(len(names)) + 1  # 1-based positions
        ax.bxp(bxpstats, positions=positions, showfliers=False)
        ax.set_xticks(positions)
        ax.set_xticklabels(names, rotation=90, ha='center')
        ax.set_title(f"{pretty_name} tracking")
        ax.set_ylabel(f"{pretty_name} [{unit}]")

        fig.savefig(path_out / f"tracking_{pretty_name}.png",
                    bbox_inches='tight')




if __name__ == '__main__':
    from qa4sm_api.client_api import Connection
    from glob import glob
    from qa4sm_api.client_api import ValidationConfiguration

    config_templ = "/home/wpreimes/shares/home/code/qa4sm-autoreports/tests/test_series/report_config_templates"
    out_path = Path("/home/wpreimes/shares/home/code/qa4sm-autoreports/tests/testdata/test_series")

    series = AutoReportSeries(series_root=out_path)

    series.track_metrics(metric='urmsd_between_0-ISMN_and_1-C3S_combined',
                         unit='m³m⁻³', ref_epoch=-1, n_epochs=10)

    series.track_metrics(metric='R_between_0-ISMN_and_1-C3S_combined',
                         pretty_name='R', unit='-', ref_epoch=-1, n_epochs=10,
                         p_mask_var='p_R_between_0-ISMN_and_1-C3S_combined')



    # QA4SM_IP_OR_URL = "test.qa4sm.eu"
    #
    # for report_name in ["epoch1", "epoch2"]:
    #
    #     run_id = series[report_name][0].remote_id
    #     assert series[report_name].status.lower() == 'collected'
    #
    #     assert os.path.isdir(str(out_path / report_name))
    #     assert os.path.isfile(str(out_path / report_name / "val_run_list.csv"))
    #     assert os.path.isfile(str(out_path / report_name / "common_extent.png"))
    #     assert os.path.isfile(str(out_path / report_name / "ReportVars.yml"))
    #
    #     assert os.path.isdir(str(out_path / report_name / "run 1 - ismn_c3s"))
    #     assert len(glob(str(out_path / report_name / "run 1 - ismn_c3s" / "qa4sm_graphics" / "*"))) > 0
    #     assert len(glob(str(out_path / report_name / "run 1 - ismn_c3s" / "latex" / "*"))) > 0
    #
    #     assert os.path.isfile(str(out_path / report_name / "run 1 - ismn_c3s" / f"{run_id}.nc"))
    #     assert os.path.isfile(str(out_path / report_name / "run 1 - ismn_c3s" / "extent.png"))
    #     assert os.path.isfile(str(out_path / report_name / "run 1 - ismn_c3s" / "summary_stats.csv"))
    #     assert os.path.isfile(str(out_path / report_name / "run 1 - ismn_c3s" / f"config-{QA4SM_IP_OR_URL}.json"))
    #
    #     config = ValidationConfiguration.from_file(
    #         out_path / report_name / "run1 - ismn_c3s" / "ContentVars.yml")
    #
    #     assert config.data["remote_id"] == run_id



