TEMP_FUNC <- function(tbls = c()) {
  
  lst <- tibble(Data = tbls)
  
  wb <- openxlsx::createWorkbook()
  
  openxlsx::addWorksheet(
    wb = wb,
    sheetName = "DataInsert"
  )
  
  #Write Various files
  lst %>% mutate(
    index = row_number(),
    cols = pmap_int(
      .l = tibble(x = Data),
      .f = ~eval(sym(..1)) %>% length()
    ),
    cols_wspace = if_else(index == 1,cols + 2,cols+1),
    sumcol = cumsum(cols_wspace),
    stcol = if_else(is.na(lag(sumcol)),1,lag(sumcol))
  ) %>% pwalk(
    .f = function(...){
      curtbl <- tibble(...)
      openxlsx::writeDataTable(
        wb,
        sheet = "DataInsert",
        x = eval(sym(curtbl$Data)),
        startCol = curtbl$stcol,
        tableName = paste0(curtbl$Data)
      )
    }
  )
  
  openxlsx::openXL(wb)
  
  return(0)
}