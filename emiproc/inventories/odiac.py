from emiproc.grids import ODIACGrid, WGS84
from pathlib import Path
import rioxarray as rxr
import geopandas as gpd
from emiproc.inventories import Inventory


class ODIAC_Inventory(Inventory):
    grid: ODIACGrid

    def __init__(self, nc_file):

        da = rxr.open_rasterio(nc_file)[0]
        da = da.sortby("x")
        da = da.sortby("y")

        self.grid = ODIACGrid(nc_file)
        key = ("all", "CO2")
        mapping = {
            key: da.T.values.flatten()  # [x1y1, x1y2 ... xnyn ]
        }

        polys = self.grid.cells_as_polylist

        assert len(mapping[key]) == len(polys)

        nc_path = Path(nc_file)
        self.name = nc_path.stem

        gdf = gpd.GeoDataFrame(
                mapping,
                geometry=polys,
                crs=WGS84,
            )

        self.gdf = gdf
        self.gdfs = {
            # "all": gdf
        }

        self.cell_areas = self.grid.cell_areas

        super().__init__()
