"""
test_geographic_extent.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the GeographicExtent class.
Run with:  python -m pytest test_geographic_extent.py -v
"""

import pytest
from src.qa4sm_autoreports.extent import GeographicExtent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def europe():
    return GeographicExtent(35.0, -10.0, 71.0, 40.0)

@pytest.fixture
def med_area():
    return GeographicExtent(30.0, -6.0, 48.0, 37.0)

@pytest.fixture
def balkans():
    return GeographicExtent(39.0, 18.0, 48.0, 30.0)

@pytest.fixture
def arctic():
    return GeographicExtent(80.0, 0.0, 90.0, 10.0)


# ---------------------------------------------------------------------------
# Construction & validation
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_valid_extent(self):
        e = GeographicExtent(0.0, 0.0, 10.0, 10.0)
        assert e.min_lat == 0.0
        assert e.min_lon == 0.0
        assert e.max_lat == 10.0
        assert e.max_lon == 10.0

    def test_from_corners_sorted(self):
        e = GeographicExtent.from_corners(10.0, 20.0, 0.0, 5.0)
        assert e.min_lat == 0.0
        assert e.min_lon == 5.0
        assert e.max_lat == 10.0
        assert e.max_lon == 20.0

    def test_from_corners_already_sorted(self):
        e = GeographicExtent.from_corners(0.0, 5.0, 10.0, 20.0)
        assert e == GeographicExtent(0.0, 5.0, 10.0, 20.0)

    def test_invalid_min_lat_too_low(self):
        with pytest.raises(ValueError, match="min_lat"):
            GeographicExtent(-91.0, 0.0, 10.0, 10.0)

    def test_invalid_max_lat_too_high(self):
        with pytest.raises(ValueError, match="max_lat"):
            GeographicExtent(0.0, 0.0, 91.0, 10.0)

    def test_invalid_min_lon_too_low(self):
        with pytest.raises(ValueError, match="min_lon"):
            GeographicExtent(0.0, -181.0, 10.0, 10.0)

    def test_invalid_max_lon_too_high(self):
        with pytest.raises(ValueError, match="max_lon"):
            GeographicExtent(0.0, 0.0, 10.0, 181.0)

    def test_invalid_lat_inverted(self):
        with pytest.raises(ValueError, match="min_lat"):
            GeographicExtent(20.0, 0.0, 10.0, 10.0)

    def test_invalid_lon_inverted(self):
        with pytest.raises(ValueError, match="min_lon"):
            GeographicExtent(0.0, 20.0, 10.0, 10.0)

    def test_frozen(self):
        e = GeographicExtent(0.0, 0.0, 10.0, 10.0)
        with pytest.raises(Exception):
            e.min_lat = 5.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Derived properties
# ---------------------------------------------------------------------------

class TestProperties:
    def test_width(self):
        e = GeographicExtent(0.0, -10.0, 10.0, 30.0)
        assert e.width == pytest.approx(40.0)

    def test_height(self):
        e = GeographicExtent(10.0, 0.0, 55.0, 10.0)
        assert e.height == pytest.approx(45.0)

    def test_center(self):
        e = GeographicExtent(0.0, 0.0, 10.0, 20.0)
        assert e.center == (5.0, 10.0)

    def test_corners(self):
        e = GeographicExtent(0.0, 0.0, 10.0, 20.0)
        assert e.corners == (
            (0.0, 0.0),   # SW
            (10.0, 0.0),  # NW
            (10.0, 20.0), # NE
            (0.0, 20.0),  # SE
        )


# ---------------------------------------------------------------------------
# Equality
# ---------------------------------------------------------------------------

class TestEquality:
    def test_exact_equal(self, europe):
        same = GeographicExtent(35.0, -10.0, 71.0, 40.0)
        assert europe == same

    def test_exact_not_equal(self, europe, med_area):
        assert europe != med_area

    def test_fuzzy_equal_within_tolerance(self, europe):
        approx = GeographicExtent(35.0001, -10.0, 71.0, 40.0)
        assert europe.equals(approx, tolerance=0.001)

    def test_fuzzy_not_equal_outside_tolerance(self, europe):
        approx = GeographicExtent(35.01, -10.0, 71.0, 40.0)
        assert not europe.equals(approx, tolerance=0.001)

    def test_fuzzy_zero_tolerance_same_as_eq(self, europe):
        same = GeographicExtent(35.0, -10.0, 71.0, 40.0)
        assert europe.equals(same, tolerance=0.0)

    def test_hashable_usable_in_set(self, europe, med_area):
        s = {europe, med_area, GeographicExtent(35.0, -10.0, 71.0, 40.0)}
        assert len(s) == 2


