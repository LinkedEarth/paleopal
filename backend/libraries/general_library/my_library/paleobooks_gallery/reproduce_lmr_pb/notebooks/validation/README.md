# Assimilating PAGES 2k records with LinkedEarth tools

By [Tanaya Gondhalekar](https://orcid.org/0009-0004-2440-3266), [Deborah Khider](https://orcid.org/0000-0001-7501-8430) & [Julien Emile-Geay](https://orcid.org/0000-0001-5920-4751). 

Climate field reconstruction is the task of estimating variations in one or more climate fields (e.g. surface temperature or precipitation) from a collection of paleoclimate observations (aka "proxies"). Many statistical methods are available for doing so ; a relatively new and impactful one has been offline data assimilation, as implemented in the Last Millennium Reanalysis [Hakim et al. (2016)](http://dx.doi.org/10.1002/2016JD024751). Part of [PReSto](https://paleopresto.com)'s mission is to democratize these tools and enable a wider variety of actors, from seasoned researchers to students or citizen scientists, to generate their own reconstructions based on available code and data.  

The purpose of this repository is to showcase how to use tools from the [LinkedEarth](http://linked.earth) Python research ecosystem (and broader scientific Python stack) to emulate and expand on the Last Millennium Reanalysis, version 2.1 [(Tardif et al, 2019)](https://doi.org/10.5194/cp-15-1251-2019), which used the offline data assimilation method of [Hakim et al. (2016)](http://dx.doi.org/10.1002/2016JD024751) together with the [PAGES 2k](http://dx.doi.org/10.1038/sdata.2017.88) database, version 2.0.0. 

The reconstruction workflow is broken down into 3 major steps, some of which have variants:
1. Data assembly: gathering, selection and cleaning
2. Data assimilation, which blends proxy observations with calibration data and the model prior
3. Validation and comparison to other relevant reconstructions

Here we offer 4 different ways to carry out Step 1, all of which result in a netCDF file that can be used in Step 2:

- [Step 1a](./C01_a_db_assembly_Tardif2019_pickle.html) illustrates how to get a proxy database derived from the two pickle files (metadata and data) provided by [(Tardif et al, 2019)](https://doi.org/10.5194/cp-15-1251-2019).
- [Step 1b](./C01_b_db_assembly_cfr_PAGES2k.html) illustrates how to get the proxy database directly from what is built into the `cfr` codebase. 
- [Step 1c](./C01_c_db_assembly_LiPDVerse.html) illustrates how to get the proxy database from the [LiPDVerse](https://lipdverse.org). 
- [Step 1d](./C01_d_db_assembly_LiPDGraph.html) illustrates how to get the proxy database from the [LiPD Graph](http://linkedearth.graphdb.mint.isi.edu).

Step 2 is common to all workflows, and only one instance is illustrated here (results obviously vary as a function of how Step 1 is implemented). Step 3 focuses here on emulating LMR v2.1, with validating both our results from Step 2, as well as comparing different proxy databases from Step 1 for forensics purposes. Newer reconstructions based on updates to the PAGES 2k database will be the subject of upcoming notebooks/publications.