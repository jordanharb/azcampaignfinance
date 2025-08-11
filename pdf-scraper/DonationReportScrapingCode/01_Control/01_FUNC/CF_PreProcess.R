###CF Preprocess - Triangle Development
TEMP_FUNC <- function(EncData,TimeST,TimeEnd,CFGrp,RnkGrp) {
  
  CF_Frame1 <- tibble(
    SVC_NDate = seq.Date(TimeST,TimeEnd,by="month"),
    PMT_NDate = list(0:(interval(TimeST,TimeEnd)%/%months(1)))
  ) %>% unnest(PMT_NDate) %>% mutate(
    PMT_NDate = SVC_NDate + months(PMT_NDate)
  ) %>% filter(
    PMT_NDate <= TimeEnd
  ) %>% crossing(
    EncData %>% mutate(
      CFGroup = !!sym(CFGrp)
    ) %>% filter(!grepl("^Exclude",CFGroup)) %>% distinct(CFGroup)
  ) %>% left_join(
    EncData %>% mutate(
      CFGroup = !!sym(CFGrp),
      SVC_NDate = ymd(paste0(SVCMTH,"01")),
      PMT_NDate = ymd(paste0(PMTMTH,"01"))
    ) %>% group_by(
      CFGroup,
      SVC_NDate,
      PMT_NDate
    ) %>% summarize(
      across(
        .cols = starts_with("True"),
        .fns = ~sum(.)
      )
    ) %>% ungroup() %>% filter(
      !grepl("^Exclude",CFGroup)
    )
  ) %>% mutate(
    across(
      .cols = starts_with("True"),
      .fns = ~if_else(is.na(.),0,.)
    )
  ) %>% arrange(
    CFGroup,SVC_NDate,PMT_NDate
  ) %>% group_by(
    CFGroup,SVC_NDate
  ) %>% mutate(
    across(
      .cols = starts_with("True"),
      .fns = ~cumsum(.),
      .names = "RunTTLCurr_{.col}"
    )
  ) %>% mutate(
    across(
      .cols = starts_with("True"),
      .fns = ~if_else(is.na(lag(cumsum(.))),0,lag(cumsum(.))),
      .names = "RunTTLPrev_{.col}"
    )
  ) %>% ungroup() %>% mutate(
    across(
      .cols = starts_with("True"),
      .fns = ~if_else(eval(sym(paste0("RunTTLPrev_",cur_column())))==0,0,1),
      .names = "RankIND_{.col}"
    )
  ) %>% mutate(
    LagDuration = interval(SVC_NDate,PMT_NDate)%/%months(1),
    RankChoice = !!sym(paste0("RankIND_",RnkGrp))
  ) %>% arrange(
    CFGroup,
    LagDuration,
    desc(SVC_NDate)
  ) %>% group_by(
    CFGroup,
    LagDuration,
    RankIND_TrueAmt
  ) %>% mutate(
    RankVal = if_else(RankChoice==0,0,1*row_number())
  ) %>% ungroup() %>% mutate(
    CFType = CFGrp
  ) %>% select(
    CFType,
    CFGroup,
    LagDuration,
    SVC_NDate,
    PMT_NDate,
    starts_with("RunTTLCurr"),
    starts_with("RunTTLPrev"),
    RankVal
  ) %>% arrange(
    CFGroup,
    SVC_NDate,
    PMT_NDate
  )
  return(CF_Frame1)
}
###


