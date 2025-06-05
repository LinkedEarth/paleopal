# PyLiPD SPARQL Queries Documentation

This document describes all SPARQL queries used in PyLiPD for accessing and filtering LiPD datasets from the RDF graph.

## Dataset Metadata Queries

### QUERY_DSNAME
Description:

This query retrieves basic dataset identification information.
* Filters for all entities that are of type Dataset
* Returns the name of each dataset in the graph

```sparql
SELECT ?dsname WHERE {
    ?ds a le:Dataset .
    ?ds le:hasName ?dsname
}
```

### QUERY_DSID
Description:

This query retrieves all dataset identifiers from the database.
* Filters for all entities that are of type Dataset
* Returns the dataset ID for each dataset if available (optional field)

```sparql
SELECT ?dsid WHERE {
    ?ds a le:Dataset .
    OPTIONAL{?ds le:hasDatasetId ?dsid}
}
```

### QUERY_BIBLIO
Description:

This query extracts comprehensive bibliographic information for all datasets.
* Filters for all entities that are of type Dataset 
* For each dataset, retrieves its associated publication information
* Extracts detailed publication metadata including authors, DOI, publication year, title, journal, etc.
* Groups authors together with "and" separators to create a standardized author string

The information returned includes:
* Dataset name
* Publication title
* List of author names
* DOI
* Publication year
* Journal name
* Volume, issue, and page information
* Publication type and publisher
* Additional citation information (cite key, edition, institution, URLs)

```sparql
SELECT ?dsname ?title (GROUP_CONCAT(?authorName;separator=" and ") as ?authors) 
?doi ?pubyear ?year ?journal ?volume ?issue ?pages ?type ?publisher ?report ?citeKey ?edition ?institution ?url ?url2
WHERE { 
    ?ds a le:Dataset .
    ?ds le:hasName ?dsname .
    ?ds le:hasPublication ?pub .
    OPTIONAL{?pub le:hasDOI ?doi .}
    OPTIONAL{
        ?pub le:hasAuthor ?author .
        ?author le:hasName ?authorName .
    }
    OPTIONAL{?pub le:publicationYear ?pubyear .}
    OPTIONAL{?pub le:hasYear ?year .}
    OPTIONAL{?pub le:hasTitle ?title .}
    OPTIONAL{?pub le:hasJournal ?journal .}
    OPTIONAL{?pub le:hasVolume ?volume .}
    OPTIONAL{?pub le:hasIssue ?issue .}
    OPTIONAL{?pub le:hasPages ?pages .}
    OPTIONAL{?pub le:hasType ?type .}
    OPTIONAL{?pub le:hasPublisher ?publisher .}
    OPTIONAL{?pub le:hasReport ?report .}
    OPTIONAL{?pub le:hasCiteKey ?citeKey .}
    OPTIONAL{?pub le:hasEdition ?edition .}
    OPTIONAL{?pub le:hasInstitution ?institution .}
    OPTIONAL{?pub le:hasLink ?url .}
    OPTIONAL{?pub le:hasUrl ?url2 .}
}
GROUP BY ?pub ?dsname ?title ?doi ?year ?pubyear ?journal ?volume ?issue ?pages ?type ?publisher ?report ?citeKey ?edition ?institution ?url ?url2
```

### QUERY_LOCATION
Description:

This query retrieves geographic coordinates for paleoclimate datasets.
* Filters for datasets matching a specific name pattern (if dsname parameter is provided)
* Extracts location information using linkedearth properties

The information returned includes:
* Dataset name
* Latitude (geo_meanLat)
* Longitude (geo_meanLon)
* Elevation (geo_meanElev)

```sparql
PREFIX le: <http://linked.earth/ontology#>

SELECT ?dataSetName ?lat ?lon ?elev WHERE {
    ?ds a le:Dataset .
    ?ds le:hasName ?dataSetName .
    FILTER regex(?dataSetName, "[dsname].*", "i").
    
    ?ds le:hasLocation ?loc .
    ?loc le:hasLatitude ?lat .
    ?loc le:hasLongitude ?lon .
    OPTIONAL {?loc le:hasElevation ?elev}
}
```

## Variable Queries

### QUERY_DISTINCT_VARIABLE
Description:

