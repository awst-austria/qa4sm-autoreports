# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright (c) 2026 TU Wien & AWST
# SPDX-FileCopyrightText: For a full list of authors, see the AUTHORS file.

import glob
import pandas as pd
import requests.exceptions
from typing import Tuple, Union
import shutil
import os
from pathlib import Path
import xarray as xr

from qa4sm_api.client_api import Connection, ValidationConfiguration
from qa4sm_autoreports.extent import GeographicExtent


class ValidationRun:
    def __init__(
            self,
            config: ValidationConfiguration,
            root_local: Union[str, Path],
            connection: Connection,
            remote_id=None,
            name_tag=None,
    ):
        """
        Parameters
        ----------
        config: ValidationConfiguration
            Configuration for validation run to trigger (settings)
        root_local: Union[str, Path]
            Local root folder, a subfolder for the validation run is created
        connection: Connection
            Connection to the QA4SM instance to run the validation on
        remote_id: str, optional
            Remote ID if the run already exists online
        name_tag: str, optional
            Name tag for the run. If None is passed, we use the tag from the
            config file.
        """
        self.config = config
        self.local_root = Path(root_local)
        self.connection = connection
        self.remote_id = remote_id
        self.name = self.update_name(name_tag or self.config['name_tag'])

    def __repr__(self):
        return (
            f"ValidationRun [{self.status[0]}]\n"
            f"  - name:       {self.name}\n"
            f"  - remote_id:  {self.remote_id}\n"
            f"  - local_root: {self.local_root}\n"
            f"  - connection: {self.connection}\n"
        )

    @classmethod
    def from_remote(cls, local_root: Union[str, Path], connection: Connection,
                    remote_id: str):
        """
        Set up ValidationRun based on a remote validation run with a local
        folder for synchronization.

        Parameters
        ----------
        local_root: str
            Local folder where the run data is stored
        connection: Connection
            Service connection for your user
        remote_id: str
            Name of the remote run (UID).

        Returns
        -------
        run : ValidationRun
        """
        local_root = Path(local_root)
        url = connection.url(f"validation-configuration/{remote_id}")
        response = connection.session.get(url)
        config = ValidationConfiguration(response.data[0])
        cls._init_origin = 'remote'

        return cls(config, local_root, connection, remote_id)

    @classmethod
    def from_template(cls, local_dir: Union[str, Path],
                      connection: Connection, name_tag=None):
        """
        Set up ValidationRun based on a previously synchronized, now local, run.

        Parameters
        ----------
        local_dir: Union[str, Path]
            Local run folder containing at least the config.json or some
            previously downloaded results.
        connection: Connection
            Connection to QA4SM instance to which the validation run should be
            assigned.
        name_tag: str, optional
            Name to assign to the new run. If None is passed, the name
            of the local_dir is used.

        Returns
        -------
        run : ValidationRun
        """
        local_dir = Path(local_dir)
        conf_file = glob.glob(str(local_dir / "config-*.json"))
        assert len(conf_file) == 1, \
            f"Found multiple config files in {local_dir}"
        conf_file = conf_file[0]

        config = ValidationConfiguration.from_file(conf_file)

        name_tag = name_tag or os.path.dirname(local_dir)

        return cls(config, root_local=local_dir,
                   connection=connection, remote_id=None,
                   name_tag=name_tag)

    @classmethod
    def from_results(cls, local_dir: Union[str, Path],
                     connection: Connection = None, name_tag=None):
        """
        Set up ValidationRun based on a previously synchronized, now local, run.
        Uses: run_id, instance url from response/results files to restore a
        connection.

        Parameters
        ----------
        local_dir: Union[str, Path]
            Local run folder containing at least the config.json or some
            previously downloaded results.
        connection: Connection, optional
            Connection to use for the run. If None, a new connection will be
            created based on the instance in the config file.
        name_tag: str, optional
            Name to assign to the new run. If None is passed, the name
            of the local_dir is used.

        Returns
        -------
        run : ValidationRun
        """
        local_dir = Path(local_dir)
        conf_file = glob.glob(str(local_dir / "config-*.json"))
        assert len(conf_file) == 1, \
            f"No unique config file found in {local_dir}"
        conf_file = conf_file[0]

        instance = os.path.basename(conf_file).split('-')[1].replace('.json', '')

        config = ValidationConfiguration.from_file(conf_file)

        results_files = glob.glob(str(local_dir / "*.nc"))
        response_file = glob.glob(str(local_dir / "response-*.csv"))
        remote_id = None
        if connection is None:
            connection = Connection(instance)

        if len(results_files) > 0:
            assert len(results_files) == 1, \
                f"Found multiple results netcdf files in {local_dir}"
            remote_id = os.path.basename(results_files[0]).split('.nc')[0]
        if len(response_file) > 0:
            assert len(response_file) == 1, \
                f"Found multiple response csv files in {local_dir}"
            response_file = response_file[0]
            response = pd.read_csv(response_file, index_col=0).squeeze()
            remote_id = remote_id or response['pk']
            if connection is None:
                connection = Connection(response['instance'])

        name_tag = name_tag or os.path.dirname(local_dir)

        return cls(config, root_local=local_dir,
                   connection=connection, remote_id=remote_id,
                   name_tag=name_tag)

    def __eq__(self, other) -> bool:
        return self.remote_id == other.remote_id

    @property
    def extent(self) -> (float, float, float, float):
        # y_min, x_min, y_max, x_max
        d = self.config.data
        extent = GeographicExtent.from_corners(d['min_lat'], d['min_lon'],
                                               d['max_lat'], d['max_lon'])
        return extent

    @property
    def instance(self) -> str:
        if self.remote_id is None:
            return None
        else:
            return self.connection.session.instance

    @property
    def url(self):
        """Get the API URL of the validation run."""
        if self.remote_id is None:
            return None
        else:
            return self.connection.url(f"validation-configuration/{self.remote_id}")

    @property
    def status(self) -> Tuple[str, int]:
        """
        Check the status of the remote run.

        Returns
        -------
        status[str], progress[int]
            see :func:`Connection.validation_status`
        """
        try:
            s = self.connection.validation_status(self.remote_id)
        except requests.exceptions.HTTPError:
            s = ("unknown", 0)
        return s

    def open_dataset(self) -> xr.Dataset:
        """
        Read local netcdf data as xarray Dataset
        """
        ncpath = self.local_root / f"{self.remote_id}.nc"
        return xr.open_dataset(ncpath)

    def has_remote(self, raise_error: bool = False):
        """ Check if the validation run has a remote counter part """
        s = self.remote_id is not None
        if not s and raise_error:
            raise ValueError("Validation run has no remote counter part")
        return s

    def get_results_url(self):
        """Get the UI URL of the validation run."""
        if self.remote_id is None:
            return None
        else:
            url = self.connection.url(f"validation-result/{self.remote_id}")
            return url.replace('api', 'ui')

    def get_reference(self, reftype='spatial'):
        """
        Get reference dataset for this run.

        Parameters
        ----------
        reftype: Literal['spatial', 'temporal', 'scaling']
            What scaling reference to get

        Returns
        -------
        dataset: str
            Dataset name
        version: str
            Version name
        variable: str
            Variable name
        """
        for conf in self.config.data["dataset_configs"]:
            if conf[f'is_{reftype}_reference']:
                dataset = int(conf['dataset_id'])
                version = int(conf['version_id'])
                variable = int(conf['variable_id'])
                dataset = self.connection.dataset_info(dataset)['pretty_name']
                version = self.connection.version_info(version)['pretty_name']
                variable = self.connection.variable_info(variable)['pretty_name']
                return str(dataset), str(version), str(variable)

        return None, None, None

    def load_results(self) -> xr.Dataset:
        """
        Load downloaded results as xarray.
        """
        ds = xr.open_dataset(self.local_root / f'{self.remote_id}.nc')
        return ds

    def update_remote_id(self, pk):
        if self.response is not None:
            self.remote_id = pk
            return self.remote_id

    def update_name(self, new_name: str):
        self.config['name_tag'] = new_name
        self.name = self.config['name_tag']
        return self.name

    def setup_workdir(self, clear=False):
        if self.local_root.exists() and clear:
            shutil.rmtree(self.local_root)
        os.makedirs(self.local_root, exist_ok=True)

    def override_params(self, **kwargs):
        """
        Override certain parameters in the validation config file. Such as
        name_tag and start/end date etc.

        Parameters
        ----------
        kwargs:
            Keys and new values. Keys must already exist in the config. You
            cannot add anything new, only change existing fields!
        """
        for k, v in kwargs.items():
            self.config[k] = v

    def verify_period(self):
        """
        Checks if the chosen validation period is within the range available
        for all datasets on the service.

        Returns
        -------
        status: bool
            True if all datasets are available, False otherwise
        """
        period_start = pd.to_datetime(self.config['interval_from'])
        period_end = pd.to_datetime(self.config['interval_to'])

        for ds_config in self.config['dataset_configs']:
            avail_start, avail_end = self.connection.get_period(
                ds_config['version_id'])
            avail_start = pd.to_datetime(avail_start)
            avail_end = pd.to_datetime(avail_end)

            if (period_start < avail_start) or (period_end > avail_end):
                return False

        return True

    def start(self):
        """
        Start the current Validation Run on the chosen instance. Creates
        a local folder and dumps the config and the response from the server
        there.

        Returns
        -------
        response: dict
            Response from validation run
        """
        self.setup_workdir(clear=True)
        self.response = self.connection.run_validation(self.config)
        run_pk = self.response['pk']
        instance = self.connection.session.instance
        self.config.dump(self.local_root / f'config-{instance}.json')
        self.response['instance'] = instance
        self.response.to_csv(self.local_root / f'response-{run_pk}.csv')
        self.update_remote_id(self.response['pk'])
        return self.response

    def timing(self) -> dict:
        """
        Get timing information for the remote validation run

        Returns
        -------
        time: dict
            Time information as a dict
        """
        status, progress = self.status

        time = {'start': None, 'end': None, 'duration': None}

        if status == 'NOT FOUND':
            pass
        else:
            start_time, end_time = (
                self.connection.validation_time(self.remote_id))
            _, duration = self.connection.validation_duration(self.remote_id)
            time['start'] = start_time
            time['end'] = end_time
            time['duration'] = duration

        return time

    def download_data(self, force_download=False):
        """
        Download the run's results, i.e., netcdf file, plots.

        Parameters
        ----------
        force_download: bool, optional
            Always download, replace any existing local files.
            If False, only downloads results that don't exist locally.
        """
        os.makedirs(self.local_root, exist_ok=True)
        self.config.dump(self.local_root /
                         f'config-{self.connection.session.instance}.json')
        self.connection.download_results(self.remote_id, self.local_root,
                                         force_download=force_download)

    def plot_extent(self):
        """
        Create a map plot of the area covered by the validation run.
        """
        os.makedirs(self.local_root, exist_ok=True)
        path = self.local_root
        fig = self.extent.plot_map()
        fig.savefig(path / "extent.png", bbox_inches='tight')

    def delete(self, local=True, remote=True):
        """
        Delete validation run. Online and/or offline.

        Parameters
        ----------
        local: bool, optional
            Delete the remote version of the run
        remote: bool, optional
            Delete the local copy of the validation run
        """
        if local:
            if os.path.exists(self.local_root):
                shutil.rmtree(self.local_root)
        if remote:
            self.connection.delete(self.remote_id)



if __name__ == '__main__':
    QA4SM_IP_OR_URL = "test.qa4sm.eu"
    QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"
    qa4sm = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)
    name1 = "test"
    id1 = "e1b0bc31-9a12-4528-8885-85bad6cfbff6"
    run = ValidationRun.from_remote('/tmp/test', qa4sm, id1)
    run.download_data()
    run.delete(False)

