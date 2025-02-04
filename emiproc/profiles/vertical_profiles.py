from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from os import PathLike
import numpy as np
import pandas as pd

from emiproc.profiles.utils import read_profile_csv


@dataclass
class VerticalProfile:
    """Vertical profile.

    A vertical profile defines how the emission is split vertically on the
    altitude. A vertical profile is defined simply by its ratios
    and the height levels.

    You can check the conditions required on the profile in
    :py:func:`check_valid_vertical_profile`

    :arg ratios: The proportion of emission that is in each layer.
    :arg height: The top height of the layers.
        The first layer starts at 0 meter and ends at height[0].
        The second layer starts at height[0] and ends at height[1].
        Over the last height value, there is no emission.
    """

    ratios: np.ndarray
    height: np.ndarray

    @property
    def n_profiles(self) -> int:
        return 1


@dataclass
class VerticalProfiles:
    """Vertical profiles.

    This is very similar to :py:class:`VerticalProfile` but it can store
    many ratios for the same height distributions

    :arg ratios: a (n_profiles, n_heights) array.
    :arg height: Same as :py:attr:`VerticalProfile.height` .
    """

    ratios: np.ndarray
    height: np.ndarray

    @property
    def n_profiles(self) -> int:
        return self.ratios.shape[0]

    def copy(self):
        """Make a deep copy of the profiles."""
        return VerticalProfiles(
            self.ratios.copy(),
            self.height.copy(),
        )

    def __add__(self, other: VerticalProfiles):
        if isinstance(other, int) and other == 0:
            # Useful for call in sum()
            return self.copy()

        assert isinstance(other, VerticalProfiles)
        assert np.allclose(other.height, self.height)

        return VerticalProfiles(
            height=self.height,
            ratios=np.concatenate([self.ratios, other.ratios], axis=0),
        )

    def __radd__(self, other: VerticalProfiles):
        # Useful for call in sum()
        return self.__add__(other)

    def __getitem__(self, index: int) -> VerticalProfile:
        return VerticalProfile(
            ratios=self.ratios[index],
            height=self.height,
        )
    
    def __len__(self) -> int:
        return self.n_profiles


class GroupingMethod(Enum):
    KEEP_ALL_LEVELS = auto()


def get_mid_heights(max_heights: np.ndarray) -> np.ndarray:
    """Get the mid position of the height based on emiproc convention for height levels."""
    min_height = np.roll(max_heights, 1)
    # First level start at 0
    min_height[0] = 0
    mid_heights = (max_heights + min_height) / 2
    return mid_heights


def get_delta_h(max_heights: np.ndarray) -> np.ndarray:
    """Get height coverd by each level based on emiproc convention for height levels.."""
    min_height = np.roll(max_heights, 1)
    # First level start at 0
    min_height[0] = 0
    return max_heights - min_height


def get_weights_profiles_interpolation(
    from_p: np.ndarray, to_p: np.ndarray
) -> np.ndarray:
    """Calculate the weights matrix between two profiles.

    The weights matrix can then simply be used .

    The two given profiles must be sorted.
    It is assumed that they are vertical profiles from emiproc convention
    """

    # Initialize parameters for the algorithm
    i, j = 0, 0
    last = 0.0

    diff = np.zeros((len(to_p), len(from_p)))

    while i < len(from_p) and j < len(to_p):
        # Will check the distance with the last point
        # and will input it in the diff matrix
        f = from_p[i]
        t = to_p[j]
        if f <= t:
            diff[j, i] = f - last
            i += 1
            last = f
        else:
            diff[j, i] = t - last
            j += 1
            last = t

    if j == len(to_p):
        # Assing the last ones to the last line
        while i < len(from_p):
            f = from_p[i]
            diff[-1, i] += f - last
            i += 1
            last = f

    # Weights is the noramlized
    return diff / diff.sum(axis=0)


