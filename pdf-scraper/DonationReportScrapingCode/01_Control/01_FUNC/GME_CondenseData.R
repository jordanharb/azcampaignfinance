###Read various population datasets and combine
TEMP_FUNC <- function (GMEData,Fields) {
  
  MainDat <- GMEData %>% select(
    any_of(Fields)
  ) %>% group_by_at(
    vars(
      -starts_with("MV_")
    )
  ) %>% summarize_at(
    vars(
      starts_with("MV_")
    ),
    .funs = ~sum(.)
  ) %>% ungroup()
  
  return(
    MainDat
  )
}
###