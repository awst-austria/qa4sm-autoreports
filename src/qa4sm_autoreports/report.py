# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright (c) 2026 TU Wien & AWST
# SPDX-FileCopyrightText: For a full list of authors, see the AUTHORS file.

import glob
import warnings
import pandas as pd
import shutil
from datetime import datetime
import os
import time
import re
import numpy as np
import yaml
from pathlib import Path
import subprocess
from typing import Union
import logging

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.extent import GeographicExtent
import qa4sm_autoreports as utils
from qa4sm_autoreports.run import ValidationRun
from qa4sm_autoreports.data import (
    NetcdfMetaData,
    NetcdfData,
    SummaryStatsData,
    ConfigData,
    RunData,
    RemoteData,
    Data
)


class AutoReportCreator:
    """
    Trigger multiple validation runs, check status, compile PDF.
    """
    _STATUS_LUT = {
        0: "Staged",
        1: "Started",
        2: "Processed",
        3: "Collected",
        4: "Compiled",
    }

    def __init__(self, runs, report_root):
        """
        Parameters
        ----------
        runs: list[ValidationRun, ...]
            List of validation runs to use in the report
        report_root: str or Path
            Path where reports from this series are stored.
        """
        self.report_root = Path(report_root)
        self.name = str(self.report_root.name)
        self.runs = self._collect_runs(runs)  # dtype: dict[str, ValidationRun]

    def _collect_runs(self, runs) -> dict:
        _runs = {}
        for run in runs:
            name = run.name
            i = 0
            while name in _runs.keys():
                name = run.name + f"({i})"
                i += 1
            _runs[name] = run
        return _runs

    @classmethod
    def from_scratch(cls, report_root, templates_path, connection,
                     run_name_long=False, force=False):
        """
        Set up report creator from scratch, i.e. from template configs.
        If report_root already exists, runs will be loaded from files.

        Parameters
        ----------
        report_root: str or Path
            Path to the report folder (is created / overwritten)
        templates_path: str or Path
            Path where the config templates (json) are found (we use all
            available files).
        connection: Connection
            QA4SM Connection
        run_name_long: bool, optional
            Instead of naming runs "runX", name them "run X - <template>" instead.
        force: bool, optional
            Force creating a new report_root from scratch
            If False, an error is thrown if it exists.
        """
        template_path = Path(templates_path)
        report_root = Path(report_root)

        if os.path.exists(report_root):
            if force:
                shutil.rmtree(report_root)
            else:
                warnings.warn("Report directory already exists. "
                              "Load runs from existing files.")
                return cls.from_results(report_root)

        os.makedirs(str(report_root))

        templates = glob.glob(str(template_path / '*.json'))
        if len(templates) == 0:
            raise FileNotFoundError(f"No templates found in {template_path}")
        runs = []
        for i, template in enumerate(templates, start=1):
            if run_name_long:
                n = os.path.basename(template).replace('.json', '')
                name = f"run {i} - {n}"
            else:
                name = f"run{i}"
            os.makedirs(str(report_root / name), exist_ok=True)
            instance = connection.session.instance
            shutil.copy(template, str(report_root / name / f"config-{instance}.json"))
            run = ValidationRun.from_template(str(report_root / name),
                                              connection=connection,
                                              name_tag=name)
            runs.append(run)

        return cls(runs, report_root)

    @classmethod
    def from_results(cls, report_root, connection=None):
        """
        Set up report creator from previously created local runs.

        Parameters
        ----------
        report_root: str or Path
            Path to the report folder (is created / overwritten)
        connection: Connection, optional
            Connection to use for all runs. If None, connections will be
            created based on the instance in each run's config file.
        """
        report_root = Path(report_root)

        run_dirs = glob.glob(str(report_root / 'run*'))
        runs = []
        for local_dir in run_dirs:
            name_tag = os.path.basename(local_dir)
            run = ValidationRun.from_results(local_dir, connection=connection,
                                             name_tag=name_tag)
            runs.append(run)

        return cls(runs, report_root)

    @property
    def status(self) -> int:
        """
        Status between all validation runs, returned as a numerical code in
        order of progress
        - 0 - Staged: Local setup created, not triggered online
        - 1 - Started: All runs were triggered
        - 2 - Processed: All runs have finished online
        - 3 - Collected: All results were downloaded locally
        - 4 - Compiled: PDF was created
        """
        run_status = [r.status[0] for _, r in self.runs.items()]
        if ("NOT FOUND" in run_status) or (len(run_status) == 0):
            status = 0
            complete = False
        else:  # either running or finished
            status = 1
            try:
                complete = self.validations_complete()
            except ValueError:
                complete = False

        if complete:
            status = 2
            if os.path.exists(self.report_root / 'ReportVars.yml'):
                status = 3
                pdfs = glob.glob(str(self.report_root / 'pdf_report' / "*.pdf"))
                if len(pdfs) > 0:
                    status = 4

        return status

    def __len__(self) -> int:
        return len(self.runs)

    def __getitem__(self, item: Union[int, str]) -> ValidationRun:
        """ Can be used to select one of the loaded validation runs """
        names = list(self.runs.keys())
        if isinstance(item, int):
            return self.runs[names[item]]
        elif isinstance(item, str):
            if item not in names:
                raise KeyError(f"The run '{item}' is not part of "
                               f"the report. "
                               f"Use one of {list(self.runs.keys())}")
            return self.runs[item]
        else:
            raise ValueError(f"Pass either run index or a "
                             f"name from {list(self.runs.keys())}.")

    def __repr__(self):
        s = ''
        i = 0
        for n, r in self.runs.items():
            s += f"{i} [{r.status[0]}]: {n}\n"
            i += 1
        s += f"<AutoReportCreator <--> {self.report_root}>"
        return s

    @staticmethod
    def _warn_incomplete():
        warnings.warn("Skipping content collection as some runs are "
                      "incomplete.")

    def open_datasets(self) -> dict:
        datasets = {}
        for name, run in self.runs.items():
            datasets[name] = run.open_dataset()
        return datasets

    def validation_run_table(self, short_url=True):
        """
        Create a table in .csv format that lists all validation runs for this
        report.

        Validation run; URL; Reference; Completed
        \#1; https://test.qa4sm.eu/ui/validation-result/e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e; ERA5-Land; December 2, 2025

        Parameters
        ----------
        short_url: bool, optional
            URL as link, not full URL

        Returns
        -------
        df: pd.DataFrame
            A table containing the validation runs
        """
        columns = ["Validation run", "URL", "Name", "Completed"]
        records = []
        for i, run in enumerate(list(self.runs.values()), start=1):
            run.has_remote(raise_error=True)
            url = run.get_results_url()
            ds, vers, _ = run.get_reference('spatial')
            time = run.timing()
            ref = f"{ds} ({vers})"
            name = "\\texttt{" + run.name + "}"

            if short_url:
                url = "\\href{"+url+"}{"+run.remote_id+"}"
            else:
                url = "\\url{"+url+"}"

            if time['end'] is None:
                enddate = "not finished"
            else:
                enddate = time['end'].strftime('%Y-%m-%d %H:%M')

            records.append([f"\\#{i}", url, name, enddate])

        df = pd.DataFrame.from_records(records, columns=columns)

        return df

    def rollback(self, status=0):
        """
        Roll back the report to the selected stage.

        Parameters
        ----------
        status: int
            Target status after rollback.
        """
        raise NotImplementedError()

    def override_params(self, **kwargs):
        """
        Override parameters in all runs loaded for this report.

        Parameters
        ----------
        kwargs:
            Kwargs are passed to each run's override_params method.
        """
        for name, run in self.runs.items():
            run.override_params(**kwargs)

    def verify_dataset_availability(self) -> bool:
        """
        Verify for each run that that datasets cover the required period.

        Returns
        -------
        avail: bool
            True if all datasets are available for the requested period,
            False otherwise.
        """
        for name, run in self.runs.items():
            avail = run.verify_period()
            if not avail:
                return False

        return True

    def start_all_runs(self, delay=1, override=None):
        """
        Trigger all validation runs with the run configurations currently
        loaded in here (self.runs).
        Use self.runs[i].start() to trigger them individually.

        Parameters
        ----------
        delay: int, optional (default: 1)
            Delay in seconds between API calls to start a run.
        override: dict, optional (default: None)
            To override certain settings in all validation runs before
            starting them, pass them here.
            e.g., {'interval_from': "2023-01-01", 'interval_to': "2023-03-31",
                   'min_lat': -17.0, 'max_lon': 150.0, ...}
        """
        for name, run in self.runs.items():  # type: ValidationRun
            if override is not None:
                run.override_params(**override)
            run.start()
            time.sleep(delay)

    def validations_complete(self) -> bool:
        """
        Check whether all remote runs have already completed.

        Returns
        -------
        all_done : bool
            False if at least one run is not complete yet, else True
        """
        for name, run in self.runs.items():
            run.has_remote(raise_error=True)
            s, p = run.status
            if not ((s == "DONE") and (p == 100)):
                return False

        return True

    def download_all_results(self, delay=1):
        """
        Download all results from the server for all runs.

        Parameters
        ----------
        delay: int, optional (default: 1)
            Delay in seconds between API calls to start a run.
        """
        if self.validations_complete():
            for name, run in self.runs.items():
                run.download_data()
                time.sleep(delay)
        else:
            self._warn_incomplete()

    def delete(self, remote=True):
        """
        Delete all runs in this report.

        Parameters
        ----------
        local: bool, optional
            Delete the remote version of the run
        remote: bool, optional
            Delete the local copy of the validation run
        """
        for name, run in self.runs.items():
            run.delete(remote=remote, local=True)
        if os.path.exists(self.report_root):
            shutil.rmtree(self.report_root)

    def collect_content(self, force_download=False):
        """
        Collect all content variables for a given run. Write to single file.

        Parameters
        ----------
        force_download: bool, optional (default: False)
            Always download new results. If this is False, only download
            results if the don't yet exist.
        """
        if self.validations_complete():

            table = self.validation_run_table()
            table.to_csv(self.report_root / "val_run_list.csv",
                         sep=';', index=False)

            for i, run in enumerate(list(self.runs.values()), start=1):
                # Download all required data from server
                run.download_data(force_download=force_download)
                # Make the coverage map plot
                run.plot_extent()

                # Collect various variables
                all_vars = RunData(run)
                all_vars.data['report_run_index'] = i
                all_vars.data['remote_id'] = run.remote_id

                config_data = ConfigData(run).collect()
                all_vars.append(config_data)

                nc_metadata = NetcdfMetaData(run).collect()
                all_vars.append(nc_metadata)

                nc_data = NetcdfData(run).collect()
                all_vars.append(nc_data)

                service_data = RemoteData(run).collect()
                all_vars.append(service_data)

                sum_data = SummaryStatsData(run).collect()
                os.makedirs(os.path.join(run.local_root, 'latex'), exist_ok=True)
                sum_data.export_table(
                    os.path.join(run.local_root, 'latex', 'summary_stats.csv'))
                all_vars.append(sum_data)

                all_vars.dump(os.path.join(run.local_root, 'ContentVars.yml'),
                              overwrite=True)


            extents = [r.extent for _, r in self.runs.items()]
            if len(extents) == 1:
                common_extent = extents[0]
            else:
                common_extent = GeographicExtent.multi_intersection(*extents)

            fig = common_extent.plot_map(global_map=True)
            fig.savefig(self.report_root / "common_extent.png", bbox_inches='tight')

            def all_equal(*extents, tolerance=0.0):
                return all(extents[0].equals(e, tolerance) for e in extents[1:])
            extents_equal = all_equal(*extents)
            # ----------------------------------
            # Common, non-run-specific variables
            report_data = {
                'compilation_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'qa4sm_version': all_vars.data["NetcdfMetaVars"]["qa4sm_version"],
                'qa4sm_url': list(self.runs.values())[-1].connection.session.base_url,
                'interval_days': all_vars.data["ConfigVars"]["interval_days"],
                'interval_from': all_vars.data["ConfigVars"]["interval_from"],
                'interval_to': all_vars.data["ConfigVars"]["interval_to"],
                'count_runs': len(self.runs),
                'extents_equal': extents_equal,
                'common_area': [common_extent.min_lat, common_extent.min_lon,
                                common_extent.max_lat, common_extent.max_lon]
            }
            common_data = Data()
            common_data.add(report_data, section='Common')
            common_data.dump(os.path.join(self.report_root, 'ReportVars.yml'),
                             overwrite=True)
        else:
            self._warn_incomplete()

    @staticmethod
    def _fix_apostrophe_keys(expr: str) -> str:
        """
        Rewrite dict subscripts whose key contains an apostrophe from single-quoted
        to double-quoted so eval() can parse them: ['PEARSON'S R'] -> ["PEARSON'S R"]

        A character scan is needed because the apostrophe inside the key would
        confuse any regex-based approach.
        """
        out, i = [], 0
        while i < len(expr):
            if expr[i] == '[' and i + 1 < len(expr) and expr[i + 1] == "'":
                j = i + 2
                while j < len(expr):
                    if expr[j] == "'" and j + 1 < len(expr) and expr[j + 1] == ']':
                        key = expr[i + 2: j]
                        delim = '"' if "'" in key else "'"
                        out.append(f"[{delim}{key}{delim}]")
                        i = j + 2
                        break
                    j += 1
                else:
                    out.append(expr[i])
                    i += 1
            else:
                out.append(expr[i])
                i += 1
        return "".join(out)

    def _replacer(self, context: dict,
                  FMT_RE=re.compile(r"^(.*):([0-9+\- #]*\.?[0-9]*[bcdeEfFgGnosxX%])$")):
        def replace(m: re.Match) -> str:
            expr = self._fix_apostrophe_keys(m.group(1))
            fmt = FMT_RE.match(expr)
            return format(eval(fmt.group(1), {"__builtins__": {}}, context), fmt.group(2)) \
                if fmt else str(eval(expr, {"__builtins__": {}}, context))

        return replace

    def populate_latex(
            self,
            template_file: str or Path,
            out_file: str or Path,
            yaml_bindings: dict,
            placeholder=re.compile(r"(?:\\detokenize\{)?\$<(.+?)>\$(?:\})?"),
        ) -> None:
        """
        Populate run latex file with run data.

        Parameters
        ----------
        template_file : str or Path
            Path to the run latex template
        out_file: str or Path, optional
            Path where the variables are stored (yaml bindings) and where the
            output is written to.
        yaml_bindings: dict
            Specify the yaml bindings, if None is passed we use the default
            bindings from the run and report root.
        placeholder: re.Pattern, optional
            Placeholder pattern to replace in the tex files.
            the default looks like r`\detokenize{$<...>$}` and contains python
            f-strings.
        """
        context = {name: yaml.safe_load(Path(path).read_text())
                   for name, path in yaml_bindings.items()}
        context["np"] = np
        context["utils"] = utils
        replacer = self._replacer(context)
        tex = Path(template_file).read_text(encoding="utf-8")
        tex = placeholder.sub(replacer, tex)
        Path(out_file).write_text(tex, encoding="utf-8")

    def compile(self, template_path,
                main_tex="main.tex",
                run_tex='run.tex',
                tex_ignore=None,
                from_scratch=False):
        """
        Collect contents to compile PDF report from templates.

        Parameters
        ----------
        template_path: str or Path
            Path where the templates latex files are stored.
        main_tex: str, optional
            Main tex file
        run_tex: str, optional
            Tex file template to use for runs (have separate yml bindings).
        tex_ignore: list, optional
            A list of tex files in the template path to ignore
        from_scratch: bool, optional
            Download and collect data, even if it already exists.
        """
        tex_ignore = tex_ignore or []

        self.collect_content(from_scratch)  # todo: include!
        template_path = Path(template_path)

        for file in os.listdir(template_path):
            if file.endswith(".tex"):
                continue
            full_path = os.path.join(template_path, file)
            if os.path.isfile(full_path):
                shutil.copy2(full_path, self.report_root)

        yaml_bindings = {
            "ReportVars": self.report_root / "ReportVars.yml"
        }

        for i, run in enumerate(list(self.runs.values()), start=1):
            yaml_bindings[f"Run{i}ContentVars"] = run.local_root / "ContentVars.yml"

        for f in glob.glob(str(template_path / "*.tex")):
            name = os.path.basename(f)
            if (name == run_tex) or (name in tex_ignore):
                continue
            #out_name = name.replace('template_', '')
            self.populate_latex(f,
                                self.report_root / name,
                                yaml_bindings)

        for i, run in enumerate(list(self.runs.values()), start=1):
            yaml_bindings["ContentVars"] = run.local_root / "ContentVars.yml"
            #print(run.local_root)
            self.populate_latex(template_path / run_tex,
                                run.local_root / run_tex,
                                yaml_bindings)

        os.makedirs(str(self.report_root / "pdf_report"), exist_ok=True)

        try:
            for i in range(4):
                try:
                    ret = subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode", main_tex],
                        capture_output=True, text=True, check=True,
                        cwd=str(self.report_root), timeout=100
                    )
                except subprocess.TimeoutExpired as e:
                    raise RuntimeError(
                        f"pdflatex timed out on run {i + 1} — likely caused by interactive error prompts. "
                        f"Check the .log file for lines starting with '!'"
                    ) from e

                if "! " in ret.stdout:
                    errors = [line for line in ret.stdout.splitlines() if line.startswith("! ")]
                    raise RuntimeError(
                        f"pdflatex failed on run {i + 1} with errors:\n" + "\n".join(errors)
                    )

                if i == 0:
                    try:
                        subprocess.run(
                            ["bibtex", main_tex.replace('.tex', '')],
                            capture_output=True, text=True, check=True,
                            cwd=str(self.report_root), timeout=100
                        )
                    except subprocess.TimeoutExpired as e:
                        raise RuntimeError(
                            f"bibtex timed out — likely caused by interactive error prompts."
                        ) from e

            if ret.returncode != 0:
                logging.info("bibtex stdout: %s", ret.stdout)
                print("STDOUT:", ret.stdout)
                print("STDERR:", ret.stderr)
        finally:
            # Move the output files to pdf_report (always runs, even on failure)
            pdf_out_dir = self.report_root / "pdf_report"
            os.makedirs(str(pdf_out_dir), exist_ok=True)
            for ext in ['pdf', 'log', 'aux', 'out', 'tex', 'bib', 'bbl', 'blg']:
                src = glob.glob(str(self.report_root / f"*.{ext}"))
                for f in src:
                    if os.path.exists(f):
                        shutil.move(str(f), str(pdf_out_dir / os.path.basename(f)))