This query provides a comprehensive list of all variable names used across the database.
* Filters for all entities that have both a name and a variable ID
* Returns only distinct variable names to avoid duplicates
* Used to understand what types of variables are available in the database

```sparql
PREFIX le: <http://linked.earth/ontology#>

SELECT distinct ?variableName 
WHERE {
    ?uri le:hasName ?variableName .
    ?uri le:hasVariableId ?TSID
}
```

### QUERY_DISTINCT_PROXY
Description:

This query retrieves all distinct proxy types used in the database.
* Filters for all entities that have a variable ID
* Extracts proxy information if available (optional field)
* Returns only distinct proxy types to avoid duplicates
* Used to understand what proxy measurements are available in the database

```sparql
PREFIX le: <http://linked.earth/ontology#>

SELECT distinct ?proxy 
WHERE {
    uri le:hasProxy ?proxyObj .
    ?proxyObj rdfs:label ?proxy .
}
```


### QUERY_VARIABLE_PROPERTIES
Description:

This query retrieves all property types used to describe variables in the database.
* Checks for variables in both paleoclimate data tables and chronology data tables
* Returns only distinct property types to avoid duplicates
* Used to understand what types of metadata are available for variables

```sparql
PREFIX le: <http://linked.earth/ontology#>
SELECT  DISTINCT ?property where {
    ?ds a le:Dataset .
    {
        ?ds le:hasPaleoData ?data .
        ?data le:hasMeasurementTable ?table .
        ?table le:hasVariable ?var .
        ?var ?property ?value .
    }
    UNION
    {
        ?ds le:hasChronData ?data1 .
        ?data1 le:hasMeasurementTable ?table1 .
        ?table1 le:hasVariable ?var1 .
        ?var1 ?property ?value1 .
    }
}
```


## Ensemble Table Queries

### QUERY_ENSEMBLE_TABLE
Description:

This query provides detailed ensemble table information with flexible variable name filters.
* Filters for datasets matching a specific name pattern (if dsname parameter is provided)
* Allows custom filtering for both ensemble variables and depth variables
* Can capture methods information associated with the ensemble model

The information returned includes:
* Dataset name
* Ensemble table reference
* Variable name, values, and units (based on custom filter)
* Depth variable name, values, and units (based on custom filter)
* Table notes and methods information

```sparql
PREFIX le: <http://linked.earth/ontology#>

SELECT ?datasetName ?ensembleTable ?ensembleVariableName ?ensembleVariableValues ?ensembleVariableUnits ?ensembleDepthName ?ensembleDepthValues ?ensembleDepthUnits ?notes ?methodobj ?methods
WHERE {
    ?ds a le:Dataset .
    ?ds le:hasName ?datasetName .
    FILTER regex(?datasetName, "[dsname].*", "i").

    ?ds le:hasChronData ?chron .
    ?chron le:modeledBy ?model .
    ?model le:hasEnsembleTable ?ensembleTable .
    OPTIONAL{?ensembleTable le:hasNotes ?notes}
    
    ?ensembleTable le:hasVariable ?ensvar .
    ?ensvar le:hasName ?ensembleVariableName .
    FILTER regex(lcase(?ensembleVariableName), "[ensembleVarName].*", "i").
    ?ensvar le:hasValues ?ensembleVariableValues
    OPTIONAL{
        ?ensvar le:hasUnits ?ensembleVariableUnitsObj .
        ?ensembleVariableUnitsObj rdfs:label ?ensembleVariableUnits .
    }
    
    ?ensembleTable le:hasVariable ?ensdepthvar .
    ?ensdepthvar le:hasName ?ensembleDepthName .
    FILTER regex(lcase(?ensembleDepthName), "[ensembleDepthVarName].*", "i").
    ?ensdepthvar le:hasValues ?ensembleDepthValues .
    OPTIONAL{
        ?ensdepthvar le:hasUnits ?ensembleDepthUnitsObj .
        ?ensembleDepthUnitsObj rdfs:label ?ensembleDepthUnits .
    }
}
```

## Filter Queries

### QUERY_FILTER_GEO
Description:

This query filters datasets based on geographic boundaries (bounding box).
* Filters for datasets with location information
* Restricts results to those within specified latitude and longitude ranges
* Uses LinkedEarth properties for location data

The information returned includes:
* Dataset names that fall within the specified geographic bounds

