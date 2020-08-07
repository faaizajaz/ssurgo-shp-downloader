SSURGO-GIS-Downloader


A Python tool to download SSURGO data from the UC Davis Soil Web API

===Dependencies===

```
mechanize
BeautifulSoup
arcpy
```
===How to use===


1) Instantiate AOI:
```
  # AreaOfInterest(lon1, lat1, lon2, lat2, resolution)
  # Coordinates in DDS, resolution in meters
  a = AreaOfInterest(-120.0, 37.0, -120.05, 37.05, 1000)
```
2) Fetch soil data for AOI
```
  # MakeSoilData_multi(number-of-threads) 
  # Ideal number of threads depends on resolution and AOI size
  a.MakeSoilData_multi(25)
```  
3) Export shapefile from data
```
  a.MakeFeatureClass()
```  

===Sample test script===

```
from SoilExplorer import AreaOfInterest

a = AreaOfInterest(-120.0, 37.0, -120.05, 37.05, 50)
a.MakeSoilData_multi(200)
a.MakeFeatureClass()
print "Complete."
```