if __name__ == '__main__':
    QA4SM_IP_OR_URL = "test.qa4sm.eu"
    QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"

    qa4sm = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)

    template_path = "/qa4sm_autoreports/pipelines/configs/smos_l2_v700"
    creator = AutoReportCreator.from_scratch(
        "/data-read/USERS/wpreimes/qa4sm_smos_report/20220701_20220930",
                  template_path, connection=qa4sm
    )

    # creator.start_all_runs(override={'interval_from': '2020-01-01',
    #                                  'interval_to': '2020-01-31'})

    creator.validations_complete()
    creator.collect_content()
    creator.validation_run_table()







    series_root = Path("/data-read/USERS/wpreimes/qa4sm_smos_report/20220701_20220930")

    name1 = "01-SmosL2-vs-C3sComb-abs"
    id1 = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"
    path1 = series_root / "01-SmosL2-vs-C3sComb-abs"

    name2 = "02-SmosL2-vs-Era5Land-abs"
    id2 = "e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e"
    path2 = series_root / "02-SmosL2-vs-Era5Land-abs"

    run1 = ValidationRun.from_remote(path1, connection=qa4sm,
                remote_id="6eb61199-59b8-4ecc-8e3c-7b1139df4a05")

    run2 = ValidationRun.from_remote(path2, connection=qa4sm,
                remote_id="e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e")

    report = AutoReportCreator([run1, run2], series_root)

    report.compile(
        "/home/wpreimes/shares/home/code/qa4sm-autoreports/src/qa4sm_autoreports/pipelines/configs/smos_l2_v700/latex_template/src",
    )

    # run = ValidationRun(config, connection=qa4sm, root_local="/tmp/test_run",
    #                     name='mytestrun') src/qa4sm_autoreports/pipelines/configs/smos_l2_v700/latex_template/src
    # assert run.verify_period(), "Data is not available"
    # run.start()
