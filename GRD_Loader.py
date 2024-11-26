# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GrdLoader
                                 A QGIS plugin
 Load GRD Format Rasters
 Generated by Plugin Builder: http:#g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-05-11
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Mark Jessell
        email                : mark.jessell@uwa.edu.au
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QLineEdit
from qgis.core import QgsRasterLayer, QgsCoordinateReferenceSystem
from qgis.core import Qgis

import numpy as np
from osgeo import gdal, osr
import struct
import zlib
import os
import ntpath
from .geosoft_grid_parser import * 

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .GRD_Loader_dialog import GrdLoaderDialog
import os.path


class GrdLoader:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = str(QSettings().value('locale/userLocale'))[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GrdLoader_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
            
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&GRD_Loader')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('GrdLoader', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/GRD_Loader/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'GRD Loader'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(
                self.tr(u'&GRD_Loader'),
                action)
            self.iface.removeToolBarIcon(action)

    # select grd file and attempt to extract CRS from xml file
    def select_input_file(self):
        filename, _filter = QFileDialog.getOpenFileName(
            self.dlg, "Select input file ","", '*.grd *.GRD')
        self.dlg.lineEdit.setText(filename)
        epsg=4326
        if(os.path.exists(filename+'.xml')):
            epsg=extract_proj_str(filename+'.xml')
            if(epsg== None):
                epsg=4326
                self.iface.messageBar().pushMessage("No CRS found in XML, default to 4326", level=Qgis.Warning, duration=15)
            else:
                self.iface.messageBar().pushMessage("CRS Read from XML as "+str(epsg), level=Qgis.Info, duration=15)
        self.dlg.mQgsProjectionSelectionWidget.setCrs(QgsCoordinateReferenceSystem('EPSG:'+str(epsg)))
        return (epsg)

    #load grd file
    def load_a_grid(self,proj):
        file_path = self.dlg.lineEdit.text()

        #check if projection is valid
        if(proj.isValid()):
            epsg = proj.authid().split(':')[1]
        else:
            epsg = 4326
            self.iface.messageBar().pushMessage("No CRS Defined, assumed to be 4326", level=Qgis.Warning, duration=15)

        #load grd file and store in memory
        if(file_path !=''): 
            if(not os.path.exists(file_path)):
                self.iface.messageBar().pushMessage("File: "+file_path+" not found", level=Qgis.Warning, duration=3)
            else:    
                grid,header,Gdata_type=load_oasis_montaj_grid_optimized(file_path)
                                
                path,name=ntpath.split(file_path)
                fn='/vsimem/'+name[:-4]+'.tif'

                driver=gdal.GetDriverByName('GTiff')
                if(header["ordering"]==1):
                    ds = driver.Create(fn,xsize=header["shape_e"],ysize=header["shape_v"],bands=1,eType=Gdata_type)
                else:
                    ds = driver.Create(fn,xsize=header["shape_v"],ysize=header["shape_e"],bands=1,eType=Gdata_type)

                ds.GetRasterBand(1).WriteArray(grid)
                geot=[header["x_origin"]-(header["spacing_e"]/2),
                    header["spacing_e"],
                    0,
                    header["y_origin"]-(header["spacing_v"]/2),
                    0,
                    header["spacing_e"],
                    ]
                ds.SetGeoTransform(geot)
                srs=osr.SpatialReference()
                #ds.SetProjection(srs.ExportToWkt())
                ds=None
                rlayer=self.iface.addRasterLayer(fn)
                rlayer.setCrs( QgsCoordinateReferenceSystem('EPSG:'+str(epsg) ))
                self.iface.messageBar().pushMessage("GRD file loaded as layer in memory, use export to save as file", level=Qgis.Success, duration=5)

        else:
            self.iface.messageBar().pushMessage("You need to select a file first", level=Qgis.Warning, duration=3)
    
    def define_tips(self):
        Path_tooltip = '<p>Path to Geosoft Binary Grid</p>'
        Epsg_tooltip = '<p>Coordinate Reference System , leave blank for default of EPSG:4326 or if XML file available</p>'
        self.dlg.lineEdit.setToolTip(Path_tooltip)
        self.dlg.pushButton.setToolTip(Path_tooltip)
        self.dlg.mQgsProjectionSelectionWidget.setToolTip(Epsg_tooltip)


    def run(self):
        from qgis.gui import QgsProjectionSelectionWidget
        """Run method that performs all the real work"""


        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = GrdLoaderDialog()
            epsg=self.dlg.pushButton.clicked.connect(self.select_input_file)
            self.dlg.mQgsProjectionSelectionWidget.setCrs(QgsCoordinateReferenceSystem('EPSG:'+str(epsg)))
        self.define_tips()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            proj=self.dlg.mQgsProjectionSelectionWidget.crs()
            self.load_a_grid(proj)    

# from https://geosoftgxdev.atlassian.net/wiki/spaces/GXDEV92/pages/54833854/Grid+File+Name+Decorations
#--------------------------------------------------------------------------
# GRD   Geosoft grid file
#
#    TYPE=    data type for new files: SHORT   2-byte signed integer
#                                      LONG    4-byte signed integer
#                                      FLOAT   4-byte floating point
#                                      DOUBLE  8-byte floating point
#                                      COLOR   4-byte RGBd colour
#                                      RGB     4-byte RGB, no dummy
#
#             If not specified, the TYPE parameter in the [DAT_GRD]
#             section of "DAT Setting" in the global settings is used.
#
#    For color grids, each grid element is 4-bytes, first byte red, second
#    byte green, third byte blue, and the fourth byte is a dummy flag.  If
#    the dummy flag is 0, the cell is transparent, otherwise the cell
#    should be coloured.  The following parameters are also meaningful
#    for color grids:
#
#    BAND=R      Red    band only
#    BAND=G      Green  band only
#    BAND=B      Yellow band only
#    BRT=        Brightness, 0.0 -> 2.0 (black -> white), default is BRT=1.0
#                This only works for colour grids.
#    DUMMY=r,g,b Dummy colour. Default is DUMMY=255,255,255 (white).
#                To disable dummy colour, enter "DUMMY=".
#    PIXEL=0     Continuous function data (default), displays smoothly
#    PIXEL=1     Pixel data, displays as grid cells.
#
# Compression:
#
#    COMP=NONE   Default - no compression of data.
#    COMP=SPEED  Compress grid data. Faster compression than "SIZE", but
#                produces a larger grid file.
#    COMP=SIZE   Compress grid data. Compresses better than "SPEED", but
#                takes longer.
#
#                Compression ratios can be improved by stripping insignificant
#                bits from the floating-point mantisa.  You can control this
#                by appending the numver of mantisa bits required to the
#                COMP=SIZE string.  For example, COMP=SIZE12 will produce
#                data to between 3 and 4 significant figures and achieve
#                much better compression.
#
#                  Mantisa   Significant  
#                  Bits      Figures   
#                  4         1         
#                  7         2         
#                  10        3         
#                  14        4         
#                  17        5         
#                  20        6         
#                  23        almost 7  (this is the maximum)
#                                 
#
# GEOSOFT.INI section
#
#    [DAT_GRD]
#    BROWSE_IN="GRD"
#    BROWSE_OUT="GRD"
#               "GRD;Type=Byte"
#               "GRD;Type=Short"
#               "GRD;Type=Long"
#               "GRD;Type=Float"
#               "GRD;Type=Color"