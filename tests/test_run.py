import os.path
import unittest
import shutil
from datetime import datetime
from qa4sm_api.client_api import Connection
from qa4sm_autoreports.run import ValidationRun
from tempfile import mkdtemp

QA4SM_IP_OR_URL = "test.qa4sm.eu"
QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"
RUN_ID = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"
QA4SM = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)


class TestRunFromRemote(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tempdir = mkdtemp()
        cls.valrun = ValidationRun.from_remote(cls.tempdir, QA4SM, RUN_ID)
        cls.valrun.download_data()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_is_local_run(self):
        assert self.valrun._init_origin == 'remote'

    def test_setup_from_local(self):
        local_ins = ValidationRun.from_results(self.tempdir, QA4SM)
        assert local_ins == self.valrun

    def test_url(self):
        assert self.valrun.url == f"https://test.qa4sm.eu/api/validation-configuration/{RUN_ID}"

    def test_get_reference(self):
        ds_s, vers_s, var_s = self.valrun.get_reference('spatial')
        ds_t, vers_t, var_t = self.valrun.get_reference('temporal')
        assert ds_s == ds_t == 'SMOS Level 2'
        assert vers_s == vers_t == 'v700'
        ds, vers, var = self.valrun.get_reference('scaling')
        assert ds == vers == var
        assert ds is None

    def test_load_results(self):
        res = self.valrun.load_results()
        assert len(res.dims) == 2

    def test_update_name(self):
        _ = self.valrun.update_name('new name')
        assert self.valrun.name == 'new name'

    def test_verify_period(self):
        assert self.valrun.verify_period()

    def test_plot_extent(self):
        self.valrun.plot_extent()
        assert os.path.exists(self.valrun.local_root / "extent.png")

    def test_override_params(self):
        self.valrun.override_params(name_tag='override name')
        assert self.valrun.config['name_tag'] == 'override name'

    def test_timing(self):
        timing = self.valrun.timing()
        assert timing['start'] < timing['end']
        assert isinstance(timing['start'], datetime)
        assert isinstance(timing['end'], datetime)
        assert isinstance(timing['duration'], str)

    def test_status(self):
        status, percent = self.valrun.status()
        assert (status.upper() == 'DONE') & (percent == 100)


class TestRunFromLocal(TestRunFromRemote):

    @classmethod
    def setUpClass(cls):
        cls.tempdir = mkdtemp()
        valrun = ValidationRun.from_remote(cls.tempdir, QA4SM, RUN_ID)
        valrun.download_data()
        localrun = ValidationRun.from_results(cls.tempdir, QA4SM)
        cls.valrun = localrun

    def test_is_local_run(self):
        assert self.valrun._init_origin == 'local'


