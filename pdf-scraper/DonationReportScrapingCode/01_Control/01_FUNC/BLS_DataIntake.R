TEMP_FUNC <- function(idSearch = c("CUSR0000SA0"),styear,endyear) {
  

  catalog_data <- readr::read_tsv(
    file.path(
      ProjPath,
      "01_Control",
      "00_DATA",
      "BLSTables",
      "cu.series.txt"
    )
  ) %>% select(
    series_id,series_title
  ) %>% bind_rows(
    readr::read_tsv(
      file.path(
        ProjPath,
        "01_Control",
        "00_DATA",
        "BLSTables",
        "cw.series.txt"
      )
    ) %>% select(
      series_id,series_title
    )
  )
  
  
  
  MainDat <- blsAPI::blsAPI(
    list('seriesid'=idSearch,
         'startyear'=styear,
         'endyear'=endyear
         #'catalog'=TRUE #Doesn't work, no point.
    ),
    return_data_frame = TRUE
  ) %>% left_join(
    catalog_data,
    by=c(
      "seriesID" = "series_id"
    )
  )
  
  
  
  
  #Return Main Data after all adjustments are made
  return(MainDat)
}