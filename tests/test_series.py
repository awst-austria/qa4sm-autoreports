import os
import os.path
import unittest
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from tempfile import mkdtemp
import matplotlib
matplotlib.use('Agg')

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.series import AutoReportSeries

RUN_ID = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"
QA4SM = Connection("test.qa4sm.eu")
TEST_PATH = Path(os.path.dirname(os.path.abspath(__file__)))


class TestSeriesExistingLocal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tempdir = mkdtemp()
        with patch('qa4sm_autoreports.run.Connection') as mock_connection:
            mock_conn_instance = Mock()
            mock_connection.return_value = mock_conn_instance
            cls.series = AutoReportSeries(TEST_PATH / 'testdata' / 'test_series')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_inspect_series(self):
        assert self.series.name == "test_series"
        assert len(self.series) == 2
        assert list(self.series.reports.keys())[0] == 'epoch1'

    def test_metric_tracking(self):
        self.series.track_metric(metric='urmsd_between_0-ISMN_and_1-C3S_combined',
                                 unit='m³m⁻³', ref_epoch=-1, n_epochs=10, path_out=Path(self.tempdir))

    def test_track_metrics_ubrmsd_and_r(self):
        out_path = Path(self.tempdir)
        self.series.track_metric(metric='urmsd_between_0-ISMN_and_1-C3S_combined',
                                 unit='m³m⁻³', ref_epoch=-1, n_epochs=10, path_out=out_path)

        self.series.track_metric(metric='R_between_0-ISMN_and_1-C3S_combined',
                                 pretty_name='R', unit='-', ref_epoch=-1, n_epochs=10,
                                 p_mask_var='p_R_between_0-ISMN_and_1-C3S_combined',
                                 path_out=out_path)

        assert os.path.isfile(out_path / "tracking_ubRMSD.png")
        assert os.path.isfile(out_path / "tracking_R.png")
        assert os.path.isfile(out_path / "data_tracking_ubRMSD.yml")
        assert os.path.isfile(out_path / "data_tracking_R.yml")

        for yml_file in ["data_tracking_ubRMSD.yml", "data_tracking_R.yml"]:
            from qa4sm_autoreports.data import Data
            data = Data().from_yml(out_path / yml_file)
            assert 'results' in data.data
            assert 'tracking' in data.data
            assert 'tracking_status' in data.data['results']
            assert data.data['results']['tracking_status'] == 'green'
            assert len(data.data['tracking']) > 0

        from PIL import Image
        for png_file in ["tracking_ubRMSD.png", "tracking_R.png"]:
            img = Image.open(out_path / png_file)
            assert img.size[0] > 0
            assert img.size[1] > 0

    def test_track_metrics_single_entry(self):
        out_path = Path(self.tempdir)
        self.series.track_metric(metric='urmsd_between_0-ISMN_and_1-C3S_combined',
                                 unit='m³m⁻³', ref_epoch=-2, n_epochs=10, path_out=out_path)

        assert os.path.isfile(out_path / "tracking_ubRMSD.png")
        assert os.path.isfile(out_path / "data_tracking_ubRMSD.yml")

        from qa4sm_autoreports.data import Data
        data = Data().from_yml(out_path / "data_tracking_ubRMSD.yml")
        assert 'results' in data.data
        assert 'tracking' in data.data
        assert len(data.data['tracking']) == 1

        from PIL import Image
        img = Image.open(out_path / "tracking_ubRMSD.png")
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_select_epochs(self):
        epochs = ['epoch1', 'epoch2', 'epoch3', 'epoch4', 'epoch5']
        result = AutoReportSeries._select_epochs(epochs, ref_epoch=-1, n_epoch=3)
        assert result == ['epoch3', 'epoch4', 'epoch5']
        result = AutoReportSeries._select_epochs(epochs, ref_epoch=0, n_epoch=2)
        assert result == ['epoch1']
        result = AutoReportSeries._select_epochs(epochs, ref_epoch=-2, n_epoch=4)
        assert result == ['epoch1', 'epoch2', 'epoch3', 'epoch4']


class TestSeriesScratch(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(mkdtemp())
        shutil.copytree(TEST_PATH / "testdata" / "test_series",
                        self.tempdir / "test_series")
        self.series = AutoReportSeries(self.tempdir / "test_series",
                                       connection=QA4SM)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _stage_dummy_report(self):
        template_dir = TEST_PATH / "testdata" / "report_config_templates"
        self.series.new_report('dummy', template_dir)

    def test_new_report(self):
        assert self.series.reports_complete()
        assert len(self.series) == 2
        assert self.series[0].status == 3
        assert self.series[1].status == 3
        self._stage_dummy_report()
        assert len(self.series) == 3
        status = self.series['dummy'].status
        assert status == 0   # staged, not triggered
        assert not self.series.reports_complete()
        assert self.series['dummy']._STATUS_LUT[status].lower() == 'staged'
        assert len(os.listdir(self.series["dummy"].report_root)) == 1
        assert self.series['dummy']["run1"].status[1] == 0

    def test_delete_report(self):
        self._stage_dummy_report()
        assert len(self.series) == 3
        assert os.path.exists(self.series["dummy"].report_root)
        self.series["dummy"].delete(remote=False)  # there is no remote version
        assert not os.path.exists(self.series["dummy"].report_root)


if __name__ == '__main__':
    testcase = TestSeriesScratch()
    testcase.setUpClass()
    testcase.setUp()
    testcase.test_new_report()
    testcase.test_delete_report()
