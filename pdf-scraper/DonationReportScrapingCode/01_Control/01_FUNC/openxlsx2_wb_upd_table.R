TEMP_FUNC <- function(
    wb,
    tbl_lst = c(),
    rpl_lst = c(),
    keepNames = TRUE
    
) {
  wb_tab <- wb$tables %>% filter(
    tab_name %in% tbl_lst
  ) %>% mutate(
    startcol = str_extract(tab_ref,"^.*:") %>% str_remove(":") %>% col2int(),
    startrow = str_extract(tab_ref,"[0-9]*:") %>% str_remove(":") %>% as.integer()
  ) %>% bind_cols(
    tibble(rpl_tab_name = rpl_lst)
  ) %>% arrange(startcol)
  
  wb_upd <- wb$clone(deep=TRUE)
  
  pwalk(
    .l = wb_tab,
    .f = function(...){
      lst <- list(...)
      if(keepNames){
        tabName <- lst$tab_name
      } else{
        tabName <- lst$rpl_tab_name
      }

      wb_upd$remove_tables(
        sheet = lst$tab_sheet,
        table = lst$tab_name
      )$add_data_table(
        sheet = lst$tab_sheet,
        start_col = lst$startcol,
        start_row = lst$startrow,
        table_name = tabName,
        x = eval(sym(lst$rpl_tab_name))
      )
      
    }
  )
  
  return(wb_upd)
  
}