```sparql
PREFIX le: <http://linked.earth/ontology#>

SELECT ?dsname WHERE {
    ?ds a le:Dataset .
    ?ds le:hasName ?dsname .
    ?ds le:hasLocation ?loc .
    ?loc le:hasLatitude ?lat .
    ?loc le:hasLongitude ?lon .
    FILTER ( ?lat >= [latMin] && ?lat < [latMax] && ?lon >= [lonMin] && ?lon < [lonMax] ) .
}
```


### QUERY_FILTER_ARCHIVE_TYPE_STANDARD
Description:
This query filters datasets based on archive type.
* Filters for datasets with particular archive type

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX le: <http://linked.earth/ontology#>
PREFIX le_arch: <http://linked.earth/ontology/archive#>
SELECT DISTINCT ?datasetName WHERE {
    ?dataset rdf:type le:Dataset ;
    le:hasName ?datasetName ;
    le:hasArchiveType le_arch:[archiveType]
```


### QUERY_FILTER_DATASET_NAME
Description:

This query filters datasets based on name pattern.
* Searches through all dataset names
* Uses case-insensitive regular expression matching
* Allows partial matching for flexibility in searches

The information returned includes:
* Dataset names that match the specified pattern

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX le: <http://linked.earth/ontology#>
SELECT ?dsname WHERE {
    ?ds a le:Dataset .
    ?ds le:hasName ?dsname .
    FILTER regex(?dsname, "[datasetName].*", "i")
}
```

### QUERY_FILTER_TIME
Description:

This query filters datasets based on the minimum/maximum time.
* Identifies datasets containing variables that represent temporal information (0 to 11,700 years)
* Checks that the variable spans a particular time period Holocene period (0-11,700 years BP)
* Temperature variables that have been interpreted as temperature proxies

The query handles multiple time unit systems (yr_BP, yr_CE/AD, yr_b2k, ka_BP) and performs the necessary conversions to ensure proper filtering of the time period. 

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX le: <http://linked.earth/ontology#>
PREFIX pvar: <http://linked.earth/ontology/paleo_variables#>
PREFIX punits: <http://linked.earth/ontology/paleo_units#>
SELECT DISTINCT ?datasetName ?min_time ?max_time WHERE {

    ?dataset rdf:type le:Dataset .
    ?dataset le:hasName ?datasetName .

    # Find datasets with time variables that may fall within the period
    ?dataset le:hasPaleoData ?paleoData_time .
    ?paleoData_time le:hasMeasurementTable ?dataTable_time .
    ?dataTable_time le:hasVariable ?variable_time .

    # Look for variables that represent time/age
    {
        # Option 1: Variables with standard time/age variables
        ?variable_time le:hasStandardVariable ?stdVar .
        FILTER(?stdVar IN (pvar:age, pvar:year))
    }
    UNION
    {
        # Option 2: Variables with names indicating time
        ?variable_time rdfs:label ?varLabel .
        FILTER(REGEX(?varLabel, "year|age|yr|ka", "i"))
    }

    # Check variable values
    ?variable_time le:hasMinValue ?min_time .
    ?variable_time le:hasMaxValue ?max_time .

    # Get units for conversion
    ?variable_time le:hasUnits ?units_time .

    # Filter based on units and value ranges
    # Check if time range contains our period
    # - If dataset fully contained within period (>= min && <= max)
    # - If dataset fully contains period (<= min && >=max )
    # - If dataset intersects period (>= min|| <= max)
    # The range check will change if     
    {
        # Case 1: yr_BP with direct comparison
        FILTER(?units_time IN (punits:yr_BP))
        FILTER(
            (?min_time >= [minBeforePresent] && ?max_time <= [maxBeforePresent])
        )
    }
    UNION
    {
        # Case 2: yr_CE/AD needs conversion (1950 - yr_CE = yr_BP)
        FILTER(?units_time IN (punits:yr_AD, punits:yr_CE))
        # Convert yr_CE to yr_BP: 1950 - yr_CE = yr_BP
        BIND(1950 - ?max_time AS ?min_bp)
        BIND(1950 - ?min_time AS ?max_bp)
        FILTER(
            (?min_bp >= [minBeforePresent] && ?max_bp <= [maxBeforePresent])
        )

    }
    UNION
    {
        # Case 3: yr_b2k needs conversion (yr_b2k - 50 = yr_BP)
        FILTER(?units_time IN (punits:yr_b2k))
        # Convert yr_b2k to yr_BP: yr_b2k - 50 = yr_BP
        BIND(?min_time - 50 AS ?min_bp)
        BIND(?max_time - 50 AS ?max_bp)
        FILTER(
            (?min_bp >= [minBeforePresent] && ?max_bp <= [maxBeforePresent])
        )

    }
    UNION
    {
        # Case 4: ka_BP needs conversion (ka_BP * 1000 = yr_BP)
        FILTER(?units_time IN (punits:ka, punits:kyr))
        # Convert ka_BP to yr_BP: ka_BP * 1000 = yr_BP
        BIND(?min_time * 1000 AS ?min_bp)
        BIND(?max_time * 1000 AS ?max_bp)
        FILTER(
            (?min_bp >= [minBeforePresent] && ?max_bp <= [maxBeforePresent])
        )
    }
}
```

### QUERY_FILTER_VARIABLE_NAME
Description:

This query filters variables based on name pattern.
* Searches through all variable names
* Uses case-insensitive regular expression matching
* Provides context about where each matching variable is found

The information returned includes:
* Variable URI
* Dataset URI and name
* Table URI
* Variable ID and name

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX le: <http://linked.earth/ontology#>
SELECT ?uri ?dsuri ?dsname ?tableuri ?id ?name WHERE {
    ?uri le:hasVariableId ?id .
    ?uri le:hasName ?name .
    FILTER regex(?name, "[name].*", "i") .
    ?uri le:foundInDataset ?dsuri .
    ?uri le:foundInDatasetName ?dataSetName .
    ?uri le:foundInTable ?tableuri .
}
```

### QUERY_FILTER_VARIABLE_STANDARD_NAME
Description:

This query filters variables based on variable's standard variable instance
* Searches through all standard variables

The information returned includes:
* Dataset name
  
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX le: <http://linked.earth/ontology#>
PREFIX pvar: <http://linked.earth/ontology/paleo_variables#>
PREFIX le_arch: <http://linked.earth/ontology/archive#>
SELECT DISTINCT ?datasetName WHERE {
    ?dataset rdf:type le:Dataset ;
    le:hasName ?datasetName ;
    le:hasArchiveType le_arch:[archiveType] .

    ?dataset le:hasPaleoData ?paleoData_var .
    ?paleoData_var le:hasMeasurementTable ?dataTable_var .
    ?dataTable_var le:hasVariable ?variable_var .
    ?variable_var le:hasStandardVariable pvar:[standardVariableInstance] .
```


### QUERY_FILTER_VARIABLE_PROXY_STANDARD
Description:

This query filters variables based on variable's proxy
* Searches through all standard variables

The information returned includes:
* Dataset name
  
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX le: <http://linked.earth/ontology#>
PREFIX proxy: <http://linked.earth/ontology/paleo_proxy#>

SELECT DISTINCT ?datasetName WHERE {
    ?dataset rdf:type le:Dataset ;
    le:hasName ?datasetName ;
    le:hasArchiveType archive:[archiveTypeInstance] .

    ?dataset le:hasPaleoData ?paleoData_var .
    ?paleoData_var le:hasMeasurementTable ?dataTable_var .
    ?dataTable_var le:hasVariable ?variable_var .
    ?variable_var le:hasProxy proxy:[proxyInstance]
```

### QUERY_FILTER_VARIABLE_RESOLUTION
Description:

This query filters datasets by temporal resolution:
* Searches for a temperature variable
* Searches for temporal/time variable
* Checks that the resolution of the time variable is less than 1 year

The information returned includes:
* Dataset name

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX le: <http://linked.earth/ontology#>
PREFIX proxy: <http://linked.earth/ontology/paleo_proxy#>
PREFIX pvar: <http://linked.earth/ontology/paleo_variables#>
PREFIX punits: <http://linked.earth/ontology/paleo_units#>
PREFIX interp: <http://linked.earth/ontology/interpretation#>
SELECT DISTINCT ?datasetName WHERE {
    ?dataset rdf:type le:Dataset ;
    le:hasName ?datasetName .

    # Search for a Temperature variable (interpretation)
    ?dataset le:hasPaleoData ?paleoData_temperature .
    ?paleoData_temperature le:hasMeasurementTable ?dataTable_temperature .
    ?dataTable_temperature le:hasInterpretation ?interp_temperature .
    ?interp_temperature le:hasVariable interp:temperature .

    # Search for Time variable
    ?dataset le:hasPaleoData ?paleoData_time .  
    ?paleoData_time le:hasMeasurementTable ?dataTable_time .  
    ?dataTable_time le:hasVariable ?variable_time .  
    ?variable_time le:hasStandardVariable ?stdVar .  
    FILTER(?stdVar IN (pvar:age, pvar:year))

    # Get time variable properties
    ?variable_time le:hasMinValue ?min_time .  
    ?variable_time le:hasMaxValue ?max_time .  
    ?variable_time le:hasUnits ?units_time .  

    # Get time variable resolution
    ?variable_time le:hasResolution ?resolution .
    BIND(?units_time AS ?resolutionUnits)
    {
        # Option 1: Resolution max value is at most 1 year
        le:hasMaxValue ?maxValue .
        # Check for different types of year units        
        FILTER(?resolutionUnits IN (punits:yr_AD, punits:yr_BP, punits:yr))
        FILTER(?maxValue <= 1)
    }
    UNION
    {
        # Option 2: Temporal units are in months or days
        FILTER(?resolutionUnits IN (punits:month, punits:day, punits:hour))
    }
}
```

### QUERY_FILTER_COMPILATION
Description:

This query filters datasets based on compilation membership.
* Identifies datasets containing variables that are part of a specified compilation
* Uses case-insensitive regular expression matching
* Returns only distinct dataset names to avoid duplicates

The information returned includes:
* Dataset names that contain variables belonging to the specified compilation

```sparql
SELECT DISTINCT ?dataSetName WHERE {
    ?ds a le:Dataset .
    ?ds le:hasName ?dataSetName .

    ?ds le:hasPaleoData ?data .
    ?data le:hasMeasurementTable ?table .
    ?table le:hasVariable ?var .
    
    ?var le:partOfCompilation ?compilation . 
    ?compilation le:hasName ?compilationName .
    FILTER regex(?compilationName, "[compilationName].*", "i")}
```

## Metadata Queries

### QUERY_LiPDSERIES_PROPERTIES
Description:

This query identifies all properties used in the LiPDSeries data structure.
* Examines all properties across all entities in the graph
* Returns only distinct property types to avoid duplicates
* Used to understand the complete schema of the database

```sparql
SELECT DISTINCT ?p WHERE {
    ?uri ?p ?v .}
```

### QUERY_DATASET_PROPERTIES
Description:

This query identifies all properties used to describe datasets.
* Focuses only on properties directly attached to dataset entities
* Returns only distinct property types to avoid duplicates
* Used to understand the metadata schema for datasets

```sparql
PREFIX le: <http://linked.earth/ontology#>
SELECT DISTINCT ?property where {
?ds a le:Dataset .
?ds ?property ?value .
}
```

### QUERY_MODEL_PROPERTIES
Description:

This query identifies all properties used to describe models.
* Examines properties of both paleoclimate models and chronology models
* Returns only distinct property types to avoid duplicates
* Used to understand the metadata schema for models

```sparql
PREFIX le: <http://linked.earth/ontology#>
SELECT  DISTINCT ?property where {

?ds a le:Dataset .

{OPTIONAL{?ds le:hasPaleoData ?data .
          ?data le:modeledBy ?paleomodel .
          ?paleomodel ?property ?value .}}

UNION

{OPTIONAL{?ds le:hasChronData ?chron .
          ?chron le:modeledBy ?chronmodel .
          ?chronmodel ?property ?value .}}

}
```

### QUERY_COMPILATION_NAME
Description:

This query retrieves all compilation names in the database.
* Identifies all variables that are part of compilations
* Extracts the names of those compilations
* Returns only distinct compilation names to avoid duplicates
* Used to understand what data compilations are available

```sparql
PREFIX le: <http://linked.earth/ontology#>
        
SELECT DISTINCT ?compilationName WHERE {
    ?var a le:Variable .
    ?var le:partOfCompilation ?compilation . 
    ?compilation le:hasName ?compilationName .}
``` 
