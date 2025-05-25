"""
Automatically generated context from the LinkedEarth ontology.
"""

# Prefixes
ONTOLOGY_PREFIXES = """
owl: <http://www.w3.org/2002/07/owl#>
rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
rdfs: <http://www.w3.org/2000/01/rdf-schema#>
xsd: <http://www.w3.org/2001/XMLSchema#>
xml: <http://www.w3.org/XML/1998/namespace>
dct: <http://purl.org/dc/terms/>
le: <http://linked.earth/ontology#>
pvar: <http://linked.earth/ontology/paleo_variables#>
pproxy: <http://linked.earth/ontology/paleo_proxy#>
arch: <http://linked.earth/ontology/archive#>
punits: <http://linked.earth/ontology/paleo_units#>
interp: <http://linked.earth/ontology/interpretation#>
"""

# Classes
ONTOLOGY_CLASSES = """
arch:ArchiveType (ArchiveType )
interp:InterpretationSeasonality (InterpretationSeasonality )
le:Calibration (Calibration (Calibration information for measured data))
le:Change (Change (A specific change recorded in a changelog))
le:ChangeLog (ChangeLog (A record of changes made to a dataset))
le:ChronData (ChronData (Chronology data contained within a dataset. This includes all measurements and models related to establishing the age-depth relationship of the archive.))
le:Compilation (Compilation (A compilation of paleoclimate datasets. Compilations aggregate multiple datasets to enable regional or global analyses of paleoclimate patterns.))
le:DataTable (DataTable (A table of data measurements))
le:Dataset (Dataset (A paleoclimate dataset containing measurements, interpretations, and metadata. Datasets form the core unit in the LinkedEarth ontology and include paleoclimate data (measurements), chronology data, physical sample information, and related publications.))
le:Funding (Funding (Information about funding sources for research))
le:Interpretation (Interpretation (An interpretation of measured variables. This represents the climate or environmental interpretation derived from proxy measurements, including the relationship between the measured variable and the interpreted parameter.))
le:Location (Location (The geographic location where data was collected. This includes coordinates, site name, and other geographic information related to where the physical samples were obtained.))
le:Model (Model (A model derived from or applied to dataset measurements))
le:PaleoData (PaleoData (Paleoclimate data contained within a dataset. This includes all measured and derived variables related to past climate conditions, distinct from chronology data.))
le:Person (Person (A person involved with the dataset))
le:PhysicalSample (PhysicalSample (A physical sample used for measurements. This represents the actual physical specimen from which measurements were taken, such as a core section, fossil, or sediment sample.))
le:Publication (Publication (A scientific publication related to the dataset. This includes journal articles, books, reports and other publication types that document the dataset's collection, processing, interpretation, or use in a scientific study.))
le:Resolution (Resolution (The temporal or spatial resolution of measurements))
le:Variable (Variable (A variable measured or derived in a dataset. Variables represent the actual measurements or values derived from the paleoclimate archive, and can include measured proxies, chronological controls, or interpreted climate parameters.))
pproxy:PaleoProxy (PaleoProxy )
pproxy:PaleoProxyGeneral (PaleoProxyGeneral )
punits:PaleoUnit (PaleoUnit )
pvar:PaleoVariable (PaleoVariable )
"""

