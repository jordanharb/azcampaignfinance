TEMP_FUNC <- function(data,StDat, EndDat) {
  
  #Establish path to file
  # DatPath <- file.path(
  #   ProjPath,
  #   "01_CommonUse_Data",
  #   "02_Output",
  #   "CFData.RDS"
  # )
  
  #Establish connection and read data
  # Will need to substantially revise once actual file is available,
  # will depend on DDDs response format
  x <- data
  
  
  MainDat <- tibble(
    LagDuration = 0:(lubridate::interval(StDat,EndDat)%/%months(1))
  ) %>% crossing(
    distinct(
      x,
      CFGroup,
      Version
    )
  ) %>% left_join(
    x,
    by = c(
      "CFGroup" = "CFGroup",
      "Version" = "Version",
      "LagDuration" = "LagDuration"
    )
  ) %>% mutate(
    CFValid_IND = if_else(is.na(CFValid_IND),"N",CFValid_IND),
    MV_LR = if_else(is.na(MV_LR),1,MV_LR)
  ) %>% arrange(
    CFGroup,
    desc(LagDuration)
  ) %>% group_by(
    CFGroup,
    Version
  ) %>% mutate(
    MV_AggLR = cumprod(MV_LR)
  ) %>% ungroup() %>% mutate(
    MV_CompFact = 1/MV_AggLR,
    SVC_NDate = EndDat - months(LagDuration)
  )
  
  
  
  #Return Main Data after all adjustments are made
  return(MainDat)
}