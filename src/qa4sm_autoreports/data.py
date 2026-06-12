# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright (c) 2026 TU Wien & AWST
# SPDX-FileCopyrightText: For a full list of authors, see the AUTHORS file.

import glob
import os
import pandas as pd
import yaml
from typing import Union
import xarray as xr
from pathlib import Path

from qa4sm_autoreports.run import (
    ValidationRun, ValidationConfiguration
)

"""
Containers for various types of data from QA4SM (e.g. stats, results, config,
...). Each container comes with a function to collect the required data.
"""

def load_yml_to_dict(filepath: str | Path) -> dict:
    """
    Load a QA4SM-style YAML config/results file into a nested dictionary.

    Parameters
    ----------
    filepath: str or Path
        Path to the yml content

    Returns:
    -------
    data: dict
        The first level are the content sections names, sub-levels are the
        variables in that section.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"No file found at: {filepath}")
    if filepath.suffix not in (".yml", ".yaml"):
        raise ValueError(f"Expected a .yml/.yaml file, got: {filepath.suffix}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("YAML content did not parse to a dictionary.")

    return data


class Data:
    """
    Data container base class for variables from various sources
    """
    def __init__(self, data=None):
        if data is None:
            self.data = self._reset()
        else:
            self.data = data

    def _reset(self):
        # Empty data dict
        self.data = dict()
        return self.data

    @classmethod
    def from_yml(cls, path: Union[Path, str]):
        """
        Load data from a previous stored yml file

        Parameters
        ----------
        path: str or Path
            Path to the yml file to load content from
        """
        data = load_yml_to_dict(path)
        return cls(data=data)

    def load(self, path, mode='r'):
        """
        Load data from the passed yml file into this Data
        container.

        Parameters
        ----------
        path: str
            Path to the yml file to take content from
        mode: str, optional
            'r': Read mode will drop any already loaded content
            'a' Append mode will add content from the to anything loaded
        """
        data = load_yml_to_dict(path)
        if mode == 'a':
            self.data.update(data)
        elif mode == 'r':
            self.data = data

    def append(self, other):
        """ Add data from other variable """
        self.data.update(other.data)

    def add(self, content: dict, section: str = "Content"):
        """
        Add content to the collection.

        Parameters
        ----------
        content: dict
            Yaml storable content, usually {KEY: Value, ...}
        section: str
            Multiple contents can be stored, specify name of content
            group (e.g. summary statistics).
            Each name will be a separate yml section upon export.
        """
        self.data[section] = content

    def dump(self, path: Union[Path, str], overwrite: bool = False):
        """
        Write content to yml to import later for the report.

        Parameters
        ----------
        path: str
            File path to write data to
        overwrite: bool, optional
            Overwrite will replace an existing file, otherwise will append
            to it.
        """
        path = Path(path)
        os.makedirs(path.parent, exist_ok=True)

        if os.path.exists(path) and (not overwrite):
            mode = 'a'
        else:
            mode = 'w'

        with open(str(path), mode) as f:
            yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)


class RunData(Data):
    """
    Collection of data from multiple validation runs for a report
    """
    def __init__(self, validation_run: ValidationRun):
        self.run = validation_run
        super(RunData, self).__init__()


class RemoteData(RunData):
    """
    Collect variables from service API sources
    """
    def __init__(self, validation_run: ValidationRun):
        super().__init__(validation_run)

    def collect(self):
        """
        Collect Configuration Variables from all datasets in this validation
        run.

        Returns:
        --------
        run_vars: dict
            Collection of config variables from this run
        """

        status, progress = self.run.status
        time = self.run.timing()

        start = str(time['start']) or None
        end = str(time['end']) or None

        run_vars = {
            'run_status': status,
            'run_progress': progress,
            'run_duration': time['duration'],
            'run_start': start,
            'run_end': end
        }

        self.add(run_vars, "RemoteVars")

        return self


class SummaryStatsData(RunData):
    """
    Collect variables from the csv summary stats file of the validation run
    """
    def __init__(self, validation_run: ValidationRun):
        self.unit_sep = "  in"
        super().__init__(validation_run)

    def _load_sum_stats(self, drop_unit=False) -> pd.DataFrame:
        df = pd.read_csv(self.run.local_root / 'summary_stats.csv',
                         index_col=0)
        # get rid of unit from table:
        if drop_unit:
            new_index = [i.split(self.unit_sep)[0].strip()
                         for i in df.index.values]
            df.index = new_index

        df.index = [i.strip() for i in df.index]

        if "Dataset" in df.columns:
            df = df.drop(columns="Dataset")
        if "Spearman's ρ" in df.index:
            df = df.rename(index={"Spearman's ρ": "Spearman's rho"})
        if "# observations" in df.index:
            df = df.rename(index={"# observations": "N. Obs."})

        return df

    def export_table(self, path=None):
        """
        Export the data to a csv table that is used in the latex report

        Parameters
        ----------
        path: str
            Path to csv file
        """
        df = self._load_sum_stats()
        df.to_csv(path, sep=';', index_label='Metric')

    def collect(self):
        """
        Collect all relevant stats from the downloaded summary table
        """
        df = self._load_sum_stats(drop_unit=True)

        params = {}

        for i in df.index.values:
            for c in df.columns.values:
                if self.unit_sep in i:
                    i = i.split(self.unit_sep)[0]
                val = df.loc[i, c]
                params[f"{c.upper()}_{i.upper()}"] = float(val)

        self.add(params, "SummaryVars")

        return self


class NetcdfData(RunData):
    """
    Collect variables from the results netcdf file
    """
    def __init__(self, validation_run: ValidationRun):
        super().__init__(validation_run)

    def stats(self):
        pass

    def collect_content(self) -> dict:
        ds = xr.open_dataset(self.run.local_root / f"{self.run.remote_id}.nc")
        n_gpis = len(ds["gpi"].values)
        status_code_ok = 0
        n_status_points = []
        n_status_ok = []
        for var in list(ds.variables.keys()):
            if var.startswith("status_"):
                n_status_points.append(int(len(ds[var].values.flatten())))
                n_status_ok.append(int(len(ds[var].values[ds[var].values.flatten()
                                           == status_code_ok])))

        data = {
            'n_gpis': int(n_gpis),
            'n_status': n_status_points,
            'percent_ok': [int((o / s) * 100) for o, s in zip(n_status_ok, n_status_points)]
        }

        return data

    def collect(self):
        nc_attrs = self.collect_content()
        self.add(nc_attrs, "NetcdfVars")
        return self


class NetcdfMetaData(RunData):
    """
    Collect meta variables from the results netcdf file
    """
    def __init__(self, validation_run: ValidationRun):
        super().__init__(validation_run)

    def collect_metadata_content(self) -> dict[str, str]:
        ds = xr.open_dataset(self.run.local_root / f"{self.run.remote_id}.nc")
        attrs = {}
        for k, v in ds.attrs.items():
            attrs[k] = str(v)
        return attrs

    def collect(self):
        nc_attrs = self.collect_metadata_content()
        self.add(nc_attrs, "NetcdfMetaVars")
        return self


class ConfigData(RunData):
    """
    Collect variables from the validation run config
    """
    def __init__(self, validation_run: ValidationRun):
        super().__init__(validation_run)
        c = glob.glob(os.path.join(self.run.local_root, f"config-*.json"))[0]
        self.config_path = c
        self.conf = ValidationConfiguration.from_file(self.config_path)

    def collect_datasets(self, i=0):
        """
        Collect the Variables from a dataset configuration

        Parameters
        ----------
        i: int, optional
            Id of the dataset to read from the config
        """
        dataset_config = self.conf['dataset_configs'][i].copy()

        id = dataset_config['dataset_id']
        dataset_config[f'name'] = (
            self.run.connection.dataset_info(id))['pretty_name']
        id = dataset_config['version_id']
        dataset_config[f'version'] = (
            self.run.connection.version_info(id))['pretty_name']
        id = dataset_config['variable_id']
        dataset_config[f'variable'] = (
            self.run.connection.variable_info(id))['pretty_name']

        active_filters = []
        filters = dataset_config['basic_filters']
        for filter in filters:
            finf = self.run.connection.filter_info(filter)
            active_filters.append({
                'description': finf['description'],
                'help_text': finf['help_text']
            })
        dataset_config['basic_filters_description'] = active_filters

        # todo: How do param filters work?
        active_filters = []
        filters = dataset_config['parametrised_filters']
        for filter in filters:
            filter_id = filter['id']
            finf = self.run.connection.filter_info(filter_id)
            active_filters.append({
                'description': finf['description'],
                'help_text': finf['help_text'],
                'parameters': filter['parameters']
            })
        dataset_config['parametrised_filters_description'] = active_filters

        return dataset_config

    def collect(self):
        """
        Collect Configuration Variables from all datasets in this validation
        run.

        Returns:
        --------
        run_vars: dict
            Collection of config variables from this run
        """
        run_vars = {
            'scaling_reference': None,
            'spatial_reference': None,
            'temporal_reference': None,
            'tcol_metrics': None,
            'stability_metrics': None,
            'interval_days': None,
        }

        for id in range(len(self.conf['dataset_configs'])):
            ds_vars = self.collect_datasets(id)
            if bool(ds_vars['is_spatial_reference']):
                run_vars['spatial_reference'] = \
                    f"{ds_vars['name']} ({ds_vars['version']})"

            if bool(ds_vars['is_temporal_reference']):
                run_vars['temporal_reference'] = \
                    f"{ds_vars['name']} ({ds_vars['version']})"

            if bool(ds_vars['is_scaling_reference']):
                run_vars['scaling_reference'] = \
                    f"{ds_vars['name']} ({ds_vars['version']})"

            run_vars[f'DS{id}'] = ds_vars

        _d = self.conf.data.copy()
        for m in _d['metrics']:
            if m['id'] == 'tcol':
                run_vars["tcol_metrics"] = m['value']
            if m['id'] == 'stability_metrics':
                run_vars["stability_metrics"] = m['value']

        interval_days = (pd.to_datetime(_d['interval_to']) -
                         pd.to_datetime(_d['interval_from'])).days
        run_vars["interval_days"] = interval_days

        _ = _d.pop("dataset_configs")
        run_vars.update(_d)
        self.add(run_vars, "ConfigVars")

        return self

