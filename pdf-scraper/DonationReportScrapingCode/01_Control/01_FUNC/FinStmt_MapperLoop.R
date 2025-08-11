TEMP_FUNC <- function(FinDat) {
  
  ######
  #Expects financial data formatted with the standard 9 columns, only one file at a time
  #Explicit vectorization would be needed to handle multiple successive maps
  ######
  
  ####primary processing loop
  TEST_mapName <- FinDat %>% distinct(file) %>% .$file %>% str_remove(pattern=".xlsx$")
  TEST_mapData <- FinDat %>% transmute(
    TEMP_AcctCD,
    TEMP_AcctDesc,
    TRUE_AcctCD,
    MapIndex = TEST_mapName
  )
  
  while(
    "UNDEFINED" %in% (TEST_mapData$TRUE_AcctCD %>% unlist())
  ) {
    TEST_mapData <- TEST_mapData %>% data_edit(
      col_options = list(TRUE_AcctCD = paste0("<",Dim_AcctCD$AcctCD)),
      viewer = "browser"
    ) %>% mutate(
      TRUE_AcctCD = str_replace(TRUE_AcctCD,"<","")
    )
    
  }
  
  TEST_mapData <- TEST_mapData %>% mutate(
    TEMP_AcctDesc = str_to_sentence(TEMP_AcctDesc)
  ) %>% distinct()
  ####
  
  return(TEST_mapData)
}