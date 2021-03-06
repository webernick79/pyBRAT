# -------------------------------------------------------------------------------
# Name:        iHYD
# Purpose:     Adds the hydrologic attributes to the BRAT input table
#
# Author:      Jordan
#
# Created:     09/2016
# Copyright:   (c) Jordan 2016
# Licence:     <your licence>
# -------------------------------------------------------------------------------

import arcpy
import numpy as np
import os
import sys


def main(
    in_network,
    region):

    scratch = 'in_memory'

    arcpy.env.overwriteOutput = True

    # create segid array for joining output to input network
    segid_np = arcpy.da.FeatureClassToNumPyArray(in_network, "SegID")
    segid = np.asarray(segid_np, np.int64)

    # create array for input network drainage area ("iGeo_DA")
    DA_array = arcpy.da.FeatureClassToNumPyArray(in_network, "iGeo_DA")
    DA = np.asarray(DA_array, np.float32)

    # convert drainage area (in square kilometers) to square miles
    # note: this assumes that streamflow equations are in US customary units (e.g., inches, feet)
    DAsqm = np.zeros_like(DA)
    DAsqm = DA * 0.3861021585424458

    # create Qlow and Q2
    Qlow = np.zeros_like(DA)
    Q2 = np.zeros_like(DA)

    arcpy.AddMessage("Adding Qlow and Q2 to network...")

    if region is None:
        region = 0

    # --regional curve equations for Qlow (baseflow) and Q2 (annual peak streamflow)--
    # # # Add in regional curve equations here # # #
    if float(region) == 101:  # example 1 (box elder county)
        Qlow = 0.019875 * (DAsqm ** 0.6634) * (10 ** (0.6068 * 2.04))
        Q2 = 14.5 * DAsqm ** 0.328

    elif float(region) == 102:  # example 2 (upper green generic)
        Qlow = 4.2758 * (DAsqm ** 0.299)
        Q2 = 22.2 * (DAsqm ** 0.608) * ((42 - 40) ** 0.1)

    elif float(region) == 24:  # oregon region 5
        Qlow = 0.000133 * (DAsqm ** 1.05) * (15.3 ** 2.1)
        Q2 = 0.000258 * (DAsqm ** 0.893) * (15.3 ** 3.15)

    else:
        Qlow = (1.29265*10**-20.0945) * (DAsqm ** 0.9143) * (18.0 ** 2.6626) * (4730**3.9409)
        Q2 = (1.04647*10**-3.9067) * (DAsqm ** 1.0143) * (18.0 ** 2.6456)

    # save segid, Qlow, Q2 as single table
    columns = np.column_stack((segid, Qlow, Q2))
    tmp_table = os.path.dirname(in_network) + "/ihyd_Q_Table.txt"
    np.savetxt(tmp_table, columns, delimiter = ",", header = "SegID, iHyd_QLow, iHyd_Q2", comments = "")
    ihyd_table = scratch + "/ihyd_table"
    arcpy.CopyRows_management(tmp_table, ihyd_table)

    # join Qlow and Q2 output to the flowline network
    # create empty dictionary to hold input table field values
    tblDict = {}
    # add values to dictionary
    with arcpy.da.SearchCursor(ihyd_table, ['SegID', "iHyd_QLow", "iHyd_Q2"]) as cursor:
        for row in cursor:
            tblDict[row[0]] = [row[1], row[2]]
    # populate flowline network out field
    arcpy.AddField_management(in_network, "iHyd_QLow", 'DOUBLE')
    arcpy.AddField_management(in_network, "iHyd_Q2", 'DOUBLE')
    with arcpy.da.UpdateCursor(in_network, ['SegID', "iHyd_QLow", "iHyd_Q2"]) as cursor:
        for row in cursor:
            try:
                aKey = row[0]
                row[1] = tblDict[aKey][0]
                row[2] = tblDict[aKey][1]
                cursor.updateRow(row)
            except:
                pass
    tblDict.clear()

    # delete temporary table
    arcpy.Delete_management(tmp_table)

    # check that Q2 is greater than Qlow
    # if not, re-calculate Q2 as Qlow + 0.001
    with arcpy.da.UpdateCursor(in_network, ["iHyd_QLow", "iHyd_Q2"]) as cursor:
        for row in cursor:
            if row[1] < row[0]:
                row[1] = row[0] + 0.001
            else:
                pass
            cursor.updateRow(row)

    arcpy.AddMessage("Adding stream power to network...")

    # calculate Qlow and Q2 stream power
    # where stream power = density of water (1000 kg/m3) * acceleration due to gravity (9.80665 m/s2) * discharge (m3/s) * channel slope
    # note: we assume that discharge ("iHyd_QLow", "iHyd_Q2") was calculated in cubic feet per second and handle conversion to cubic
    #       meters per second (e.g., "iHyd_QLow" * 0.028316846592
    arcpy.AddField_management(in_network, "iHyd_SPLow", "DOUBLE")
    arcpy.AddField_management(in_network, "iHyd_SP2", "DOUBLE")
    with arcpy.da.UpdateCursor(in_network, ["iGeo_Slope", "iHyd_QLow", "iHyd_SPLow", "iHyd_Q2", "iHyd_SP2"]) as cursor:
        for row in cursor:
            row[2] = (1000 * 9.80665) * row[0] * (row[1] * 0.028316846592)
            row[4] = (1000 * 9.80665) * row[0] * (row[3] * 0.028316846592)
            cursor.updateRow(row)


if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2])
