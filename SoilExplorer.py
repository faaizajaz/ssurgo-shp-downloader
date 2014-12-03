#####################################################
##############Soil Explorer Module###################
#####################################################

from math import cos, radians
from bs4 import BeautifulSoup
from mechanize import Browser, URLError
import threading, arcpy
import time

class AreaOfInterest:
	#Constructor takes two (lon,lat) pairs that make up AOI bounding box and resolution (meters)
	def __init__(self, lon1, lat1, lon2, lat2, res):
		# Assign arguments to instance references
		self.lon1 = lon1
		self.lat1 = lat1
		self.lon2 = lon2
		self.lat2 = lat2
		self.res = res
		# Set anchor point for AOI (choose lowest of each lon and lat)
		self.anchorLon = self.lon2 if self.lon1 > self.lon2 else self.lon1
		self.anchorLat = self.lat2 if self.lat1 > self.lat2 else self.lat1
		# Flag to prevent dividing an AOI twice. Set to True after Divide() method called
		self.hasDivided = False
		# Create list to store Cells
		self.areaList = []
		self.Divide()
		self.numErrorCells = 0

	# This method divides the AOI into Cell objects based on the resolution specified in AOI constructor
	def Divide(self):
		print "Dividing..."
		div_start = time.time()
		midLat = ((abs(self.lat1) + abs(self.lat2)) / 2.0)
		# Check AOI hasDivided flag
		if self.hasDivided == False:
			self.hasDivided = True # Set flag to True
			lonDistMeters, latDistMeters = ConvertToEucDist(self, midLat) # Get meter value for coordinates
			# Determine the X and Y ranges of the AOI (in terms of Cells of side res) and add one for partials
			lonRange = (lonDistMeters / self.res) + 1
			latRange = (latDistMeters / self.res) + 1

			# Set current lon, lat to respective anchors (origin)
			currLon = self.anchorLon
			currLat = self.anchorLat
			# First populate areaList with all cells in given latitude
			for lat in range(0, int(latRange)):
				currLon = self.anchorLon # Set current lon to anchorLon (X origin)
				# For given latitude, iter across all Cells
				for lon in range(0, int(lonRange)):
					# Populate current Cell's coordinate attributes (bounding box)
					self.areaList.append(Cell(currLon, currLat, currLon + ConvertToDegs(self.res, "lo", midLat), currLat + ConvertToDegs(self.res, "la", midLat)))
					# Increment current lon by converting degree subdivision (res) to meter
					currLon += ConvertToDegs(self.res, "lo", midLat)
				# Increment current lat by converting degree subdivision (res) to meter
				currLat += ConvertToDegs(self.res, "la", midLat)
			# Test message to confirm division
			print "Division successful"
			div_time = time.time() - div_start
			print str(div_time) + " seconds"
			return None
		# TODO Catch an exception here
		# If already divided, give an error message
		else:
			print "Already divided (hasDivided == true)"
			return None

	# This method allows User to get soil data for AOI and specify number of threads for API calls
	def MakeSoilData_multi(self, numThreads):
		print "Getting soil data..."
		soil_start = time.time()

		threadCount = 0 # Keeps count of how many Cells have been assigned to threads
		threads = [] # list for holding threads
		for i in range(numThreads):
			#TODO improve to avoid extra n records on the last Cell block
			# If the current Cell block is any EXCEPT the LAST one
			if i < (numThreads - 1):
				cellsPerThread = len(self.areaList) / numThreads # Cells per thread is simple division
				threadCount += cellsPerThread # increment count of assigned Cells
				# Set min and max (indexes) for current thread
				min = i * cellsPerThread
				max = min + cellsPerThread
			# If the current Cell block is the LAST one
			elif i == (numThreads - 1):
				min = i * cellsPerThread # min index assigned as usual
				cellsPerThread = len(self.areaList) - threadCount # cells per thread = (total cells - already assigned)
				max = min + cellsPerThread #assign max
			# Create a new thread, append to list
			t = threading.Thread(target=self.AddDataToCells_multi, args=(min, max))
			threads.append(t)
		# Start all threads
		for i2 in range(numThreads):
			threads[i2].start()
		# Wait for all threads to complete
		for i3 in range(numThreads):
			threads[i3].join()

		print "Cell data retrieved."
		soil_time = (time.time() - soil_start) / 60
		print str(soil_time) + " minutes."

	# This method makes the API call and adds data to the current Cell
	def AddDataToCells_multi(self, min, max):
		# Make base URL and mechanize browser
		baseUrl = "http://casoilresource.lawr.ucdavis.edu/soil_web/reflector_api/soils.php?what=mapunit&bbox="
		browser = Browser()
		# Iterate through the assigned block of Cells, make API call, store in Cell attributes

		for i in range(min, max):
			try:
				madeUrl = baseUrl + str(self.areaList[i].lon1) + "," + str(self.areaList[i].lat1) + ","+ str(self.areaList[i].lon2) + "," + str(self.areaList[i].lat2)
				browser.open(madeUrl)
				response = browser.follow_link(nr=0)
				responseData = response.get_data()
				bs = BeautifulSoup(responseData)
				soilTable = bs.findAll('table')[1]
				temp = soilTable.select(".record")[0]
				cellResult = str(temp.text)
				self.areaList[i].SetSoilProperties(cellResult)
			except URLError:
				self.areaList[i].SetSoilProperties("ERR_URL")
				self.numErrorCells += 1



	# This method creates polygons out of each Cell and creates/populates the SOILTYPE field
	def MakeFeatureClass(self):
		print "Building shapefile..."
		arc_start = time.time()


		spatial_ref = "NAD 1983"
		# Arcpy housekeeping
		arcpy.env.workspace = "D:/Faaiz/PythonProjects/SSURGO-GIS-Downloader"
		arcpy.env.overwriteOutput = True
		# Create output FC to store final result
		arcpy.CreateFeatureclass_management("/Results", "SoilCells.shp", "POLYGON", "", "", "", spatial_ref)
		# Add "SOILTYPE" field
		arcpy.AddField_management("/Results/SoilCells.shp", "SOILTYPE", "TEXT")
		# Iterate through Cells in divided area, create array of points from corner coords, make Polygon.
		for cell in self.areaList:
			pointArray = arcpy.Array()
			pointArray.add(arcpy.Point(cell.lon1, cell.lat1))
			pointArray.add(arcpy.Point(cell.lon2, cell.lat1))
			pointArray.add(arcpy.Point(cell.lon2, cell.lat2))
			pointArray.add(arcpy.Point(cell.lon1, cell.lat2))
			cellPolygon = arcpy.Polygon(pointArray, spatial_ref)
			# Add current polygon to final result FC
			arcpy.Append_management(cellPolygon, "/Results/SoilCells.shp", "NO_TEST")
		print "Done building shapefile."
		arc_time = (time.time() - arc_start) / 60 / 60
		print str(arc_time) + " hours"
		# Create update cursor for SOILTYPE field
		cursor = arcpy.da.UpdateCursor("/Results/SoilCells.shp", ['SOILTYPE'])
		# Create index variables for populating SOILTYPE field
		i = 0
		# Iterate through returned results, and update SOILTYPE to corresponding Cells soilType using index (i)
		print "Populating SOILTYPE field..."
		pop_start = time.time()

		for row in cursor:
			row[0] = self.areaList[i].soilType
			cursor.updateRow(row)
			i += 1
		# Delete cursor, row, and index
		del cursor
		del row
		del i
		print "Done populating"
		pop_time = (time.time() - pop_start) / 60
		print str(pop_time) + " minutes to populate"



