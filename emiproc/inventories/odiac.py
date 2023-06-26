from emiproc.grids import ODIACGrid, WGS84
from os import PathLike
from pathlib import Path
import rioxarray as rxr
import numpy as np
import geopandas as gpd
from emiproc.inventories import Inventory
import matplotlib.pyplot as plt


class ODIAC_Inventory(Inventory):
    grid: ODIACGrid

    def __init__(self, nc_file):

        da = rxr.open_rasterio(nc_file)[0]
        da = da.sortby("x")

        da = da.sortby("y")
        print(da["y"], "da[y]")
        print(da.shape, len(da["x"].values))
        self.grid = ODIACGrid(nc_file)

        nx = len(da["x"])
        ny = len(da["y"])
        values = np.zeros(nx*ny)
        k = 0
        # for i, vi in enumerate(da["x"]):
        #     for j, vj in enumerate(da["y"]):
        #         # print(da.sel(x=vi, y=vj))

        #         values[k] = da.sel(x=vi, y=vj).values
        #         k += 1

        mapping = {
            "CO2": da.T.values.flatten()  # [x1y1, x1y2 ... xnyn ]
            # "CO2": values  # [x1y1, x1y2 ... xnyn ]
        }
        print("equal:?")
        print(da.sel(x=da["x"][0], y=da["y"])[10].values)
        print(da.sel(x=da["x"][0], y=da["y"])[10])
        print(mapping["CO2"][10])
        print(da.shape)

        polys = self.grid.cells_as_polylist
        print(polys[10], "polys ??")

        print((mapping["CO2"].shape))

        assert len(mapping["CO2"]) == len(polys)

        nc_path = Path(nc_file)
        self.name = nc_path.stem

        gdf = gpd.GeoDataFrame(
                mapping,
                geometry=polys,
                crs=WGS84,
            )
        # gdf.plot(column="CO2")
        # plt.show()

        # gdf_geometry = gdf_geometry.to_crs(WGS84)

        self.gdf = gdf
        self.gdfs = {
            "all": gdf
        }

        self.cell_areas = self.grid.cell_areas

        super().__init__()


if __name__ == "__main__":
    from emiproc.grids import ICONGrid
    from emiproc.regrid import remap_inventory
    from emiproc.exports.icon import export_icon_oem

    nc_file = "/home/lena/Projects/data/odiac/odiac2020b_1km_excl_intl_1905.tif"
    inv = ODIAC_Inventory(nc_file)
    grid_file = Path("/home/lena/Projects/my_runscripts/data_preparation/areaemission/boxArea/domain1_DOM01.nc")
    icon_grid = ICONGrid(grid_file)

    remaped_inv = remap_inventory(
        inv, icon_grid, grid_file.parent / f".emiproc_remap_odiac{grid_file.stem}"
    )
    output_dir = grid_file.with_name(f"{grid_file.stem}_with_tno_emissions")

    export_icon_oem(
        inv=inv,
        icon_grid_file=grid_file,
        output_dir=output_dir,
    )

    print(f"Exported to {output_dir}")
