import os
import os.path
import unittest
import shutil
from pathlib import Path
from tempfile import mkdtemp
from PIL import Image
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use('Agg')

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.series import AutoReportSeries
from qa4sm_autoreports.data import Data

RUN_ID = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"
QA4SM = Connection(os.environ.get('QA4SM_INSTANCE', "test.qa4sm.eu"))
TEST_PATH = Path(os.path.dirname(os.path.abspath(__file__)))


class TestSeriesExistingLocal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tempdir = mkdtemp()
        # with patch('qa4sm_autoreports.run.Connection') as mock_connection:
        #     mock_conn_instance = Mock()
        #     mock_connection.return_value = mock_conn_instance
        cls.series = AutoReportSeries(TEST_PATH / 'testdata' / 'test_series',
                                      connection=None)

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

        assert os.path.isfile(out_path / "tracking_urmsd_between_0-ISMN_and_1-C3S_combined.png")
        assert os.path.isfile(out_path / "tracking_R_between_0-ISMN_and_1-C3S_combined.png")
        assert os.path.isfile(out_path / "tracking_urmsd_between_0-ISMN_and_1-C3S_combined.yml")
        assert os.path.isfile(out_path / "tracking_R_between_0-ISMN_and_1-C3S_combined.yml")

        for yml_file in ["tracking_urmsd_between_0-ISMN_and_1-C3S_combined.yml",
                         "tracking_R_between_0-ISMN_and_1-C3S_combined.yml"]:
            data = Data().from_yml(out_path / yml_file)
            assert 'series' in data.data
            assert 'tracking' in data.data
            assert 'tracking_status' in data.data['tracking']
            # Only one previous report -> not enough history for a status
            assert data.data['tracking']['tracking_status'] == 'none'
            assert data.data['tracking']['n_history'] == 1
            assert data.data['tracking']['previous_report'] == 'epoch1'
            # both epochs contain the same locations -> can be paired
            assert data.data['tracking']['paired_previous']['n_common'] > 0
            assert isinstance(data.data['tracking']['summary'], str)

        for png_file in ["tracking_urmsd_between_0-ISMN_and_1-C3S_combined.png",
                         "tracking_R_between_0-ISMN_and_1-C3S_combined.png"]:
            img = Image.open(out_path / png_file)
            assert img.size[0] > 0
            assert img.size[1] > 0

    def test_track_metrics_single_entry(self):
        out_path = Path(self.tempdir)
        self.series.track_metric(metric='urmsd_between_0-ISMN_and_1-C3S_combined',
                                 unit='m³m⁻³', ref_epoch=-2, n_epochs=10, path_out=out_path)

        assert os.path.isfile(out_path / "tracking_urmsd_between_0-ISMN_and_1-C3S_combined.png")
        assert os.path.isfile(out_path / "tracking_urmsd_between_0-ISMN_and_1-C3S_combined.yml")

        data = Data().from_yml(out_path / "tracking_urmsd_between_0-ISMN_and_1-C3S_combined.yml")
        assert 'series' in data.data
        assert 'tracking' in data.data
        assert data.data['tracking']['tracking_status'] == 'none'
        assert data.data['tracking']['tracking_color'] == 'gray'
        assert data.data['tracking']['n_history'] == 0
        assert data.data['tracking']['previous_report'] is None

        from PIL import Image
        img = Image.open(out_path / "tracking_urmsd_between_0-ISMN_and_1-C3S_combined.png")
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_track_spatial_coverage(self):
        out_path = Path(self.tempdir)
        status = 'status_between_0-ISMN_and_1-C3S_combined'
        self.series.track_spatial_coverage(
            status_vars={'ISMN': status, 'missing': 'status_not_there'},
            ref_epoch=-1, n_epochs=10, path_out=out_path)
        assert os.path.isfile(out_path / "coverage.png")
        assert os.path.isfile(out_path / "stats_coverage.csv")
        data = Data().from_yml(out_path / "coverage.yml")
        cur = data.data['coverage']['datasets']['ISMN']
        # test data: 1 of 25 locations with status 0 (GOOD)
        assert cur['current'] == 1
        assert cur['current_total'] == 25
        assert cur['previous_report'] == 'epoch1'
        assert cur['change'] == cur['current'] - cur['previous']
        # metric that does not exist in any report
        assert data.data['coverage']['datasets']['missing']['current'] is None
        assert isinstance(data.data['coverage']['summary'], str)

    def test_track_spatial_coverage_same_reference(self):
        out_path = Path(self.tempdir)
        status = 'status_between_0-ISMN_and_1-C3S_combined'
        other = 'status_between_0-ISMN_and_2-C3S_active'  # not in test data
        data = self.series.track_spatial_coverage(
            status_vars=[status, other], path_out=out_path)
        cov = data.data['coverage']['datasets']
        assert list(cov.keys()) == ['ISMN vs. C3S combined',
                                    'ISMN vs. C3S active']
        assert cov['ISMN vs. C3S combined']['current'] == 1
        assert cov['ISMN vs. C3S active']['current'] is None

        data = self.series.track_spatial_coverage(
            status_vars=[('ISMN', status), ('ISMN 2', status)],
            path_out=out_path)
        assert len(data.data['coverage']['datasets']) == 2
        with self.assertRaises(ValueError):
            self.series.track_spatial_coverage(
                status_vars=[('ISMN', status), ('ISMN', other)],
                path_out=out_path)

    def test_select_epochs(self):
        epochs = ['epoch1', 'epoch2', 'epoch3', 'epoch4', 'epoch5']
        result = AutoReportSeries._select_epochs(epochs, ref_epoch=-1, n_epoch=3)
        assert result == ['epoch3', 'epoch4', 'epoch5']
        result = AutoReportSeries._select_epochs(epochs, ref_epoch=0, n_epoch=2)
        assert result == ['epoch1']
        result = AutoReportSeries._select_epochs(epochs, ref_epoch=-2, n_epoch=4)
        assert result == ['epoch1', 'epoch2', 'epoch3', 'epoch4']

    def test_label_helpers(self):
        assert AutoReportSeries._epoch_label('2026-02-28') == '2026-02'
        assert AutoReportSeries._epoch_label(
            '2025-12-01_to_2026-02-28') == '2026-02'
        assert AutoReportSeries._epoch_label('epoch1') == 'epoch1'
        assert AutoReportSeries._pretty_pair(
            'R_between_0-SMOS_L2_and_1-ERA5_LAND') == 'SMOS L2 vs. ERA5 LAND'
        assert AutoReportSeries._pretty_pair('n_obs') == 'n_obs'


