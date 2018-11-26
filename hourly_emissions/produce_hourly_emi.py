import time
import datetime

import netCDF4 as nc
import numpy as np

# ATM: rlat, rlon determined by dimensions in emi_file
#      levels determined by dimensions in ver_file
#      Would be nice if a subset could be specified by slicing

def daterange(start_date, end_date):
    """Yield a range containing dates from [start_date, end_date).

    From https://stackoverflow.com/a/1060330.

    Parameters
    ----------
    start_date : datetime.date
    end_date : datetime.date

    Yields
    ------
    datetime.date
        Consecutive dates, starting from start_date and ending the day
        before end_date.
    """
    for n in range(int ((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)


def country_id_mapping(country_codes, grid):
    """Map a country index to each gridpoint

    grid contains an EMEP country code at each gridpoint.
    country_codes is a 1D-array with all EMEP country codes.
    Assign to each gridpoint the index in country_codes
    of the EMEP-code given at that gridpoint by grid-mapping.

    This is useful as profiles belonging to countries are stored
    in the same order as the country_codes.

    Parameters
    ----------
    country_codes : np.array(dtype=int, shape=(n, ))
        Contains EMEP country codes
    grid : np.array(dtype=int)
        Each element points is a EMEP code which should be present in
        country_codes

    Returns
    -------
    np.array(dtype=int, shape=grid.shape)
        Contains at each gridpoint the position of the EMEP code (from grid)
        in country_codes
    """
    # There are 134 different EMEP country-codes, this fits in an uint8
    res = np.empty(shape=grid.shape, dtype=np.uint8)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            location = np.where(country_codes[:] == grid[i,j])
            try:
                res[i,j] = location[0][0]
            except IndexError:
                raise IndexError("Country-ID not found")

    return res


def extract_to_grid(grid_to_index, country_vals):
    """Extract the values from each country_vals [1D] on gridpoints given
    by grid_to_index (2D)

    Parameters
    ----------
    grid_to_index : np.array(dtype=int)
        grid_to_index has at every gridpoint an integer which serves as an
        index into country_vals.
        grid_to_index.shape == (x, y)
        grid_to_index[i,j] < n_k forall i < x, j < y, k < len(country_vals)
    *country_vals : list(np.array(dtype=float))
        country_vals[i].shape == (n_i,)

    Returns
    -------
    tuple(np.array(dtype=float))
        Tuple of np.arrays, each of them the containing at (i,j) the value
        in the corresponding country_vals-array indicated by the grid_to_index-
        array.

        >>> res1, res2 = extract_to_grid(x, y, z)
        >>> y.dtype == res1.dtype
        True
        >>> x.shape == res2.shape
        >>> res1[i,j] == y[x[i,j]]
        True
        >>> res2[i,j] == z[x[i,j]]
        True
    """
    res = np.empty(shape=grid_to_index.shape, dtype=np.float32)
    for i in range(grid_to_index.shape[0]):
        for j in range(grid_to_index.shape[1]):
            res[i,j] = country_vals[grid_to_index[i,j]]
    return res


def write_metadata(outfile, org_file, emi_file, ver_file, variables):
    """Write the metadata of the outfile.

    Determine rlat, rlon from emi_file, levels from ver_file.

    Create "time", "rlon", "rlat", "bnds", "level" dimensions.

    Create "time", "rotated_pole", "level", "level_bnds" variables from
    org_file.

    Create "rlon", "rlat" variables from emi_file.

    Create an emtpy variable with dimensions ("time", "level", "rlat", "rlon")
    for element of varaibles.

    Copy "level" & "level_bnds" values from ver_file "time" values from org_file.

    Parameters
    ----------
    outfile : netCDF4.Dataset
        Opened with 'w'-option. Where the data is written to.
    org_file : netCDF4.Dataset
        Containing variables "time", "rotated_pole", "level", "level_bnds"
    emi_file : netCDF4.Dataset
        Containing dimensions "rlon", "rlat"
    ver_file : netCDF4.Dataset
        Containing the variable "level_bnds" and varaible & dimension "level"
    variables : list(str)
        List of variable-names to be created
    """
    rlat = emi_file.dimensions['rlat'].size
    rlon = emi_file.dimensions['rlon'].size
    level = ver_file.dimensions['level'].size

    outfile.createDimension('time')
    outfile.createDimension('rlon', rlon)
    outfile.createDimension('rlat', rlat)
    outfile.createDimension('bnds', 2)
    outfile.createDimension('level', level)

    var_srcfile = [('time', org_file),
                   ('rotated_pole', org_file),
                   ('level', org_file),
                   ('level_bnds', org_file),
                   ('rlon', emi_file),
                   ('rlat', emi_file)]

    for varname, src_file in var_srcfile:
        outfile.createVariable(varname = varname,
                               datatype = src_file[varname].datatype,
                               dimensions = src_file[varname].dimensions)
        outfile[varname].setncatts(src_file[varname].__dict__)

    outfile['time'][:] = org_file['time'][:]
    outfile['level'][:] = ver_file['layer_mid'][:]
    outfile['level_bnds'][:] = (
        np.array([ver_file['layer_bot'][:], ver_file['layer_top'][:]]))

    for varname in variables:
        outfile.createVariable(varname = varname,
                               datatype = 'float32',
                               dimensions = ('time', 'level', 'rlat', 'rlon'))


def extract_matrices(infile, var_list, indices, transform=None):
    """Extract the array specified by indices for each variable in var_list
    from infile.

    If transform is not none, it is applied to the extracted array.

    Parameters
    ----------
    infile : netCDF4.Dataset
    var_list : list(list(str))
    indices : slice()
    transform : function
        Takes as input the extracted array (infile[var][indices]).
        Default: None (== identity)

    Returns
    -------
    dict()
        Return a dictionary of varname : np.array() pairs.

        >>> mats = extract_matrices(if, ['myvar'], np.s_[0, :])
        >>> np.allclose(mats['myvar'], if['myvar'][0, :], rtol=0, atol=0)
        True
        >>> mats2 = extract_matrics(if, ['myvar'], np.s_[0, :], np.max)
        >>> mats2['myvar'] == np.max(if['myvar'][0, :])
        True
    """
    res = dict()

    if transform is None:
        for subvar_list in var_list:
            for var in subvar_list:
                res[var] = np.array(infile[var][indices])
    else:
        for subvar_list in var_list:
            for var in subvar_list:
                res[var] = np.array(transform(infile[var][indices]))

    return res


#################
# Berlin testcase
# path_emi = "../testdata/emis_2015_Berlin-coarse_64_74.nc"
# path_org = "../testdata/hourly_emi_brd/CO2_CO_NOX_Berlin-coarse_2015010110.nc"
# output_path = "./output/"
# output_name = "CO2_CO_NOX_Berlin-coarse_"
# prof_path = "./input_profiles/"
# rlon = 74
# rlat = 64
# var_list = ["CO2_A_E","CO2_07_E"]
# catlist = [['CO2_02_AREA','CO2_34_AREA','CO2_05_AREA','CO2_06_AREA','CO2_07_AREA','CO2_08_AREA','CO2_09_AREA','CO2_10_AREA'],
#            ["CO2_07_AREA"]]
# tplist = [['CO2_2','CO2_4','CO2_5','CO2_6','CO2_7','CO2_8','CO2_9','CO2_10'],
#           ["CO2_7"]]
# vplist = [['SNAP-2','SNAP-4','SNAP-5','SNAP-6','SNAP-7','SNAP-8','SNAP-9','SNAP-10'],
#           ["SNAP-7"]]
################

##########
# CHE
#path_emi = "../testdata/CHE_TNO_offline/emis_2015_Europe.nc"
path_emi = "../testdata/CHE_TNO_offline/emis_2015_Europe.nc"
path_org = "../testdata/hourly_emi_brd/CO2_CO_NOX_Berlin-coarse_2015010110.nc"
output_path = "./output_CHE/"
output_name = "Europe_CHE_"
prof_path = "./input_profiles_CHE/"
rlon = 760+4
rlat = 610+4
# TESTING
# rlon = 10
# rlat = 10

var_list= []
for (s,nfr) in [(s,nfr) for s in ["CO2","CO","CH4"] for nfr in ["A","B","C","F","O","ALL"]]:
    var_list.append(s+"_"+nfr+"_E") #["CO2_ALL_E","CO2_A_E"]
catlist_prelim = [
    ["CO2_A_AREA","CO2_A_POINT"], # for CO2_A_E
    ["CO2_B_AREA","CO2_B_POINT"], # for CO2_B_E
    ["CO2_C_AREA"],               # for CO2_C_E
    ["CO2_F_AREA"],               # for CO2_F_E
    ["CO2_D_AREA","CO2_D_POINT",
     "CO2_E_AREA",
     "CO2_G_AREA",
     "CO2_H_AREA","CO2_H_POINT", 
     "CO2_I_AREA",     
     "CO2_J_AREA","CO2_J_POINT",  # for CO2_O_E
 ],
    ["CO2_A_AREA","CO2_A_POINT",
     "CO2_B_AREA","CO2_B_POINT",
     "CO2_C_AREA",
     "CO2_F_AREA",
     "CO2_D_AREA","CO2_D_POINT",
     "CO2_E_AREA",
     "CO2_G_AREA",
     "CO2_H_AREA","CO2_H_POINT", 
     "CO2_I_AREA",     
     "CO2_J_AREA","CO2_J_POINT",  # for CO2_ALL_E
],
    ["CO_A_AREA","CO_A_POINT"],   # for CO_A_E
    ["CO_B_AREA","CO_B_POINT"],   # for CO_B_E
    ["CO_C_AREA"],                # for CO_C_E
    ["CO_F_AREA"],                # for CO_F_E
    ["CO_D_AREA","CO_D_POINT",
     "CO_E_AREA",
     "CO_G_AREA",
     "CO_H_AREA","CO_H_POINT", 
     "CO_I_AREA",     
     "CO_J_AREA","CO_J_POINT",    # for CO_O_E
],
    ["CO_A_AREA","CO_A_POINT",
     "CO_B_AREA","CO_B_POINT",
     "CO_C_AREA",
     "CO_F_AREA",
     "CO_D_AREA","CO_D_POINT",
     "CO_E_AREA",
     "CO_G_AREA",
     "CO_H_AREA","CO_H_POINT", 
     "CO_I_AREA",     
     "CO_J_AREA","CO_J_POINT",    # for CO_ALL_E
],
    ["CH4_A_AREA","CH4_A_POINT"], # for CH4_A_E
    ["CH4_B_AREA","CH4_B_POINT"], # for CH4_B_E
    ["CH4_C_AREA"],               # for CH4_C_E
    ["CH4_F_AREA"],               # for CH4_F_E
    ["CH4_D_AREA","CH4_D_POINT",
     "CH4_E_AREA",
     "CH4_G_AREA",
     "CH4_H_AREA","CH4_H_POINT", 
     "CH4_I_AREA",     
     "CH4_J_AREA","CH4_J_POINT",  # for CH4_O_E
],
    ["CH4_A_AREA","CH4_A_POINT",
     "CH4_B_AREA","CH4_B_POINT",
     "CH4_C_AREA",
     "CH4_F_AREA",
     "CH4_D_AREA","CH4_D_POINT",
     "CH4_E_AREA",
     "CH4_G_AREA",
     "CH4_H_AREA","CH4_H_POINT", 
     "CH4_I_AREA",     
     "CH4_J_AREA","CH4_J_POINT", # for CH4_ALL_E
 ]
]

tplist_prelim = [
    ['GNFR_A','GNFR_A'], # for s_A_E
    ['GNFR_B','GNFR_B'], # for s_B_E
    ['GNFR_C'],          # for s_C_E
    ['GNFR_F'],          # for s_F_E
    ['GNFR_D','GNFR_D', 
     'GNFR_E',
     'GNFR_G',
     'GNFR_H','GNFR_H',
     'GNFR_I',
     'GNFR_J','GNFR_J',
     'GNFR_K',
     'GNFR_L',],         # for s_O_E
    ['GNFR_A','GNFR_A',
     'GNFR_B','GNFR_B',
     'GNFR_C',
     'GNFR_F',
     'GNFR_D','GNFR_D',
     'GNFR_E',
     'GNFR_G',
     'GNFR_H','GNFR_H',
     'GNFR_I',
     'GNFR_J','GNFR_J',
 ]          # for s_ALL_E
]
tplist_prelim *= 3
vplist_prelim = tplist_prelim

# Make sure catlist, tplist, vplist have the same shape
catlist, tplist, vplist = [], [], []
for v in range(len(var_list)):
    subcat = []
    subtp = []
    subvp = []
    for cat, tp, vp in zip(catlist_prelim[v],
                           tplist_prelim[v],
                           vplist_prelim[v]):
        subcat.append(cat)
        subtp.append(tp)
        subvp.append(vp)
    catlist.append(subcat)
    tplist.append(subtp)
    vplist.append(subvp)


###########


levels = 7  # Removed if-statement in inner loop
# apply_prof = True  # Removed if-statement in inner loop

# catlist = ['CO2_01_POINT','CO2_02_AREA','CO2_34_AREA','CO2_34_POINT','CO2_05_AREA','CO2_05_POINT','CO2_06_AREA','CO2_07_AREA','CO2_08_AREA','CO2_08_POINT','CO2_09_AREA','CO2_09_POINT','CO2_10_AREA']
# tplist = ['CO2_1','CO2_2','CO2_4','CO2_4','CO2_5','CO2_5','CO2_6','CO2_7','CO2_8','CO2_8','CO2_9','CO2_9','CO2_10']
# vplist = ['SNAP-1','SNAP-2','SNAP-4','SNAP-4','SNAP-5','SNAP-5','SNAP-6','SNAP-7','SNAP-8','SNAP-8','SNAP-9','SNAP-9','SNAP-10']

dow = nc.Dataset(prof_path + "dayofweek.nc")
hod = nc.Dataset(prof_path + "hourofday.nc")
moy = nc.Dataset(prof_path + "monthofyear.nc")
ver  = nc.Dataset(prof_path + "vertical_profiles.nc")

start_date = datetime.date(2015, 1, 1)
end_date = datetime.date(2015, 1, 7)

name_template = output_path + output_name + "%Y%m%d%H.nc"

with nc.Dataset(path_emi) as emi:
    # Time- and (grid-country-mapping)-independent data
    print("Extracting emissions and vertical profiles...")
    emi_mats = extract_matrices(infile = emi,
                                var_list = catlist,
                                indices = np.s_[:])

    ver_mats = extract_matrices(infile = ver,
                                var_list = vplist,
                                indices = np.s_[:],
                                transform = (
                                    lambda x: np.reshape(x,(levels, 1, 1))))

    # Mapping country_ids (from emi) to country-indices (from moy)
    # Assuming that the order in moy, hod and dow is the same
    print("Creating gridpoint -> index mapping...")
    emigrid_to_index = country_id_mapping(
        moy['country'][:], emi['country_ids'][:])
    val_on_emigrid = lambda x: extract_to_grid(emigrid_to_index, x)

    # Time dependent data
    # Need only 1 month
    print("Extracting month-profile...")
    assert start_date.month == end_date.month
    month_id  = start_date.month - 1 
    moy_mats = extract_matrices(infile = moy,
                                var_list = tplist,
                                indices = np.s_[month_id, :],
                                transform = val_on_emigrid)

    print("Extracting day-profile...")
    dow_mats = [extract_matrices(infile = dow,
                                 var_list = tplist,
                                 indices = np.s_[day_of_week, :],
                                 transform = val_on_emigrid)
                for day_of_week in range(7)]  # always extract whole week
    # List of dicts (containing 2D matrices) is not ideal, but I'm
    # too lazy atm to change it (dict of 3D matrices would be better)
    print("Extracting hour-profile...")
    hod_mats = [extract_matrices(infile = hod,
                                 var_list = tplist,
                                 indices = np.s_[hour, :],
                                 transform = val_on_emigrid)
                for hour in range(24)]

    for day in daterange(start_date, end_date):
        start = time.time()
        for hour in range(24):
            day_hour = datetime.datetime.combine(day, datetime.time(hour))
            print(day_hour.strftime("Processing %D, %H:%M"))
            of_name = day_hour.strftime(name_template)
            with nc.Dataset(of_name, "w") as of:
                with nc.Dataset(path_org) as org:
                    write_metadata(outfile = of,
                                   org_file = org,
                                   emi_file = emi,
                                   ver_file = ver,
                                   variables = var_list)

                for v, var in enumerate(var_list):
                    oae_vals = np.zeros((levels, rlat, rlon))
                    for cat, tp, vp in zip(catlist[v],
                                           tplist[v],
                                           vplist[v]):
                        emi_mat = emi_mats[cat]
                        hod_mat = hod_mats[hour][tp]
                        dow_mat = dow_mats[day.weekday()][tp]
                        moy_mat = moy_mats[tp]
                        ver_mat = ver_mats[vp]

                        oae_vals += emi_mat * hod_mat * dow_mat * moy_mat * ver_mat
                    # Careful, automatic reshaping!
                    of[var][0,:] = oae_vals

        stop = time.time()
        print("Processed day {} in {}"
              .format(day, stop-start))