def resample_vertical_profiles(
    *profiles: VerticalProfile | VerticalProfiles,
    specified_levels: np.ndarray | None = None,
) -> VerticalProfiles:
    """Resample vertical profiles into one vertical profiles object.

    Allows for profiles of different height levels to be groupped into one.
    Sample the profile on the heights level given.

    Uses a conservative interpolation method, that ensure that
    even on higher resolution the profile will be exactly the same.
    Note that this sometimes has no physical sense and a linear
    interpolation when using profiles would be better
    at higher resolutions, but this has to be a choice from the user.

    :arg specified_levels: If this is specified, you can select an arbitray
        scale on which to reproject. If not specified, all the levels found
        in the profiles will be used.
        The ordering of the profiles will match the order given as input.
    """

    # Find the levels we want to use
    if specified_levels is None:
        levels = np.unique(np.concatenate([p.height for p in profiles]))
    else:
        levels = specified_levels


    out_ratios = []
    for p in profiles:
        # Get the weights for remapping those profiles
        weights = get_weights_profiles_interpolation(p.height, levels)

        # Do the remapping and add it to the results
        out_ratios.append(p.ratios.dot(weights.T))

    return VerticalProfiles(np.row_stack(out_ratios), levels)


def check_valid_vertical_profile(vertical_profile: VerticalProfile | VerticalProfiles):
    """Check that the vertical profile meets requirements.

    * height must have positive values
    * height must have strictly increasing values
    * ratios must sum up to one
    * ratios must all be >= 0
    * ratios and height must have the same len
    * no nan values in any of the arrays

    :arg veritcal_profile: The profile to check.
    :raises AssertionError: If the profile is invalid.
    """

    assert isinstance(vertical_profile, (VerticalProfile, VerticalProfiles))

    h = vertical_profile.height
    r = vertical_profile.ratios

    assert np.all(~np.isnan(r)) and np.all(~np.isnan(h)), "Cannot contain nan values"

    assert np.all(h > 0)
    assert np.all(h[1:] > np.roll(h, 1)[1:]), "height must be increasing"
    if isinstance(vertical_profile, VerticalProfile):
        assert np.sum(r) == 1.0
        assert len(r) == len(h)
    else:
        ratio_sum = np.sum(r, axis=1)
        assert np.allclose(ratio_sum, 1.0), f"Ratios must sum to 1, but {ratio_sum=}"
        assert r.shape[1] == len(h)
    assert np.all(r >= 0)


def from_csv(file: PathLike) -> tuple[VerticalProfiles, list[str | tuple[str, str]]]:
    """Read a csv file containing vertical profiles.

    The format is the following::

        Category,Substance,20m,92m,184m,324m,522m,781m,1106m
        Public_Power,CO2,0,0,0.0025,0.51,0.453,0.0325,0.002
        Public_Power,CH4,0,0,0.0025,0.51,0.453,0.0325,0.002
        Industry,CO2,0.06,0.16,0.75,0.03,0,0,0
        ...

    The first line is the header, the first column is the category,
    the second column is the substance and the rest of the columns
    are the ratios for each height level.

    The heights level specify mean from the previous height to this one.
    (e.g. 20m is the mean from 0 to 20m, 92m is the mean from 20m to 92m, ...)

    The Substance column is optional, if not present, the category will be used
    only.

    """

    # Read the file
    df, cat_header, sub_header = read_profile_csv(file)

    # Get the height levels
    heights_mapping = {
        float(col_name[:-1]): col_name
        for col_name in df.columns
        # Take only the columns that end with m
        if col_name.endswith("m")
    }
    heights = sorted(heights_mapping.keys())
    heights_cols = [heights_mapping[h] for h in heights]

    # Create the profiles
    profiles = VerticalProfiles(df[heights_cols].to_numpy(), heights)

    if sub_header is None:
        cat_sub = df[cat_header].to_list()
    else:
        cat_sub = df[[cat_header, sub_header]].apply(tuple, axis=1).to_list()

    return profiles, cat_sub
