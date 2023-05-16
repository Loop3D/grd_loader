# grd_loader 0.1   

Plugin to load a Geosoft(c) GRD format file as a temporary QGIS raster layer    
   
## Install   

Save repository to disk as a zip file. Use QGIS Plugin Manager to load directly from zip file.

## Usage   

1. Once the QGIS *grd_loader* Plugin is installed, click on the ![grd_icon](icon.png) icon from the Plugins Toolbar.   
2. From here you can search for a GRD format file and load it as a raster grid.   
3. If this GRD has an associated xml file:
<space><space><space><space>*<space>you can then just click on the OK button to load the grid. 
<space><space><space><space>*<space>if not, manually enter the numeric EPSG code (e.g. *4326* for WGS 84 Lat/Long), then cick on the OK button.   
4. Layers loaded with this tool are ony stored in virtual memory, so you will need to save them to file if you want a presistant copy. 

## Credits    
Plugin construction-Mark Jessell using QGIS Plugin Builder Plugin    
GRD parser- modified from Fatiando a Terra code with help from Loop Project    