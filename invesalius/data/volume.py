#--------------------------------------------------------------------------
# Software:     InVesalius - Software de Reconstrucao 3D de Imagens Medicas
# Copyright:    (C) 2001  Centro de Pesquisas Renato Archer
# Homepage:     http://www.softwarepublico.gov.br
# Contact:      invesalius@cti.gov.br
# License:      GNU - GPL 2 (LICENSE.txt/LICENCA.txt)
#--------------------------------------------------------------------------
#    Este programa e software livre; voce pode redistribui-lo e/ou
#    modifica-lo sob os termos da Licenca Publica Geral GNU, conforme
#    publicada pela Free Software Foundation; de acordo com a versao 2
#    da Licenca.
#
#    Este programa eh distribuido na expectativa de ser util, mas SEM
#    QUALQUER GARANTIA; sem mesmo a garantia implicita de
#    COMERCIALIZACAO ou de ADEQUACAO A QUALQUER PROPOSITO EM
#    PARTICULAR. Consulte a Licenca Publica Geral GNU para obter mais
#    detalhes.
#--------------------------------------------------------------------------
import plistlib
import os

import vtk
import wx
import wx.lib.pubsub as ps

from project import Project

Kernels = { 
    "Basic Smooth 5x5" : [1.0, 1.0, 1.0, 1.0, 1.0,
                          1.0, 4.0, 4.0, 4.0, 1.0,
                          1.0, 4.0, 12.0, 4.0, 1.0,
                          1.0, 4.0, 4.0, 4.0, 1.0,
                          1.0, 1.0, 1.0, 1.0, 1.0]
}

SHADING = {
    "Default": {
        "ambient"       :0.15,
        "diffuse"       :0.9,
        "specular"      :0.3,
        "specularPower" :15,
    },

    "Glossy Vascular":{
        "ambient"       :0.15,
        "diffuse"       :0.28,
        "specular"      :1.42,
        "specularPower" :50,
    },

    "Glossy Bone": {
        "ambient"       :0.15,
        "diffuse"       :0.24,
        "specular"      :1.17,
        "specularPower" :6.98,
    },

    "Endoscopy": {
        "ambient"       :0.12,
        "diffuse"       :0.64,
        "specular"      :0.73,
        "specularPower" :50,
    }
}

PRESETS = ["Airways", "Airways II", "Bone + Skin", "Bone + Skin II", "Dark Bone",
"Gold Bone", "Skin On Blue", "Skin On Blue II", "Soft + Skin", "Soft + Skin II",
"Soft + Skin III", "Yellow Bone"]

class Volume():
    
    def __init__(self):
        self.config = None
        self.exist = None
        self.color_transfer = None
        self.opacity_transfer_func = None
        
        self.__bind_events()
        
    def __bind_events(self):
        #ps.Publisher().subscribe(self.OnLoadVolume, 'Create volume raycasting')
        ps.Publisher().subscribe(self.OnShowVolume,
                                'Show raycasting volume')
        ps.Publisher().subscribe(self.OnHideVolume,
                                'Hide raycasting volume')
        ps.Publisher().subscribe(self.SetRaycastPreset,
                                'Set raycasting preset')
        ps.Publisher().subscribe(self.SetWWWL,
                                'Set raycasting wwwl')
        ps.Publisher().subscribe(self.Refresh,
                                'Set raycasting refresh')

    def OnLoadVolume(self, pubsub_evt):
        label = pubsub_evt.data
        #self.LoadConfig(label)
        self.LoadVolume()

    def LoadConfig(self, label):
        print label
        if not label:
            label = "Skin On Blue"

            path = os.path.join("..", "presets", "raycasting",
                                label+".plist")
            label = plistlib.readPlist(path)
        self.config = label
        #print path

    def OnHideVolume(self, pubsub_evt):
        self.volume.SetVisibility(0)
        ps.Publisher().sendMessage('Render volume viewer')

    def OnShowVolume(self, pubsub_evt):
        if self.exist:
            self.volume.SetVisibility(1)
            ps.Publisher().sendMessage('Render volume viewer')
        else:
            self.LoadConfig(None)
            self.LoadVolume()
            self.exist = 1

    def SetRaycastPreset(self, pubsub_evt):
        self.LoadConfig(pubsub_evt.data)
        self.Create16bColorTable(self.scale)
        self.CreateOpacityTable(self.scale)
        self.SetShading()
        colour = self.CreateBackgroundColor()
        ps.Publisher.sendMessage('Set colour interactor', colour)

    def SetWWWL(self, pubsub_evt):
        ww, wl, n = pubsub_evt.data
        print "Setting ww, wl", ww, wl
        curve = self.config['16bitClutCurves'][n]

        p1 = curve[0]
        p2 = curve[-1]
        half = (p2['x'] - p1['x']) / 2.0
        middle = p1['x'] + half

        shiftWL = wl - middle
        shiftWW = p1['x'] + shiftWL - (wl - 0.5 * ww)

        factor = 1.0
        for n,i in enumerate(curve):
            factor = abs(i['x'] - middle) / half
            if factor < 0:
                factor = 0
            i['x'] += shiftWL
            if n < len(curve)/2.0:
                i['x'] -= shiftWW * factor
            else:
                i['x'] += shiftWW * factor

        self.Create16bColorTable(self.scale)
        self.CreateOpacityTable(self.scale)
        print curve
        ps.Publisher().sendMessage('Render volume viewer', None)

    def Refresh(self, pubsub_evt):
        self.Create16bColorTable(self.scale)
        self.CreateOpacityTable(self.scale)

