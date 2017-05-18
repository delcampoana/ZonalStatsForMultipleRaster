# ZonalStatsForMultipleRaster
It's a QGis plugin to obtain zonal statistics from multiple raster layers

![](/images/icon.jpg)
![](/images/interface.jpg)

Instrucctions:
 1. Open the plugin from within QGIS
 2. Click Load Data and choose your input folder
 3. Edit every point layer to mark where you want to calculate statistics
 4. Click Create Back Up as much as you want to save your edited point layers
 5. Click Calculate Stats when you complete the editing task
 
Be carefull with:
  - The plugin can't be closed. If you want to close it, you'll have to close QGis too.
  - The Load Data process only can be pressed once. When you'll restart QGis, the new Load Data process will consider the back up information what you saved previosly.
  - The default radius for the circle is 5 pixel.
  - The statistics calculated are count, mean and standard deviation.
  
  Contatc: delcampoana@gmail.com
