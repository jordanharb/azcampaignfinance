TEMP_FUNC <- function (CFData,CFGroupLogic,GMEData,DatModIdx,ZeroFilt=TRUE,CRNRound=TRUE) {
  
  ###Remove fields from CFData that are unneeded for the calculation (reduces clutter)
  CFJoin <- CFData %>% transmute(
    CFGroup,
    SVCMTH = paste(format.Date(SVC_NDate,"%Y"),format.Date(SVC_NDate,"%m"),sep=""),
    MV_CompFact
  )
  ###
  
  ###Filter the base data for items to which completion should be applied,
  #condense by removing the DataMod and DataSrc fields, and then add a 
  #crosswalk for the CFGroups used in the CFSelector file to tie out to
  #financial statement/incurred encounter information.
  BaseEncJoin <- GMEData %>% filter(
    DataSrc_SubType != "ENC_StfModel"
  ) %>% group_by_at(
    vars(
      -starts_with("MV_"),
      -starts_with("DataSrc"),
      -starts_with("DataMod")
    )
  ) %>% summarize_at(
    vars(
      starts_with("MV_")
    ),
    .funs = ~sum(.)
  ) %>% ungroup() %>% PROJ_FUNC$FUNC$CriteriaLoader(
    LogicData = CFGroupLogic,
    SourceData = .,
    mode = 1,
    GRPName = "CFGroup",
    ERRName = "ZZZ_ELSE"
  )
  ###
  
  ##############################################################################
  #Determine non-value fields to include
  ##############################################################################
  Fields <- GMEData %>% select(
    -starts_with("MV")
  ) %>% names()
  
  ###Join the previous two tables and compute the incremental impact to generate the
  #completion factor base encounter data module
  MainDat <- BaseEncJoin %>% left_join(
    CFJoin,
    by = c(
      "SVCMTH" = "SVCMTH",
      "CFGroup" = "CFGroup"
    )
  ) %>% mutate(
    DataSrc = "Analytical",
    DataSrc_SubType = "Analytical",
    DataMod_Index = DatModIdx,
    DataMod_Name = "Completion Factor",
    across(
      .cols = starts_with("MV_"),
      .fns = ~. * (1-MV_CompFact)/MV_CompFact
    )
  ) %>% select(
    -MV_CompFact
  ) %>% transmute(
    across(
      .cols = Fields,
      .fns = ~.
    ),
    across(
      .cols = starts_with("MV_"),
      .fns = ~if_else(is.na(.),0,.)
    )
  )
  ###
  
  if(ZeroFilt){
    MainDat <- MainDat %>% filter(
      if_any(
        .cols = starts_with("MV_"),
        .fns = ~.!=0
      )
    )
  }
  
  if(CRNRound){
    MainDat <- MainDat %>% mutate(
      MV_CRNCount = round(MV_CRNCount,digits=0)
    )
  }
  
  return(
    MainDat
  )
}
###