#***************
    def Create16bColorTable(self, scale):
        if self.color_transfer:
            color_transfer = self.color_transfer
        else:
            color_transfer = vtk.vtkColorTransferFunction()
        color_transfer.RemoveAllPoints()
        print self.config
        curve_table = self.config['16bitClutCurves']
        color_table = self.config['16bitClutColors']
        colors = []
        for i, l in enumerate(curve_table):
            for j, lopacity in enumerate(l):
                gray_level = lopacity['x']
                r = color_table[i][j]['red']
                g = color_table[i][j]['green']
                b = color_table[i][j]['blue']

                colors.append((gray_level, r, g, b))
                color_transfer.AddRGBPoint(
                    self.TranslateScale(scale, gray_level), 
                    r, g, b)
        self.color_transfer = color_transfer

    def Create8bColorTable(self):
        color_transfer = vtk.vtkColorTransferFunction()
        color_preset = self.config['CLUT']
        p = plistlib.readPlist( os.path.join('ColorList', color_preset + '.plist'))
        r = p['Red']
        g = p['Green']
        b = p['Blue']
        colors = zip(r,g,b)
        for i,rgb in enumerate(colors):
            color_transfer.AddRGBPoint(i, *rgb)
        return color_transfer

    def CreateOpacityTable(self, scale):
        if self.opacity_transfer_func:
            opacity_transfer_func = self.opacity_transfer_func
        else:
            opacity_transfer_func = vtk.vtkPiecewiseFunction()
        opacity_transfer_func.RemoveAllPoints()
        curve_table = self.config['16bitClutCurves']
        opacities = []

        ww = self.config['ww']
        wl = self.config['wl']

        l1 = wl - ww/2.0
        l2 = wl + ww/2.0

        k1 = 0.0
        k2 = 1.0

        opacity_transfer_func.AddSegment(0, 0, 2**16-1, 0)

        for i, l in enumerate(curve_table):
            for j, lopacity in enumerate(l):
                gray_level = lopacity['x']
                #if gray_level <= l1:
                #    opacity = k1
                #elif gray_level > l2:
                #    opacity = k2
                #else:
                opacity = lopacity['y']
                opacities.append((gray_level, opacity))
                opacity_transfer_func.AddPoint(
                    self.TranslateScale(scale, gray_level), opacity)
        self.opacity_transfer_func = opacity_transfer_func

    def Create8bOpacityTable(self):
        opacity_transfer_func = vtk.vtkPiecewiseFunction()
        opacities = []

        ww = self.config['ww']
        wl = self.config['wl']

        print ww, wl

        l1 = wl - ww/2.0
        l2 = wl + ww/2.0

        k1 = 0.0
        k2 = 1.0

        opacity_transfer_func.AddPoint(0, 0)
        opacity_transfer_func.AddPoint(l1-1, 0)
        opacity_transfer_func.AddPoint(l1, 1)
        opacity_transfer_func.AddPoint(l2, 1)
        opacity_transfer_func.AddPoint(l2+1, 0)
        opacity_transfer_func.AddPoint(255, 0)

        return opacity_transfer_func

    def CreateBackgroundColor(self):
        color_background = (self.config['backgroundColorRedComponent'],
                            self.config['backgroundColorGreenComponent'],
                            self.config['backgroundColorBlueComponent'])
        return color_background


    def BuildTable():
        curve_table = p['16bitClutCurves']
        color_background = (p['backgroundColorRedComponent'],
                            p['backgroundColorGreenComponent'],
                            p['backgroundColorBlueComponent'])
        color_background = [i for i in color_background]
        opacities = []
        colors = []

        for i, l in enumerate(curve_table):
            for j, lopacity in enumerate(l):
                gray_level = lopacity['x']
                opacity = lopacity['y']

                opacities.append((gray_level, opacity))

                r = color_table[i][j]['red']
                g = color_table[i][j]['green']
                b = color_table[i][j]['blue']

                colors.append((gray_level, r, g, b))

        return colors, opacities, color_background, p['useShading']

    def SetShading(self):
        print "Shading"
        shading = SHADING[self.config['shading']]
        self.volume_properties.SetAmbient(shading['ambient'])
        self.volume_properties.SetDiffuse(shading['diffuse'])
        self.volume_properties.SetSpecular(shading['specular'])
        self.volume_properties.SetSpecularPower(shading['specularPower'])

    def LoadVolume(self):
        proj = Project()
        image = proj.imagedata

        # Flip original vtkImageData
        flip = vtk.vtkImageFlip()
        flip.SetInput(image)
        flip.SetFilteredAxis(1)
        flip.FlipAboutOriginOn()
        flip.Update()
        
        image = flip.GetOutput()


        scale = image.GetScalarRange()
        self.scale = scale

        cast = vtk.vtkImageShiftScale()
        cast.SetInput(image)
        if self.config['advancedCLUT']:
            cast.SetShift(abs(scale[0]))
            #cast.SetScale(2**16-1)
            cast.SetOutputScalarTypeToUnsignedShort()
            #scale = image.GetScalarRange()
            self.Create16bColorTable(scale)
            self.CreateOpacityTable(scale)
            cast.Update()
            image2 = cast
        else:
            cast.SetShift(abs(scale[0]))
            cast.SetScale(255.0/(scale[1] - scale[0]))
            cast.SetOutputScalarTypeToUnsignedChar()
            color_transfer = self.Create8bColorTable()
            opacity_transfer_func = self.Create8bOpacityTable()
            cast.Update()
            image2 = cast
        #cast.ClampOverflowOff()

        convolve = vtk.vtkImageConvolve()
        convolve.SetInput(image2.GetOutput())
        convolve.SetKernel5x5([i/60.0 for i in Kernels[self.config['convolutionFilters'][0]]])
        convolve.Update()

        image2 = convolve
        
        composite_function = vtk.vtkVolumeRayCastCompositeFunction()
        composite_function.SetCompositeMethodToClassifyFirst()

        gradientEstimator = vtk.vtkFiniteDifferenceGradientEstimator()
        gradientEstimator.SetGradientMagnitudeScale(1)

        volume_mapper = vtk.vtkVolumeRayCastMapper()
        #volume_mapper.AutoAdjustSampleDistancesOff()
        volume_mapper.SetInput(image2.GetOutput())
        volume_mapper.SetVolumeRayCastFunction(composite_function)
        volume_mapper.SetGradientEstimator(gradientEstimator)
        volume_mapper.IntermixIntersectingGeometryOn()
        
        #Cut Plane
        CutPlane(image2.GetOutput(), volume_mapper)
        
        #self.color_transfer = color_transfer

        volume_properties = vtk.vtkVolumeProperty()
        #volume_properties.IndependentComponentsOn()
        if self.config['useShading']:
            volume_properties.ShadeOn()
        else:
            volume_properties.ShadeOff()

        volume_properties.SetInterpolationTypeToLinear()
        volume_properties.SetColor(self.color_transfer)
        self.volume_properties = volume_properties

        try:
            volume_properties.SetScalarOpacity(self.opacity_transfer_func)
        except NameError:
            pass

        self.volume_properties = volume_properties

        volume = vtk.vtkVolume()
        volume.SetMapper(volume_mapper)
        volume.SetProperty(volume_properties)
        self.volume = volume
        
        colour = self.CreateBackgroundColor()
        ps.Publisher().sendMessage('Load volume into viewer', (volume, colour))
        

    def TranslateScale(self, scale, value):
        #if value < 0:
        #    valor = 2**16 - abs(value)
        #else:
        #    valor = value 
        return value - scale[0]
   
        
