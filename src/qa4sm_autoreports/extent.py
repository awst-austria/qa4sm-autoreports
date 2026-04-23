from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import cartopy.crs as ccrs
import cartopy.feature as cfeature



@dataclass(frozen=True)
class GeographicExtent:
    """
    An immutable geographic bounding box defined by its corner coordinates.

    Coordinate conventions
    ----------------------
    - Latitude  : -90.0 (South Pole) to +90.0 (North Pole)
    - Longitude : -180.0 (antimeridian west) to +180.0 (antimeridian east)

    Attributes
    ----------
    min_lat : float  Southern boundary.
    min_lon : float  Western boundary.
    max_lat : float  Northern boundary.
    max_lon : float  Eastern boundary.

    Note
    ----
    Extents that wrap around the antimeridian (e.g. parts of Alaska / Pacific)
    are *not* handled by this class.  All longitudes are assumed to satisfy
    min_lon <= max_lon.
    """

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    # ------------------------------------------------------------------
    # Construction / validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not (-90.0 <= self.min_lat <= 90.0):
            raise ValueError(f"min_lat {self.min_lat!r} is outside [-90, 90].")
        if not (-90.0 <= self.max_lat <= 90.0):
            raise ValueError(f"max_lat {self.max_lat!r} is outside [-90, 90].")
        if not (-180.0 <= self.min_lon <= 180.0):
            raise ValueError(f"min_lon {self.min_lon!r} is outside [-180, 180].")
        if not (-180.0 <= self.max_lon <= 180.0):
            raise ValueError(f"max_lon {self.max_lon!r} is outside [-180, 180].")
        if self.min_lat > self.max_lat:
            raise ValueError(
                f"min_lat ({self.min_lat}) must be <= max_lat ({self.max_lat})."
            )
        if self.min_lon > self.max_lon:
            raise ValueError(
                f"min_lon ({self.min_lon}) must be <= max_lon ({self.max_lon})."
            )

    @classmethod
    def from_corners(
        cls,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> "GeographicExtent":
        """
        Convenience constructor that accepts two arbitrary corner points and
        sorts the coordinates automatically.

        Parameters
        ----------
        lat1, lon1 : float  First corner (any order).
        lat2, lon2 : float  Opposite corner (any order).
        """
        return cls(
            min_lat=min(lat1, lat2),
            min_lon=min(lon1, lon2),
            max_lat=max(lat1, lat2),
            max_lon=max(lon1, lon2),
        )

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def width(self) -> float:
        """East–west span in degrees."""
        return self.max_lon - self.min_lon

    @property
    def height(self) -> float:
        """North–south span in degrees."""
        return self.max_lat - self.min_lat

    @property
    def center(self) -> tuple[float, float]:
        """(latitude, longitude) of the geometric centre."""
        return (
            (self.min_lat + self.max_lat) / 2.0,
            (self.min_lon + self.max_lon) / 2.0,
        )

    @property
    def corners(self) -> tuple[tuple[float, float], ...]:
        """
        All four corners as (lat, lon) tuples in order:
        SW, NW, NE, SE.
        """
        return (
            (self.min_lat, self.min_lon),  # SW
            (self.max_lat, self.min_lon),  # NW
            (self.max_lat, self.max_lon),  # NE
            (self.min_lat, self.max_lon),  # SE
        )

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def equals(self, other: "GeographicExtent", tolerance: float = 0.0) -> bool:
        """
        Return True when this extent and *other* cover the same region.

        Parameters
        ----------
        other     : GeographicExtent  The extent to compare against.
        tolerance : float             Allowed absolute difference in degrees
                                      for each boundary (default: exact match).

        Examples
        --------
        >>> a = GeographicExtent(0, 0, 10, 10)
        >>> b = GeographicExtent(0.0001, 0, 10, 10)
        >>> a.equals(b)
        False
        >>> a.equals(b, tolerance=0.001)
        True
        """
        if not isinstance(other, GeographicExtent):
            return NotImplemented
        return (
            abs(self.min_lat - other.min_lat) <= tolerance
            and abs(self.min_lon - other.min_lon) <= tolerance
            and abs(self.max_lat - other.max_lat) <= tolerance
            and abs(self.max_lon - other.max_lon) <= tolerance
        )

    # `==` uses the dataclass-generated __eq__ (exact field equality).
    # Use `.equals(other, tolerance=…)` for fuzzy comparison.

    def overlaps(self, other: "GeographicExtent") -> bool:
        """
        Return True if this extent and *other* have any area in common
        (touching edges count as overlapping).
        """
        return (
            self.min_lat <= other.max_lat
            and self.max_lat >= other.min_lat
            and self.min_lon <= other.max_lon
            and self.max_lon >= other.min_lon
        )

    def contains(self, other: "GeographicExtent") -> bool:
        """Return True if *other* is fully enclosed by this extent."""
        return (
            self.min_lat <= other.min_lat
            and self.max_lat >= other.max_lat
            and self.min_lon <= other.min_lon
            and self.max_lon >= other.max_lon
        )

    def contains_point(self, lat: float, lon: float) -> bool:
        """Return True if the point (lat, lon) lies within this extent."""
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon

    # ------------------------------------------------------------------
    # Intersection
    # ------------------------------------------------------------------

    def intersection(self, other: "GeographicExtent") -> Optional["GeographicExtent"]:
        """
        Compute the intersection of this extent and *other*.

        Returns
        -------
        GeographicExtent
            The overlapping region, or ``None`` if the extents do not overlap.

        Examples
        --------
        >>> a = GeographicExtent(0, 0, 10, 10)
        >>> b = GeographicExtent(5, 5, 15, 15)
        >>> a.intersection(b)
        GeographicExtent(min_lat=5, min_lon=5, max_lat=10, max_lon=10)
        """
        new_min_lat = max(self.min_lat, other.min_lat)
        new_min_lon = max(self.min_lon, other.min_lon)
        new_max_lat = min(self.max_lat, other.max_lat)
        new_max_lon = min(self.max_lon, other.max_lon)

        if new_min_lat > new_max_lat or new_min_lon > new_max_lon:
            return None  # No overlap

        return GeographicExtent(new_min_lat, new_min_lon, new_max_lat, new_max_lon)

    @staticmethod
    def multi_intersection(*extents: "GeographicExtent") -> Optional["GeographicExtent"]:
        """
        Compute the common intersection of two or more extents.

        Parameters
        ----------
        *extents : GeographicExtent
            Two or more extents to intersect.

        Returns
        -------
        GeographicExtent
            The region common to all supplied extents, or ``None`` if there
            is no common region (or fewer than two extents are supplied).

        Examples
        --------
        >>> a = GeographicExtent(0, 0, 20, 20)
        >>> b = GeographicExtent(5, 5, 25, 25)
        >>> c = GeographicExtent(8, 3, 15, 18)
        >>> GeographicExtent.multi_intersection(a, b, c)
        GeographicExtent(min_lat=8, min_lon=5, max_lat=15, max_lon=18)
        """
        if len(extents) < 2:
            return None

        result: Optional[GeographicExtent] = extents[0]
        for ext in extents[1:]:
            if result is None:
                break
            result = result.intersection(ext)

        return result

    # ------------------------------------------------------------------
    # Union (bounding box of all extents)
    # ------------------------------------------------------------------

    @staticmethod
    def union(*extents: "GeographicExtent") -> "GeographicExtent":
        """
        Return the smallest extent that contains all supplied extents.

        Parameters
        ----------
        *extents : GeographicExtent  Two or more extents.
        """
        if not extents:
            raise ValueError("At least one extent is required.")
        return GeographicExtent(
            min_lat=min(e.min_lat for e in extents),
            min_lon=min(e.min_lon for e in extents),
            max_lat=max(e.max_lat for e in extents),
            max_lon=max(e.max_lon for e in extents),
        )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"GeographicExtent("
            f"min_lat={self.min_lat}, min_lon={self.min_lon}, "
            f"max_lat={self.max_lat}, max_lon={self.max_lon})"
        )

    def __str__(self) -> str:
        return (
            f"[{self.min_lat}°, {self.min_lon}°]  →  "
            f"[{self.max_lat}°, {self.max_lon}°]"
        )

    def __and__(self, other: "GeographicExtent") -> Optional["GeographicExtent"]:
        """Syntactic sugar: ``extent_a & extent_b`` → intersection."""
        return self.intersection(other)

    def __or__(self, other: "GeographicExtent") -> "GeographicExtent":
        """Syntactic sugar: ``extent_a | extent_b`` → union."""
        return GeographicExtent.union(self, other)

    def plot_map(self) -> plt.Figure:
        """
        Alternative version with higher detail and different styling options.
        """
        fig = plt.figure(figsize=(15, 10), dpi=300)
        ax = plt.axes(projection=ccrs.PlateCarree())

        # Calculate bounds
        lat_range = self.max_lat - self.min_lat
        lon_range = self.max_lon - self.min_lon
        padding = max(lat_range, lon_range) * 0.4

        minlon = self.min_lon - padding
        if minlon < -180:
            minlon = -180
        maxlon = self.max_lon + padding
        if maxlon > 180:
            maxlon = 180
        minlat = self.min_lat - padding
        if minlat < -90:
            minlat = -90
        maxlat = self.max_lat + padding
        if maxlat > 90:
            maxlat = 90

        ax.set_extent([minlon, maxlon, minlat, maxlat],
                      crs=ccrs.PlateCarree())

        # High quality features
        ax.add_feature(cfeature.COASTLINE, linewidth=1.2, color='black')
        ax.add_feature(cfeature.BORDERS, linewidth=0.8, color='darkgray')
        land = cfeature.NaturalEarthFeature(
            category='physical', name='land',
            scale='110m', facecolor='#f0f0f0', edgecolor='none'
        )
        ocean = cfeature.NaturalEarthFeature(
            category='physical', name='ocean',
            scale='110m', facecolor='#e6f3ff', edgecolor='none'
        )
        ax.add_feature(land)
        ax.add_feature(ocean)
        ax.add_feature(cfeature.LAKES, facecolor='#e6f3ff', linewidth=0.5)
        ax.add_feature(cfeature.RIVERS, color='#4da6ff', linewidth=0.4)

        # Add the rectangle with gradient effect
        rectangle = patches.Rectangle(
            (self.min_lon, self.min_lat),
            self.max_lon - self.min_lon,
            self.max_lat - self.min_lat,
            linewidth=5, edgecolor='red', facecolor='red',
            alpha=0.15, transform=ccrs.PlateCarree(), zorder=10,
            label='Covered Area'
        )
        ax.add_patch(rectangle)

        # Enhanced gridlines
        gl = ax.gridlines(draw_labels=True, linewidth=0.8, color='gray',
                          alpha=0.6, linestyle=':')
        gl.top_labels = False
        gl.right_labels = False

        ax.legend()

        return fig