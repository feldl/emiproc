"""Example of remapping the TNO inventory to the ICON grid and exporting it to OEM."""
# %%
from pathlib import Path

from emiproc.grids import WGS84, ICONGrid, WGS84_PROJECTED
from emiproc.inventories.tno import TNO_Inventory
from emiproc.inventories.categories_groups import TNO_2_GNFR
from emiproc.inventories.utils import group_categories
from emiproc.regrid import remap_inventory
from emiproc.exports.icon import export_icon_oem, TemporalProfilesTypes


# %% Declare path of the TNO netcdf file
nc_file = "/home/lena/TNO/AP_2021_2022/CAMS-REG-AP_v6_1_emissions_year2021.nc"

# %% Load the inventory to an object
inv = TNO_Inventory(nc_file)


# %% Load the icon grid
grid_file = Path("/home/lena/Projects/my_runscripts/data_preparation/areaemission/boxArea/domain1_DOM01.nc")
icon_grid = ICONGrid(grid_file)

# %%
# Convert to a planar crs, required for surface conserving remapping
inv.to_crs(WGS84_PROJECTED)

# %% Remap the inventory to the icon grid
remaped_tno = remap_inventory(
    inv, icon_grid, grid_file.parent / f".emiproc_remap_tno2{grid_file.stem}"
)

# %% Group the categories to the GNFR (Mainly renaming them)
groupped = group_categories(
    inv=remaped_tno,
    categories_group=TNO_2_GNFR
)

# %% Export the invenotry to OEM

output_dir = grid_file.with_name(f"{grid_file.stem}_with_tno_emissions")

export_icon_oem(
    inv=groupped,
    icon_grid_file=grid_file,
    output_dir=output_dir,
    temporal_profiles_type=TemporalProfilesTypes.THREE_CYCLES
)

print(f"Exported to {output_dir}")

# %%