# ---------------------------------------------------------------------------
# Spatial predicates
# ---------------------------------------------------------------------------

class TestOverlaps:
    def test_overlapping(self, europe, med_area):
        assert europe.overlaps(med_area)

    def test_overlapping_symmetric(self, europe, med_area):
        assert med_area.overlaps(europe)

    def test_non_overlapping(self, europe, arctic):
        assert not europe.overlaps(arctic)

    def test_touching_edge_counts_as_overlap(self):
        a = GeographicExtent(0.0, 0.0, 10.0, 10.0)
        b = GeographicExtent(10.0, 0.0, 20.0, 10.0)
        assert a.overlaps(b)

    def test_identical_extents_overlap(self, europe):
        assert europe.overlaps(europe)


class TestContains:
    def test_contains_smaller(self, europe, balkans):
        assert europe.contains(balkans)

    def test_does_not_contain_larger(self, balkans, europe):
        assert not balkans.contains(europe)

    def test_contains_itself(self, europe):
        assert europe.contains(europe)

    def test_does_not_contain_partial_overlap(self, europe, med_area):
        # med_area extends south of europe (min_lat 30 < 35)
        assert not europe.contains(med_area)

    def test_contains_point_inside(self, europe):
        assert europe.contains_point(51.5, 0.0)   # London

    def test_contains_point_on_boundary(self, europe):
        assert europe.contains_point(35.0, -10.0)  # SW corner

    def test_does_not_contain_point_outside(self, europe):
        assert not europe.contains_point(0.0, 0.0)  # Gulf of Guinea


# ---------------------------------------------------------------------------
# Intersection
# ---------------------------------------------------------------------------

class TestIntersection:
    def test_two_overlapping(self, europe, med_area):
        result = europe.intersection(med_area)
        assert result == GeographicExtent(35.0, -6.0, 48.0, 37.0)

    def test_intersection_symmetric(self, europe, med_area):
        assert europe.intersection(med_area) == med_area.intersection(europe)

    def test_no_overlap_returns_none(self, europe, arctic):
        assert europe.intersection(arctic) is None

    def test_touching_edge_returns_zero_area(self):
        a = GeographicExtent(0.0, 0.0, 10.0, 10.0)
        b = GeographicExtent(10.0, 0.0, 20.0, 10.0)
        result = a.intersection(b)
        assert result is not None

    def test_contained_extent_returns_itself(self, europe, balkans):
        result = europe.intersection(balkans)
        assert result == balkans

    def test_and_operator(self, europe, med_area):
        assert (europe & med_area) == europe.intersection(med_area)

    def test_and_operator_no_overlap(self, europe, arctic):
        assert (europe & arctic) is None


class TestMultiIntersection:
    def test_three_overlapping(self, europe, med_area, balkans):
        result = GeographicExtent.multi_intersection(europe, med_area, balkans)
        assert result == GeographicExtent(39.0, 18.0, 48.0, 30.0)

    def test_two_extents(self, europe, med_area):
        result = GeographicExtent.multi_intersection(europe, med_area)
        assert result == europe.intersection(med_area)

    def test_one_non_overlapping_returns_none(self, europe, med_area, arctic):
        result = GeographicExtent.multi_intersection(europe, med_area, arctic)
        assert result is None

    def test_fewer_than_two_returns_none(self, europe):
        assert GeographicExtent.multi_intersection(europe) is None

    def test_no_args_returns_none(self):
        assert GeographicExtent.multi_intersection() is None


# ---------------------------------------------------------------------------
# Union
# ---------------------------------------------------------------------------

class TestUnion:
    def test_union_of_two(self, europe, med_area):
        result = GeographicExtent.union(europe, med_area)
        assert result == GeographicExtent(30.0, -10.0, 71.0, 40.0)

    def test_union_contains_both(self, europe, arctic):
        result = GeographicExtent.union(europe, arctic)
        assert result.contains(europe)
        assert result.contains(arctic)

    def test_union_of_contained_is_container(self, europe, balkans):
        assert GeographicExtent.union(europe, balkans) == europe

    def test_union_symmetric(self, europe, med_area):
        assert GeographicExtent.union(europe, med_area) == GeographicExtent.union(med_area, europe)

    def test_union_three_extents(self, europe, med_area, arctic):
        result = GeographicExtent.union(europe, med_area, arctic)
        assert result.min_lat == pytest.approx(30.0)
        assert result.max_lat == pytest.approx(90.0)

    def test_or_operator(self, europe, med_area):
        assert (europe | med_area) == GeographicExtent.union(europe, med_area)

    def test_union_no_args_raises(self):
        with pytest.raises((ValueError, TypeError)):
            GeographicExtent.union()