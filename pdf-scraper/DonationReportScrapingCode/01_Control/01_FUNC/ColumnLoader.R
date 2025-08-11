###Used to sequentially apply function expressions to a source dataset
#This allows one to define a set of features once and apply it many times
TEMP_FUNC <- function (
    LogicData = tibble(FldNm=c(),FuncExpr=expr())
    ,
    SourceData
) {
  
  ##############################################################################
  #Type 3: Putting criteria into a loop and appending by column
  ##############################################################################
  AlteredData <- identity(0) %>% {
    temp <- pmap_dfc(
      .l = LogicData,
      .f = ~SourceData %>% mutate(
        !!..1 := !!..2
      ) %>% select(c(!!..1))
    )
    bind_cols(SourceData,temp)
  }
  
  return(AlteredData)
}