# Properties
ONTOLOGY_PROPERTIES = """
# Properties for le:Calibration
le:Calibration -> le:hasDOI -> xsd:string  # has DOI
le:Calibration -> le:hasDatasetRange -> xsd:string  # has dataset range
le:Calibration -> le:hasEquation -> xsd:string  # has equation
le:Calibration -> le:hasEquationIntercept -> xsd:string  # has equation intercept
le:Calibration -> le:hasEquationR2 -> xsd:string  # has equation R2
le:Calibration -> le:hasEquationSlope -> xsd:string  # has equation slope
le:Calibration -> le:hasEquationSlopeUncertainty -> xsd:string  # has equation slope uncertainty
le:Calibration -> le:hasMethod -> xsd:string  # has method
le:Calibration -> le:hasMethodDetail -> xsd:string  # has method detail
le:Calibration -> le:hasNotes -> xsd:string  # has notes
le:Calibration -> le:hasProxyDataset -> xsd:string  # has proxy dataset
le:Calibration -> le:hasSeasonality -> interp:InterpretationSeasonality  # has seasonality
le:Calibration -> le:hasTargetDataset -> xsd:string  # has target dataset
le:Calibration -> le:hasUncertainty -> xsd:string  # has uncertainty

# Properties for le:Change
le:Change -> le:hasNotes -> xsd:string  # has notes

# Properties for le:ChangeLog
le:ChangeLog -> le:hasChanges -> le:Change  # has changes
le:ChangeLog -> le:hasLastVersion -> xsd:string  # has last version
le:ChangeLog -> le:hasNotes -> xsd:string  # has notes
le:ChangeLog -> le:hasTimestamp -> xsd:string  # has timestamp
le:ChangeLog -> le:hasVersion -> xsd:string  # has version

# Properties for le:ChronData
le:ChronData -> le:hasMeasurementTable -> le:DataTable  # has measurement table
le:ChronData -> le:modeledBy -> le:Model  # modeled by

# Properties for le:Compilation
le:Compilation -> le:hasName -> xsd:string  # has name
le:Compilation -> le:hasVersion -> xsd:string  # has version

# Properties for le:DataTable
le:DataTable -> le:hasFileName -> xsd:string  # has file name
le:DataTable -> le:hasMissingValue -> xsd:string  # has missing value
le:DataTable -> le:hasVariable -> le:Variable  # has variable

# Properties for le:Dataset
le:Dataset -> le:hasArchiveType -> arch:ArchiveType  # has archive type
le:Dataset -> le:hasChangeLog -> le:ChangeLog  # has change log
le:Dataset -> le:hasChronData -> le:ChronData  # has chron data
le:Dataset -> le:hasCollectionName -> xsd:string  # has collection name
le:Dataset -> le:hasCollectionYear -> xsd:string  # has collection year
le:Dataset -> le:hasCompilationNest -> xsd:string  # has compilation nest
le:Dataset -> le:hasContributor -> le:Person  # has contributor
le:Dataset -> le:hasCreator -> le:Person  # has creator
le:Dataset -> le:hasDataSource -> xsd:string  # has data source
le:Dataset -> le:hasDatasetId -> xsd:string  # has dataset id
le:Dataset -> le:hasFunding -> le:Funding  # has funding
le:Dataset -> le:hasInvestigator -> le:Person  # has investigator
le:Dataset -> le:hasLocation -> le:Location  # has location
le:Dataset -> le:hasName -> xsd:string  # has name
le:Dataset -> le:hasNotes -> xsd:string  # has notes
le:Dataset -> le:hasOriginalDataUrl -> xsd:string  # has original data URL
le:Dataset -> le:hasPaleoData -> le:PaleoData  # has paleo data
le:Dataset -> le:hasPublication -> le:Publication  # has publication
le:Dataset -> le:hasSpreadsheetLink -> xsd:string  # has spreadsheet link
le:Dataset -> le:hasVersion -> xsd:string  # has version

# Properties for le:Funding
le:Funding -> le:hasFundingCountry -> xsd:string  # has funding country
le:Funding -> le:hasGrant -> xsd:string  # has grant

# Properties for le:Interpretation
le:Interpretation -> le:hasBasis -> xsd:string  # has basis
le:Interpretation -> le:hasDirection -> xsd:string  # has direction
le:Interpretation -> le:hasMathematicalRelation -> xsd:string  # has mathematical relation
le:Interpretation -> le:hasNotes -> xsd:string  # has notes
le:Interpretation -> le:hasRank -> xsd:string  # has rank
le:Interpretation -> le:hasScope -> xsd:string  # has scope
le:Interpretation -> le:hasSeasonality -> interp:InterpretationSeasonality  # has seasonality
le:Interpretation -> le:hasSeasonalityGeneral -> interp:InterpretationSeasonality  # has seasonality general
le:Interpretation -> le:hasSeasonalityOriginal -> interp:InterpretationSeasonality  # has seasonality original
le:Interpretation -> le:hasVariable -> interp:InterpretationVariable  # has variable
le:Interpretation -> le:hasVariableDetail -> xsd:string  # has variable detail
le:Interpretation -> le:hasVariableGeneral -> xsd:string  # has variable general
le:Interpretation -> le:hasVariableGeneralDirection -> xsd:string  # has variable general direction
le:Interpretation -> le:isLocal -> xsd:string  # is local

# Properties for le:Location
le:Location -> le:hasElevation -> xsd:string  # has elevation
le:Location -> le:hasLatitude -> xsd:string  # has latitude
le:Location -> le:hasLongitude -> xsd:string  # has longitude
le:Location -> le:hasSiteName -> xsd:string  # has site name

# Properties for le:Model
le:Model -> le:hasDistributionTable -> le:DataTable  # has distribution table
le:Model -> le:hasEnsembleTable -> le:DataTable  # has ensemble table
le:Model -> le:hasSummaryTable -> le:DataTable  # has summary table

# Properties for le:PaleoData
le:PaleoData -> le:hasMeasurementTable -> le:DataTable  # has measurement table
le:PaleoData -> le:hasName -> xsd:string  # has name
le:PaleoData -> le:modeledBy -> le:Model  # modeled by

# Properties for le:Person
le:Person -> le:hasName -> xsd:string  # has name

# Properties for le:Publication
le:Publication -> le:hasAbstract -> xsd:string  # has abstract
le:Publication -> le:hasAuthor -> le:Person  # has author
le:Publication -> le:hasCitation -> xsd:string  # has citation
le:Publication -> le:hasCiteKey -> xsd:string  # has cite key
le:Publication -> le:hasDOI -> xsd:string  # has DOI
le:Publication -> le:hasDataUrl -> xsd:string  # has data URL
le:Publication -> le:hasFirstAuthor -> le:Person  # has first author
le:Publication -> le:hasInstitution -> xsd:string  # has institution
le:Publication -> le:hasIssue -> xsd:string  # has issue
le:Publication -> le:hasJournal -> xsd:string  # has journal
le:Publication -> le:hasPages -> xsd:string  # has pages
le:Publication -> le:hasPublisher -> xsd:string  # has publisher
le:Publication -> le:hasReport -> xsd:string  # has report
le:Publication -> le:hasTitle -> xsd:string  # has title
le:Publication -> le:hasType -> xsd:string  # has type
le:Publication -> le:hasUrl -> xsd:string  # has URL
le:Publication -> le:hasVolume -> xsd:string  # has volume
le:Publication -> le:hasYear -> xsd:string  # has year

# Properties for le:Resolution
le:Resolution -> le:hasMaxValue -> xsd:float  # has max value
le:Resolution -> le:hasMeanValue -> xsd:float  # has mean value
le:Resolution -> le:hasMedianValue -> xsd:float  # has median value
le:Resolution -> le:hasMinValue -> xsd:float  # has min value
le:Resolution -> le:hasUnits -> punits:PaleoUnit  # has units

# Properties for le:Variable
le:Variable -> le:calibratedVia -> le:Calibration  # calibrated via
le:Variable -> le:hasArchiveType -> arch:ArchiveType  # has archive type
le:Variable -> le:hasColumnNumber -> xsd:integer  # has column number
le:Variable -> le:hasDescription -> xsd:string  # has description
le:Variable -> le:hasInterpretation -> le:Interpretation  # has interpretation
le:Variable -> le:hasValues -> xsd:string  # has values (json representation of an array of values)
le:Variable -> le:hasMaxValue -> xsd:float  # has max value
le:Variable -> le:hasMeanValue -> xsd:float  # has mean value
le:Variable -> le:hasMedianValue -> xsd:float  # has median value
le:Variable -> le:hasMinValue -> xsd:float  # has min value
le:Variable -> le:hasMissingValue -> xsd:string  # has missing value
le:Variable -> le:hasName -> xsd:string  # has name
le:Variable -> le:hasNotes -> xsd:string  # has notes
le:Variable -> le:hasPhysicalSample -> le:PhysicalSample  # has physical sample
le:Variable -> le:hasProxy -> pproxy:PaleoProxy  # has proxy
le:Variable -> le:hasProxyGeneral -> pproxy:PaleoProxyGeneral  # has proxy general
le:Variable -> le:hasResolution -> le:Resolution  # has resolution
le:Variable -> le:hasStandardVariable -> pvar:PaleoVariable  # has standard variable
le:Variable -> le:hasUncertainty -> xsd:string  # has uncertainty
le:Variable -> le:hasUncertaintyAnalytical -> xsd:string  # has uncertainty analytical
le:Variable -> le:hasUncertaintyReproducibility -> xsd:string  # has uncertainty reproducibility
le:Variable -> le:hasUnits -> punits:PaleoUnit  # has units
le:Variable -> le:hasVariableId -> xsd:string  # has variable id
le:Variable -> le:isComposite -> xsd:boolean  # is composite
le:Variable -> le:isPrimary -> xsd:boolean  # is primary
le:Variable -> le:partOfCompilation -> le:Compilation  # part of compilation

"""

