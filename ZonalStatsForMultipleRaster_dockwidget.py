# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ZonalStatsForMultipleRasterDockWidget
                                 A QGIS plugin
 This plugin computes zonal stat for multiple raster files
                             -------------------
        begin                : 2017-05-01
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Ana del Campo Sánchez
        email                : delcampoana@gmail.com
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

import os,sys,shutil,re,subprocess
reload(sys)
sys.setdefaultencoding("utf-8")
import constants
# from ZonalStatsForMultipleRaster_loadData import *
from PyQt4 import QtGui, uic
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
# from processing.core.Processing import Processing
# Processing.initialize()
# from processing.tools import *
import processing
from qgis.analysis import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ZonalStatsForMultipleRaster_dockwidget_base.ui'))

class ZonalStatsForMultipleRasterDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface,parent=None):
        """Constructor."""
        super(ZonalStatsForMultipleRasterDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.iface = iface
        self.initialize()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def initialize(self):
        aux_path_plugin = 'python/plugins/' + constants.CONST_NAME
        qgisUserDbFilePath = QgsApplication.qgisUserDbFilePath()
        self.path_plugin = os.path.join(QFileInfo(QgsApplication.qgisUserDbFilePath()).path(),aux_path_plugin)
        path_file_qsettings = self.path_plugin + '/' +constants.CONST_SETTINGS_FILE_NAME
        self.settings = QSettings(path_file_qsettings,QSettings.IniFormat)
        self.lastPath = self.settings.value("last_path")
        if not self.lastPath:
            self.lastPath = QDir.currentPath()
            self.settings.setValue("last_path",self.lastPath)
            self.settings.sync()
        self.iface.mapCanvas().mapRenderer().setProjectionsEnabled(True)
        self.backupPushButton.setEnabled(False)
        self.statsPushButton.setEnabled(False)
        QObject.connect(self.loadPushButton, SIGNAL("clicked(bool)"), self.loadDataProcess)
        QObject.connect(self.backupPushButton, SIGNAL("clicked(bool)"), self.createBackupProcess)
        QObject.connect(self.statsPushButton, SIGNAL("clicked(bool)"), self.calculateStatsProcess)
        self.num_format = re.compile(r'^\-?[1-9][0-9]*\.?[0-9]*')
        self.textBrowser.setText('> Load your input folder. The current loaded layers will be CLOSED')

    def loadDataProcess(self):
        title = "Select input folder"
        self.inputFolder = QFileDialog.getExistingDirectory(self, title, self.lastPath)
        inputFileListFull = os.listdir(self.inputFolder)
        self.rasterFileList = []
        for file in inputFileListFull:
            if os.path.splitext(file)[1] == '.tif' or '.jpg' in file:
                self.rasterFileList.append(file)
        if (len(inputFileListFull) == 0) or (len(self.rasterFileList) == 0):
            self.textBrowser.append('> There is no TIF or JPG files in this folder. Load your input folder again')
            return
        self.textBrowser.append('> ' + self.inputFolder)
        self.textBrowser.append('> %s raster files loaded'%(len(self.rasterFileList)))
        self.loadPushButton.setEnabled(False)
        self.backupPushButton.setEnabled(True)
        self.statsPushButton.setEnabled(True)
        self.crs = QgsCoordinateReferenceSystem(25830, QgsCoordinateReferenceSystem.PostgisCrsId)
        self.iface.newProject()
        QgsProject.instance().layerTreeRoot().removeAllChildren()
        QgsMapLayerRegistry.instance().removeAllMapLayers()
        for loadlayer in QgsMapLayerRegistry.instance().mapLayers().values():
            QgsMapLayerRegistry.instance().removeMapLayers([loadlayer])
        self.textBrowser.append('> Previous loaded layers removed')
        self.baseFolder = os.path.dirname(self.inputFolder)
        self.backupFolder = self.inputFolder + '_backup'
        self.backupPointFolder = self.backupFolder + '\\shp_point'
        self.processFolder = self.inputFolder + '_process'
        self.processFolderImg = self.processFolder + '\\img'
        self.processFolderTmp = self.processFolder + '\\tmp'
        self.processFolderSHPpoint = self.processFolder + '\\shp_point'
        self.processFolderSHPpolygon = self.processFolder + '\\shp_polygon'
        if os.path.isdir(self.backupFolder) is False:
            os.mkdir(self.backupFolder)
            os.mkdir(self.backupPointFolder)
        if os.path.isdir(self.processFolder) is True:
            shutil.rmtree(self.processFolder)
            os.mkdir(self.processFolder)
            os.mkdir(self.processFolderImg)
            os.mkdir(self.processFolderTmp)
            os.mkdir(self.processFolderSHPpoint)
            os.mkdir(self.processFolderSHPpolygon)
        else:
            os.mkdir(self.processFolder)
            os.mkdir(self.processFolderImg)
            os.mkdir(self.processFolderTmp)
            os.mkdir(self.processFolderSHPpoint)
            os.mkdir(self.processFolderSHPpolygon)
        inputFileList = os.listdir(self.inputFolder)
        for file in inputFileList:
            if file.endswith('.aux.xml'):
                os.remove(self.inputFolder + '\\' + file)
        pointForm = uic.loadUiType(self.path_plugin + constants.CONST_UI_POINT)
        for rasterFile in self.rasterFileList:
            self.textBrowser.append('> ' + rasterFile + ' processing...')
            self.textBrowser.update()
            img = rasterFile.split('.')[0]
            rasterInputFilePath = self.inputFolder + '\\' + rasterFile
            rasterInputLayer = QgsRasterLayer(rasterInputFilePath, rasterFile)
            rasterTmpFilePath = self.processFolderTmp + '\\' + rasterFile
            rasterFilePath = self.processFolderImg + '\\' + img + '.tif'
            groupLayer = QgsProject.instance().layerTreeRoot().insertGroup(-1, rasterFile)
            shutil.copy2(rasterInputFilePath, rasterTmpFilePath)
            processing.runalg("gdalogr:extractprojection",
                              rasterTmpFilePath,
                              True)
            rasterWldFilePath = self.processFolderTmp + '\\' + img + '.wld'
            if not QFile.exists(rasterWldFilePath):
                raise ValueError('Not exists input file:\n' + rasterWldFilePath)
            rasterWldFile = QFile(rasterWldFilePath)
            if not rasterWldFile.open(QIODevice.WriteOnly | QIODevice.Text):
                raise ValueError('Error opening output file:\n' + rasterWldFile)
            coefA = 1
            coefD = 0
            coefB = 0
            coefE = -1
            coefC = 0.5
            coefF = rasterInputLayer.height() - 0.5
            coefWorld = '%s\n%s\n%s\n%s\n%s\n%s\n' % (coefA, coefD, coefB, coefE, coefC, coefF)
            rasterWldFile.writeData(coefWorld)
            rasterWldFile.close()
            warp = "gdalwarp -q -overwrite -of GTiff -t_srs EPSG:25830 " + rasterTmpFilePath + " " + rasterFilePath
            subprocess.call(warp, shell=True)
            os.remove(rasterWldFilePath)
            rasterLayerName = os.path.basename(rasterFilePath)
            rasterLayer = QgsRasterLayer(rasterFilePath, rasterLayerName)
            rasterLayer.setCrs(self.crs)
            if not rasterLayer.isValid():
                raise ValueError('ERROR LOADING RASTER FILE')
            QgsMapLayerRegistry.instance().addMapLayer(rasterLayer, False)
            groupLayer.insertLayer(0, rasterLayer)
            self.iface.legendInterface().setLayerVisible(rasterLayer, False)
            pointFilePath = self.processFolderSHPpoint + '\\' + img + '_point.shp'
            pointLayerName = os.path.basename(pointFilePath)
            pointLayerMem = QgsVectorLayer(
                "Point?crs=EPSG:25830&field=id_num:integer&field=id_name:string&field=img:string&field=feature1:string&field=feature2:string&field=feature3:string&field=radius:integer&index=yes",
                pointLayerName, "memory")
            QgsVectorFileWriter.writeAsVectorFormat(pointLayerMem, pointFilePath, "utf-8", None, "ESRI Shapefile")
            pointLayer = QgsVectorLayer(pointFilePath, pointLayerName, "ogr")
            if not pointLayer.isValid():
                raise ValueError('ERROR LOADING VECTOR FILE')
            QgsMapLayerRegistry.instance().addMapLayer(pointLayer, False)
            groupLayer.insertLayer(0, pointLayer)
            QgsProject.instance().layerTreeRoot().findLayer(pointLayer.id()).setCustomProperty("showFeatureCount", True)
            self.iface.legendInterface().setLayerVisible(pointLayer, False)
            pointLayer.loadNamedStyle(self.path_plugin + constants.CONST_QML_POINT)
            pointLayer.setEditForm(self.path_plugin + constants.CONST_UI_POINT)
            if os.path.isfile(self.processFolderSHPpoint + '\\' + img + '_point.cpg') == True:
                os.remove(self.processFolderSHPpoint + '\\' + img + '_point.cpg')
            if os.path.isfile(self.processFolderSHPpoint + '\\' + img + '_point.qpj') == True:
                os.remove(self.processFolderSHPpoint + '\\' + img + '_point.qpj')
            pointBackupFile = self.backupPointFolder + '\\' + img + '_point.shp'
            if os.path.isfile(pointBackupFile):
                self.iface.legendInterface().setLayerVisible(pointLayer, False)
                pointBackupLayerName = os.path.basename(pointBackupFile) + '_backup'
                pointBackupLayer = QgsVectorLayer(pointBackupFile, pointBackupLayerName, "ogr")
                if not pointBackupLayer.isValid():
                    raise ValueError('ERROR LOADING VECTOR BACKUP FILE')
                feats = [feat for feat in pointBackupLayer.getFeatures()]
                pointLayer.dataProvider().addFeatures(feats)
                pointLayer.updateFields()
                pointBackupFile = ''
                pointBackupLayer = ''
        inputFileList = os.listdir(self.inputFolder)
        for file in inputFileList:
            if file.endswith('.aux.xml'):
                os.remove(self.inputFolder + '\\' + file)
        tmpFileList = os.listdir(self.processFolderTmp)
        for file in tmpFileList:
            if file.endswith('.aux.xml'):
                os.remove(self.processFolderTmp + '\\' + file)
        self.iface.zoomFull()
        self.textBrowser.append('> Load Data DONE. Edit point layers')

    def createBackupProcess(self):
        for file in os.listdir(self.processFolderSHPpoint):
            srcFilePath = self.processFolderSHPpoint + '\\' + file
            dstFilePath = self.backupPointFolder + '\\' + file
            shutil.copy2(srcFilePath, dstFilePath)
        self.textBrowser.append('> Point back up DONE')

    def calculateStatsProcess(self):
        buffer = 5
        loadedLayersList = [layer for layer in QgsMapLayerRegistry.instance().mapLayers()]
        for layer in loadedLayersList:
            if '_polygon' in layer:
                QgsMapLayerRegistry.instance().removeMapLayer(layer)
        if os.path.isdir(self.processFolderSHPpolygon) == True:
            shutil.rmtree(self.processFolderSHPpolygon)
            os.mkdir(self.processFolderSHPpolygon)
        loadedGroupsNameList = [group.name() for group in QgsProject.instance().layerTreeRoot().children()]
        for groupName in self.rasterFileList:
            if not groupName in loadedGroupsNameList:
                QgsProject.instance().layerTreeRoot().insertGroup(-1, groupName)
        for rasterFile in self.rasterFileList:
            self.textBrowser.append('> %s processing...' %(rasterFile))
            img = QFileInfo(rasterFile).baseName()
            pointFile = self.processFolderSHPpoint + '\\' + img + '_point.shp'
            pointLayerName = os.path.basename(pointFile)
            pointLayer = QgsMapLayerRegistry.instance().mapLayersByName(pointLayerName)[0]
            pointLayer.startEditing()
            for feat in pointLayer.getFeatures():
                pointLayer.changeAttributeValue(feat.id(), 2, img)
            fieldNames = []
            id_nameList = []
            for feat in pointLayer.getFeatures():
                prov = pointLayer.dataProvider()
                fields = feat.fields()
                fieldNames = [prov.fields().field(2).name(), prov.fields().field(3).name(), prov.fields().field(4).name(),
                              prov.fields().field(5).name()]
                id_nameAtt = ''
                for fieldName in fieldNames:
                    attributeValue = feat.attribute(fieldName)
                    if attributeValue == ("" or NULL):
                        self.textBrowser.append('> Complete every feature for de layer: %s' % (pointLayerName))
                        pointLayer.commitChanges()
                        raise ValueError('Quedan atributos sin completar en la capa %s' % (pointLayerName))
                    id_nameAtt = id_nameAtt + '_' + attributeValue
                borrar, id_nameAtt = id_nameAtt.split('_', 1)
                id_nameList.append(id_nameAtt)
                pointLayer.changeAttributeValue(feat.id(), 1, id_nameAtt)
            id_numAtt = 0
            for feat in pointLayer.getFeatures():
                id_numAtt = id_numAtt + 1
                pointLayer.changeAttributeValue(feat.id(), 0, id_numAtt)
            for feat in pointLayer.getFeatures():
                fields = feat.fields()
                field = pointLayer.dataProvider().fields().field(6).name()
                attributeValue = feat.attribute(field)
                if attributeValue == NULL:
                    pointLayer.changeAttributeValue(feat.id(), 6, buffer)
            pointLayer.commitChanges()
            self.iface.legendInterface().setLayerVisible(pointLayer, False)
            polygonFilePath = self.processFolderSHPpolygon + "\\" + img + "_polygon.shp"
            QgsGeometryAnalyzer().buffer(pointLayer, polygonFilePath, 500, False, False, 6)
            qpj = self.processFolderSHPpolygon + "\\" + img + "_polygon.qpj"
            if os.path.isfile(qpj) == True:
                os.remove(qpj)
            polygonLayerName = os.path.basename(polygonFilePath)
            polygonLayer = QgsVectorLayer(polygonFilePath, polygonLayerName, "ogr")
            if not polygonLayer.isValid():
                raise ValueError('ERROR LOADING POLYGON VECTOR FILE')
            polygonLayer.setCrs(self.crs)
            QgsMapLayerRegistry.instance().addMapLayer(polygonLayer, False)
            groupName = rasterFile
            groupLayer = QgsProject.instance().layerTreeRoot().findGroup(groupName)
            QgsProject.instance().layerTreeRoot().findGroup(groupName).insertLayer(1, polygonLayer)
            QgsProject.instance().layerTreeRoot().findLayer(polygonLayer.id()).setCustomProperty("showFeatureCount",True)
            self.iface.legendInterface().setLayerVisible(polygonLayer, False)
            polygonLayer.loadNamedStyle(self.path_plugin + constants.CONST_QML_POLYGON)
            rasterFilePath = self.processFolderImg + "\\" + img + '.tif'
            rasterLayerName = os.path.basename(rasterFilePath)
            rasterLayer = QgsMapLayerRegistry.instance().mapLayersByName(rasterLayerName)[0]
            QgsProject.instance().layerTreeRoot().findLayer(rasterLayer.id())
            rasterLayer = QgsRasterLayer(rasterFilePath, rasterLayerName)
            for band in range(rasterLayer.bandCount()):
                band = band + 1
                prefix = str(band) + '_'
                zoneStat = QgsZonalStatistics(polygonLayer,
                                              rasterFilePath,
                                              prefix,
                                              band,
                                              QgsZonalStatistics.Count | QgsZonalStatistics.Mean | QgsZonalStatistics.StDev)
                zoneStat.calculateStatistics(None)
        self.textBrowser.append('> stas file writing...')
        statsFilePath = self.processFolder + '\\stats.txt'
        statsFile = QFile(statsFilePath)
        if not statsFile.open(QIODevice.WriteOnly | QIODevice.Text):
            raise ValueError('Error opening output file:\n' + statsFile)
        processFolderSHPpolygonFullList = os.listdir(self.processFolderSHPpolygon)
        processFolderSHPpolygonList = []
        for files in processFolderSHPpolygonFullList:
            (name, extension) = os.path.splitext(files)
            if (extension == ".shp"):
                processFolderSHPpolygonList.append(name + extension)
        polygonLayerName = processFolderSHPpolygonList[0]
        polygonLayer = QgsMapLayerRegistry.instance().mapLayersByName(polygonLayerName)[0]
        fieldNames = [field.name() for field in polygonLayer.pendingFields()]
        statsFile.writeData(','.join(fieldNames) + '\n')
        for polygonLayerName in processFolderSHPpolygonList:
            polygonFilePath = self.processFolderSHPpolygon + polygonLayerName
            polygonLayer = QgsMapLayerRegistry.instance().mapLayersByName(polygonLayerName)[0]
            for feat in polygonLayer.getFeatures():
                atts = feat.attributes()
                statsFile.writeData(','.join(str(e) for e in atts) + '\n')
        statsFile.close()
        self.textBrowser.append('> %s polygon vector files processed' %(len(processFolderSHPpolygonList)))
        self.textBrowser.append('> Calculate Stats DONE')