class Cell:
	# Constructor takes two (lon,lat) pairs as bounding box
	def __init__(self, lon1, lat1, lon2, lat2):
		# Define and set Cell attributes
		self.lon1 = lon1
		self.lat1 = lat1
		self.lon2 = lon2
		self.lat2 = lat2
		self.soilType = None

	# This method is the setter for cell attributes
	def SetSoilProperties(self, props):
		splitProps = props.split(",")
		self.soilType = splitProps[0]
		return

# Conversions

# This function converts the dimensions of an AOI into approx distance in meters
def ConvertToEucDist(AOI, midLat):
	lonConvFactor = (111.20 * (cos(radians(midLat))))
	latConvFactor = (40030.8 / 360.0)
	lonDegs = abs(AOI.lon2 - AOI.lon1)
	latDegs = abs(AOI.lat2 - AOI.lat1)
	lonDistMeters = lonDegs * lonConvFactor * 1000
	latDistMeters = latDegs * latConvFactor * 1000
	return (lonDistMeters, latDistMeters)

# This function converts a distance (x or y) value at given latitude to DDS
def ConvertToDegs(dist, key, midLat):
	# Key specifies trying to convert lat or lon (la or lo)
	if key == "lo":
		degs = (dist / 1000.0) * (1 / (111.20 * cos(midLat)))
		return degs
	elif key == "la":
		degs = (dist / 1000.0) * (360.0 / 40030.8)
		return degs
	else:
		print "Couldn't call SoilExplorer.ConvertToDegs"
		return None

