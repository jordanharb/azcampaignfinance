TEMP_FUNC <- function(data,RmvCols = c(),ValueCols = c("MV_ComboCostAmt","MV_Derived_QTY","MV_CRNCount")) {
  
  #Establish path to file
  DatPath <- data
  
  #Establish connection and read data
  # Will need to substantially revise once actual file is available,
  # will depend on DDDs response format
  BaseEncData <- DatPath %>% mutate(
    SVCMTH = as.character(SVCMTH),
    PMTMTH = as.character(PMTMTH)
  ) %>% filter(
    CTRT_PGM %in% c("ALTCS/DDD","ALTCS/DDD_CRS")
  ) %>% group_by_at(
    vars(
      -starts_with("MV_"),
      -any_of(
        RmvCols
      )
    )
  ) %>% summarize(
    across(
      .cols = any_of(ValueCols),
      .fns = ~sum(.)
    )
  ) %>% ungroup()
  
  MainDat <- expand(
    BaseEncData,
    !!!syms(
      tibble(name = names(BaseEncData)) %>% filter(name %in% c("SVCMTH")) %>% .$name
    ),
    nesting(
      !!!syms(
        tibble(name = names(BaseEncData)) %>% filter(!startsWith(name,"MV_") & !(name %in% c("SVCMTH"))) %>% .$name
      )
    )
  ) %>% left_join(
    BaseEncData
  ) %>% mutate(
    across(
      .cols = starts_with("MV_"),
      .fns = ~if_else(is.na(.),0,.)
    )
  )
  
  #Return Main Data after all adjustments are made
  return(MainDat)
}