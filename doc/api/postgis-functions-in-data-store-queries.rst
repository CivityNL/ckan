=======================================
PostGIS functions in data store queries
=======================================

.. sectnum::

.. contents:: Table of contents

Introduction
~~~~~~~~~~~~

Using the CKAN data store API, queries against data in the CKAN data store can be executed. 
It is possible to use some PostGIS functions in those queries. This document describes which 
functions can be used and provides examples on how to use them. 

To convert to text formats
~~~~~~~~~~~~~~~~~~~~~~~~~~
  
- Well Known Text, with CRS information: ST_ASEWKT_.
- GeoJSON: ST_ASGEOJSON_. 
- GML: ST_ASGML_.
- Well Known Text, without CRS information: ST_ASTEXT_.

.. _ST_ASEWKT: https://postgis.net/docs/ST_AsEWKT.html
.. _ST_ASGEOJSON: https://postgis.net/docs/ST_AsGeoJSON.html
.. _ST_ASGML: https://postgis.net/docs/ST_AsGML.html
.. _ST_ASTEXT: https://postgis.net/docs/ST_AsText.html

Example: select geometry as Well Known Text and GML
---------------------------------------------------

``curl --location 'https://tst-ckan-dataplatform-nl.dataplatform.nl/api/action/datastore_search_sql?sql=SELECT ST_ASTEXT(wkb_geometry) AS wkt, ST_ASGML(wkb_geometry) AS gml FROM random_points_1024_csv limit 5'`` 

To select different representations of the geometries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ST_BUFFER_. 
- ST_CENTROID_.
- ST_CLOSESTPOINT_. 

.. _ST_BUFFER: https://postgis.net/docs/ST_Buffer.html
.. _ST_CENTROID: https://postgis.net/docs/ST_Centroid.html
.. _ST_CLOSESTPOINT: https://postgis.net/docs/ST_ClosestPoint.html

Example: select GML representation of a point, with spatial reference ID and a 1000 meter buffer
------------------------------------------------------------------------------------------------

``curl --location 'https://tst-ckan-dataplatform-nl.dataplatform.nl/api/action/datastore_search_sql?sql=SELECT ST_ASGML(ST_BUFFER(ST_SETSRID(ST_GEOMFROMTEXT('POINT(142735.75 470715.91)'), 28992), 1000)) AS buffer_geom'``

Overlays to be able to join tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ST_CONTAINS_.
- ST_COVERS_.
- ST_DFULLYWITHIN_.
- ST_DWITHIN_.
- ST_INTERSECTS_.
- ST_UNION_.
- ST_WITHIN_.

.. _ST_CONTAINS: https://postgis.net/docs/ST_Contains.html
.. _ST_COVERS: https://postgis.net/docs/ST_Covers.html
.. _ST_DFULLYWITHIN: https://postgis.net/docs/ST_DFullyWithin.html
.. _ST_DWITHIN: https://postgis.net/docs/ST_DWithin.html
.. _ST_INTERSECTS: https://postgis.net/docs/ST_Intersects.html
.. _ST_UNION: https://postgis.net/docs/ST_Union.html
.. _ST_WITHIN: https://postgis.net/docs/ST_Within.html

Example: count the number of points within each municipality
------------------------------------------------------------

``curl --location 'https://tst-ckan-dataplatform-nl.dataplatform.nl/api/action/datastore_search_sql?sql=SELECT a.gm_code, a.gm_naam, ST_ASTEXT(a.wkb_geometry) AS the_geom, AVG(b.random_amount), COUNT(b.random_amount) FROM gemeenten_2022_v2_zip AS a JOIN random_points_1024_gpkg AS b ON a.h2o %3D %27NEE%27 AND ST_INTERSECTS(a.wkb_geometry, b.wkb_geometry) GROUP BY a.gm_code, a.gm_naam, ST_ASTEXT(a.wkb_geometry)'``

To be able to create geometries to be used in overlays
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ST_GEOMFROMEWKT. Create geometry from Well Known Text (WKT) with spatial reference information. See https://postgis.net/docs/ST_GeomFromEWKT.html
- ST_GEOMFROMGEOJSON. Create geometry from GeoJSON. See https://postgis.net/docs/ST_GeomFromGeoJSON.html
- ST_GEOMFROMGML. Create geometry from Geography Markup Language (GML). See https://postgis.net/docs/ST_GeomFromGML.html
- ST_GEOMFROMTEXT. Create geometry from Well Known Text (WKT). See https://postgis.net/docs/ST_GeomFromText.html
- ST_SETSRID. Geometries created using the ST_GEOMFROMGEOJSON and ST_GEOMFROMTEXT functions will not have spatial reference information (EPSG code). As a consequence, spatial queries will fail due to a mismatch between the coordinate reference systems. Use this function to attach an EPSG code to the geometry. See https://postgis.net/docs/ST_SetSRID.html. 
- ST_TRANSFORM. To transform geometries from one coordinate reference system to another to avoid a mismatch between coordinate reference systems when doing overlays. See https://postgis.net/docs/ST_Transform.html. 

Example: create a point and set the spatial reference ID
--------------------------------------------------------

``curl --location 'https://tst-ckan-dataplatform-nl.dataplatform.nl/api/action/datastore_search_sql?sql=SELECT%20ST_SETSRID(ST_GEOMFROMTEXT(%27POINT(142735.75%20470715.91)%27)%2C%2028992)%20AS%20geom'``