class _FakeReport:
    def __init__(self, ds):
        self.ds = ds

    def open_datasets(self):
        return {'run1': self.ds} if self.ds is not None else {}


def _fake_ds(values, metric='R_between_0-ISMN_and_1-C3S'):
    # 2 tsw so that the tsw selection is tested as well
    n = len(values)
    vals = np.stack([np.asarray(values, dtype=float), np.full(n, -99.)], axis=1)
    return xr.Dataset(
        {metric: (('loc', 'tsw'), vals),
         'lat': ('loc', np.arange(n, dtype=float)),
         'lon': ('loc', np.zeros(n))},
        coords={'tsw': ['bulk', 'other']})


class TestTrackMetricSynthetic(unittest.TestCase):
    """
    Synthetic monthly series (in memory) to test the expected range
    classification, the year-over-year comparison and missing reports.
    """
    metric = 'R_between_0-ISMN_and_1-C3S'

    def setUp(self):
        self.tempdir = Path(mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _series(self, last_values):
        rng = np.random.default_rng(42)
        names = [f"2026-0{m}-01" for m in range(1, 7)]
        datasets = [_fake_ds(0.5 + rng.normal(0, 0.01, 10)) for _ in range(5)]
        datasets[4] = None  # metric missing in the report before the current
        datasets.append(_fake_ds(last_values))
        series = AutoReportSeries.__new__(AutoReportSeries)
        series.series_root = self.tempdir
        series.reports = {n: _FakeReport(d) for n, d in zip(names, datasets)}
        return series

    def _track(self, series, **kwargs):
        with self.assertWarns(UserWarning):  # missing report
            kwargs = {'n_epochs': 6, 'min_history': 3, 'yoy_offset': 4,
                      'path_out': self.tempdir, **kwargs}
            sd = series.track_metric(self.metric, pretty_name='R', unit='-',
                                     **kwargs)
        return sd.data

    def test_track_metric_fixed_bounds(self):
        # value within history range, but below the predefined threshold
        data = self._track(self._series(np.full(10, 0.5)),
                           corridor_bounds=(0.6, 0.9))
        t = data['tracking']
        assert t['corridor_source'] == 'fixed'
        assert t['expected_lower'] == 0.6
        assert t['expected_upper'] == 0.9
        assert t['tracking_status'] == 'not ok'
        assert 'OUTSIDE the expected range [0.600, 0.900]' in t['summary']

        # one-sided bound, history is ignored (min_history not reached)
        data = self._track(self._series(np.full(10, 0.2)),
                           corridor_bounds=(0.1, None), min_history=100)
        t = data['tracking']
        assert t['tracking_status'] == 'ok'
        assert t['expected_upper'] is None
        assert 'within the expected range (≥ 0.100)' in t['summary']
        assert os.path.isfile(self.tempdir / f"tracking_{self.metric}.png")

        with self.assertRaises(ValueError):
            self._series(np.full(10, 0.5)).track_metric(
                self.metric, path_out=self.tempdir,
                corridor_bounds=(None, None))

    def test_track_metric_classification(self):
        # current report as before -> ok
        data = self._track(self._series(np.full(10, 0.5)))
        t = data['tracking']
        assert t['tracking_status'] == 'ok'
        assert t['corridor_source'] == 'history'
        assert t['n_history'] == 4
        assert t['expected_lower'] < 0.5 < t['expected_upper']
        assert data['series']['2026-05-01']['n'] == 0
        # previous valid report is used, missing one skipped
        assert t['previous_report'] == '2026-04-01'
        assert t['paired_previous']['n_common'] == 10
        assert t['paired_yoy']['report'] == '2026-02-01'
        assert t['paired_yoy']['median_diff'] is not None
        assert 'within the expected range' in t['summary']
        assert 'one year before' in t['summary']

        # strong drop -> not ok, paired difference reflects the drop
        data = self._track(self._series(np.full(10, 0.2)))
        t = data['tracking']
        assert t['tracking_status'] == 'not ok'
        assert t['tracking_color'] == 'red'
        assert abs(t['paired_previous']['median_diff'] + 0.3) < 0.05
        assert 'OUTSIDE' in t['summary']
        assert os.path.isfile(self.tempdir / f"tracking_{self.metric}.png")
        csv = (self.tempdir / f"stats_{self.metric}.csv").read_text()
        assert '2026-06' in csv


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
    testcase = TestSeriesExistingLocal()
    testcase.setUpClass()
    testcase.setUp()
    testcase.test_track_metrics_ubrmsd_and_r()
