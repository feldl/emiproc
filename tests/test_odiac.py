if __name__ == "__main__":
    from emiproc.grids import ICONGrid
    from emiproc.regrid import remap_inventory
    from emiproc.exports.icon import export_icon_oem
    from emiproc.inventories.odiac import ODIAC_Inventory
    from pathlib import Path

    nc_file = "/home/lenaf/Data/Emissions/odiac/clip6.tif"
    inv = ODIAC_Inventory(nc_file)

    print("created inventory ...")
    grid_file = Path(
        "/home/lenaf/Data/ICON-ART/grids/small_LAM/domain1_DOM01.nc")
    icon_grid = ICONGrid(grid_file)

    remaped_inv = remap_inventory(
        inv, icon_grid
    )
    print("remaped inventory ...")
    output_dir = Path("/home/lenaf/Data/Emissions/odiac/oem/")

    export_icon_oem(
        inv=remaped_inv,
        icon_grid_file=grid_file,
        output_dir=output_dir,
    )

    print(f"Exported to {output_dir}")