class CutPlane: 
    def __init__(self, img, volume_mapper):
        self.img = img
        self.volume_mapper = volume_mapper
        self.CreatePlane()
        self.__bind_events()
    
    def __bind_events(self):
        ps.Publisher().subscribe(self.ResetPlane,
                                'Reset Cut Plane')
        ps.Publisher().subscribe(self.EnablePlane,
                                'Enable Cut Plane')
        ps.Publisher().subscribe(self.DisablePlane,
                                'Disable Cut Plane')
            
    def CreatePlane(self):
        self.plane_widget = plane_widget = vtk.vtkImagePlaneWidget()
        plane_widget.SetInput(self.img)
        plane_widget.SetPlaneOrientationToXAxes()
        #plane_widget.SetResliceInterpolateToLinear()
        plane_widget.TextureVisibilityOff()
        #Set left mouse button to move and rotate plane
        plane_widget.SetLeftButtonAction(1)
        #SetColor margin to green
        margin_property = plane_widget.GetMarginProperty()
        margin_property.SetColor(0,0.8,0)
        #Disable cross
        cursor_property = plane_widget.GetCursorProperty()
        cursor_property.SetOpacity(0) 
        self.plane_source = plane_source = vtk.vtkPlaneSource()
        plane_source.SetOrigin(plane_widget.GetOrigin())
        plane_source.SetPoint1(plane_widget.GetPoint1())
        plane_source.SetPoint2(plane_widget.GetPoint2())
        plane_source.SetNormal(plane_widget.GetNormal())
        plane_mapper = vtk.vtkPolyDataMapper()
        plane_mapper.SetInput(plane_source.GetOutput())
        self.plane_actor = plane_actor = vtk.vtkActor()
        plane_actor.SetMapper(plane_mapper)
        plane_actor.GetProperty().BackfaceCullingOn()
        plane_actor.GetProperty().SetOpacity(0)
        plane_widget.AddObserver("InteractionEvent", self.UpdatePlane)
        ps.Publisher().sendMessage('AppendActor', self.plane_actor)
        ps.Publisher().sendMessage('Set Widget Interactor', self.plane_widget)
        plane_actor.SetVisibility(1)
        plane_widget.On() 
        self.plane = plane = vtk.vtkPlane()
        plane.SetNormal(self.plane_source.GetNormal())
        plane.SetOrigin(self.plane_source.GetOrigin())
        self.volume_mapper.AddClippingPlane(plane) 
        #Storage First Position
        self.origin = plane_widget.GetOrigin()
        self.p1 = plane_widget.GetPoint1()
        self.p2 = plane_widget.GetPoint2()
        self.normal = plane_widget.GetNormal()
        
    def UpdatePlane(self, a, b):        
        plane_source = self.plane_source
        plane_widget = self.plane_widget
        plane_source.SetOrigin(plane_widget.GetOrigin())
        plane_source.SetPoint1(plane_widget.GetPoint1())
        plane_source.SetPoint2(plane_widget.GetPoint2())
        plane_source.SetNormal(plane_widget.GetNormal())        
        self.plane_actor.VisibilityOn()
        self.plane.SetNormal(plane_source.GetNormal())
        self.plane.SetOrigin(plane_source.GetOrigin())
        ps.Publisher().sendMessage('Render volume viewer', None)
        
    def EnablePlane(self, evt_pubsub=None):
        self.plane_actor.SetVisibility(1)
        ps.Publisher().sendMessage('Render volume viewer', None)
        
    def DisablePlane(self,evt_pubsub=None):
        self.plane_actor.SetVisibility(0)
        ps.Publisher().sendMessage('Render volume viewer', None)
        
    def ResetPlane(self, evt_pubsub=None):
        plane_source = self.plane_source
        plane_widget = self.plane_widget
        plane_source.SetOrigin(self.origin)
        plane_source.SetPoint1(self.p1)
        plane_source.SetPoint2(self.p2)
        plane_source.SetNormal(self.normal)        
        self.plane_actor.VisibilityOn() 
        self.plane.SetNormal(self.normal)
        self.plane.SetOrigin(self.origin)
        ps.Publisher().sendMessage('Render volume viewer', None)     

