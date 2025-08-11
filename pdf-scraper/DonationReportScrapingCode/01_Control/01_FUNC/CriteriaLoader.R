###Used to sequentially apply logical expressions to a source dataset
#This can greatly simplify tasks like Completion Factor analysis and Trend Analysis
#as those processes depend heavily on the creation of simple logical groupings
#and those groupings need to be seemlessly repeatable in other contexts; hence
#this function allows one to "disembody" the logic behind the groupings and deploy
#that logic across contexts.
TEMP_FUNC <- function (
  LogicData = tibble(PageNm=c(),LogicExpr=expr())
  ,
  SourceData,
  mode = 1, #Default choice is to run the logic as a hierarchical partition of the data
  GRPName = "GRP", #Default name for the "group" column
  ERRName = "ERR_None" #Default name for the rows where no logic returns true
) {
  switch(
    mode,
    ##############################################################################
    #Type 1: Putting the criteria into a case-when with a default "no code" value
    ##############################################################################
    {
      ArgList <- LogicData %>% pmap(
        .f=~expr(!!..2 ~ !!..1)
      ) %>% append(expr(TRUE~ERRName))
      
      AlteredData <- SourceData %>% mutate(
        #use do.call to unpack the list of arguments
        !!GRPName := do.call(case_when,ArgList)
      )
    }
    ,
    ##############################################################################
    #Type 2: Putting criteria into a loop and appending by row
    ##############################################################################
    {
      AlteredData <- identity(0) %>% {
        temp <- pmap_dfc(
          .l = LogicData,
          .f = ~SourceData %>% mutate(
            !!paste0(GRPName,"_",..1) := if_else(
              !!..2,1,0
            )
          ) %>% select(c(paste0(GRPName,"_",..1)))
        )
        bind_cols(SourceData,temp) %>% mutate(
          !!paste0(GRPName,"_",ERRName) := case_when(
            if_all(
              .cols = starts_with(paste0(GRPName,"_")),
              .fns = ~.==0
            ) ~ 1,
            TRUE ~ 0
          )
        ) %>% pivot_longer(
          cols = starts_with(paste0(GRPName,"_")),
          names_to = GRPName,
          names_prefix = paste0(GRPName,"_"),
          values_to = "RMV_TEMPVAL"
        ) %>% 
          filter(
            RMV_TEMPVAL != 0
          ) %>%
          select(
            -starts_with("RMV_")
          )
      }
    }
    ,
    ##############################################################################
    #Type 3: Putting criteria into a loop and appending by column
    ##############################################################################
    {
      AlteredData <- identity(0) %>% {
        temp <- pmap_dfc(
          .l = LogicData,
          .f = ~SourceData %>% mutate(
            !!paste0(GRPName,"_",..1) := if_else(
              !!..2,1,0
            )
          ) %>% select(c(paste0(GRPName,"_",..1)))
        )
        bind_cols(SourceData,temp) %>% mutate(
          !!paste0(GRPName,"_",ERRName) := case_when(
            if_all(
              .cols = starts_with(paste0(GRPName,"_")),
              .fns = ~.==0
            ) ~ 1,
            TRUE ~ 0
          )
        )
      }
    }
  )
  
  return(AlteredData)
}

# 
# MMDat <- PROJ_DATA$FUNC$ZZ_LoadAnOutput("POP_ComboMM.RDS")
# 
# LogDat <- tribble(
#   ~PageNm,~LogicExpr,
#   #Selecting for All distinct DDD member-months
#   "DDDAll",
#   expr(
#     SeriesName %in% c("Actual","DBF_V000") &
#       DataSource == "Analytical" &
#       CTRT_PGM != "TCM"
#   )
#   ,
#   #Selecting TCM Member-Months
#   "TCM",
#   expr(
#     SeriesName %in% c("Actual","DHCM_V000") &
#       CTRT_PGM == "TCM"
#   )
# )
# 
# MMDat %>% TEMP_FUNC(
#   LogicData = LogDat,
#   SourceData = .,
#   mode = 3
# ) %>% View()
# 
# 
# 
# MMDat %>% TEMP_FUNC(
#   LogicData = LogDat,
#   SourceData = .,
#   mode = 3
# ) %>%
# pivot_longer(
#   cols = starts_with("GRP_"),
#   names_to = "GRP",
#   names_prefix = "GRP_",
#   values_to = "RMV_TEMPVAL"
# ) %>%
# filter(
#   RMV_TEMPVAL != 0
# ) %>%
# select(
#   -starts_with("RMV_")
# ) %>% View("TEMP")
# 
# MMDat %>% TEMP_FUNC(
#   LogicData = LogDat,
#   SourceData = .,
#   mode = 2
# ) %>% View("TEMP2")
# 
# 
# LogDat %>% pmap(.f=~expr(!!..2 ~ !!..1))
# 
# #Create a list of arguments to pass to the case_when function
# x<-LogDat %>% pmap(.f=~expr(!!..2 ~ !!..1)) %>% append(expr(TRUE~"ERR_None"))
# 
# 
# ################################################################################
# #Alternative Mode 2 concept: add sequentially and then compute the case where no
# #logic applies and append that data. It is unclear if this is actually more
# #performant than the current version
# ################################################################################
# pmap_dfr(
#   .l = LogDat,
#   .f = ~MMDat %>% filter(
#     !!..2
#   ) %>% mutate(
#     GRP = ..1
#   )
# ) %>% View()
# 
# MMDat %>% rowwise() %>% mutate(
#   GRPVec = list(map_lgl(.x = LogDat$LogicExpr,.f=~eval(.x)))
# ) %>% ungroup() %>% mutate(
#   GRPLog = map_lgl(.x=GRPVec,.f=~!any(.x))
# ) %>% View()


