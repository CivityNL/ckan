=======================================
PostGIS functions in data store queries
=======================================

.. sectnum::

.. contents:: The tiny table of contents

Introduction
~~~~~~~~~~~~

Using the CKAN data store API, queries against data in the CKAN data store can be executed. 
It is possible to use some PostGIS functions in those queries. This document describes which 
functions can be used and provides examples on how to use them. 

To convert to text formats
~~~~~~~~~~~~~~~~~~~~~~~~~~
  
- ST_ASEWKT - Well Known Text, with CRS information. See https://postgis.net/docs/ST_AsEWKT.html
- ST_ASGEOJSON - GeoJSON. See https://postgis.net/docs/ST_AsGeoJSON.html
- ST_ASGML - GML. See https://postgis.net/docs/ST_AsGML.html
- ST_ASTEXT - Well Known Text, without CRS information. See https://postgis.net/docs/ST_AsText.html

To select different representations of the geometries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ST_BUFFER. See https://postgis.net/docs/ST_Buffer.html
- ST_CENTROID. See https://postgis.net/docs/ST_Centroid.html
- ST_CLOSESTPOINT. See https://postgis.net/docs/ST_ClosestPoint.html

Overlays to be able to join tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ST_CONTAINS. See https://postgis.net/docs/ST_Contains.html
- ST_COVERS. See https://postgis.net/docs/ST_Covers.html
- ST_DFULLYWITHIN. See https://postgis.net/docs/ST_DFullyWithin.html
- ST_DWITHIN. See https://postgis.net/docs/ST_DWithin.html
- ST_INTERSECTS. See https://postgis.net/docs/ST_Intersects.html
- ST_UNION. See https://postgis.net/docs/ST_Union.html
- ST_WITHIN. See https://postgis.net/docs/ST_Within.html

To be able to create geometries to be used in overlays
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ST_GEOMFROMEWKT. Create geometry from Well Known Text (WKT) with spatial reference information. See https://postgis.net/docs/ST_GeomFromEWKT.html
- ST_GEOMFROMGEOJSON. Create geometry from GeoJSON. See https://postgis.net/docs/ST_GeomFromGeoJSON.html
- ST_GEOMFROMGML. Create geometry from Geography Markup Language (GML). See https://postgis.net/docs/ST_GeomFromGML.html
- ST_GEOMFROMTEXT. Create geometry from Well Known Text (WKT). See https://postgis.net/docs/ST_GeomFromText.html
- ST_SETSRID. Geometries created using the ST_GEOMFROMGEOJSON and ST_GEOMFROMTEXT functions will not have spatial reference information (EPSG code). As a consequence, spatial queries will fail due to a mismatch between the coordinate reference systems. Use this function to attach an EPSG code to the geometry. See https://postgis.net/docs/ST_SetSRID.html. 
- ST_TRANSFORM. To transform geometries from one coordinate reference system to another to avoid a mismatch between coordinate reference systems when doing overlays. See https://postgis.net/docs/ST_Transform.html. 
  
Examples
~~~~~~~~

