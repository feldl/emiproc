from emiproc.grids import ODIACGrid, WGS84
from pathlib import Path
import rioxarray as rxr
import geopandas as gpd
from emiproc.inventories import Inventory


class ODIAC_Inventory(Inventory):
    grid: ODIACGrid

    def __init__(self, tif_file, days_of_month=30.4375):
        """Initialize ODIAC Inventory.

        - Read data from .tif odiac file.
        - Convert units to kg/yr/cell.
        - Create the gdf with a single category "all"
            and one substance "CO2".

        Parameters:
            tif_file (str):
                Path to the odiac tif file
            days_of_month (float or int):
                Number of days in month to be processed.
                Default: 365.25 / 12 = 30.4375.
        """

        self.grid = ODIACGrid(tif_file)

        da = self.get_da(tif_file)
        da = self.convert_units(da, days_of_month)

        key = ("all", "CO2")
        mapping = {
            key: da.T.values.flatten()  # [x1y1, x1y2 ... xnyn ]
        }

        polys = self.grid.cells_as_polylist
        assert len(mapping[key]) == len(polys)

        nc_path = Path(tif_file)
        self.name = nc_path.stem

        gdf = gpd.GeoDataFrame(
                mapping,
                geometry=polys,
                crs=WGS84,
            )

        self.gdf = gdf
        self.gdfs = {}

        self.cell_areas = self.grid.cell_areas

        super().__init__()

    def get_da(self, nc_file):
        da = rxr.open_rasterio(nc_file)[0]
        da = da.sortby("x")
        da = da.sortby("y")
        return da

    def convert_units(self, da, days_of_month):
        """Unit conversion of the data array.

        ODIACv2022 is delivered in "tonne carbon per cell (monthly total)"
        Convert to kg CO2 per yr per gridcell (expected by emiproc).
        """

        carbon_per_co2 = 12.011 / 44.009
        month_per_yr = days_of_month / 365.25
        kg_per_t = 1e3

        return da * kg_per_t / carbon_per_co2 / month_per_yr