# Property validation examples
PROPERTY_VALIDATION = """
# Property validation examples for specific domains:

## Dataset properties:
?dataset a le:Dataset .
?dataset le:hasChronData ?chronData . # ?chronData should be le:ChronData
?dataset le:hasPaleoData ?paleoData . # ?paleoData should be le:PaleoData
?dataset le:hasArchiveType ?archiveType . # ?archiveType should be arch:ArchiveType

## Variable properties:
?variable a le:Variable .
?variable le:hasStandardVariable ?stdVar . # ?stdVar should be pvar:PaleoVariable
?variable le:hasProxy ?proxy . # ?proxy should be pproxy:PaleoProxy
?variable le:hasUnits ?units . # ?units should be punits:PaleoUnit

## Interpretation properties:
?variable a le:Variable .
?variable le:hasInterpretation ?interpretation . # ?interpretation should be le:Interpretation
?interpretation le:hasVariable ?interpVar . # ?interpVar should be interp:InterpretationVariable

## Location properties:
?location a le:Location .
?location geo:lat ?lat . # ?lat should be xsd:decimal
?location geo:long ?long . # ?long should be xsd:decimal

## Table hierarchy:
?dataset le:hasPaleoData ?paleoData .
?paleoData le:hasMeasurementTable ?table .
?table le:hasVariable ?variable .

## Resolution handling:
?variable le:hasResolution ?resolution .
?resolution le:hasMaxValue ?maxValue . # ?maxValue should be xsd:float
?resolution le:hasUnits ?resUnits . # ?resUnits should be punits:PaleoUnit

"""
