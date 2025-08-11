TEMP_FUNC <- function(
    InputData,
    DataFilter = expr(TRUE),
    AmtField,
    IndexField,
    interval_rmv,
    interval_origin,
    interval_end,
    modelargs = list(),
    kalmanargs = list(),
    betashape=c(1,1),
    RTNMode = 1
) {
  
  
  #####
  #Condensing to just the desired fields: assumption is that the incoming data
  #has had dimension fields removed or is otherwise redundant; given the high volume
  #of data modifications posted to the encounter data for rate-setting, I don't
  #want to interpolate individual modifications, I want to interpolate the aggregated
  #total on relevant dimensions
  #####
  tbl <- InputData %>% filter(
    eval(DataFilter)
  ) %>% group_by(
    across(
      .cols = -starts_with("MV_")
    )
  ) %>% summarize(
    across(
      .cols = AmtField,
      .fns = ~sum(.)
    )
  ) %>% ungroup()
  
  ###Set the return fields
  VecFieldData <- tbl %>%
    group_by(
      across(
        .cols = IndexField
      )
    ) %>% nest() %>% ungroup() %>% unnest() %>% select(
      -c(IndexField,starts_with("MV_"))
    ) %>% distinct()
  
  #Set up the vectors to interpolate between for proportional allocation
  interpvecs <- list(
    tbl %>%
      group_by(
        across(
          .cols = IndexField
        )
      ) %>% nest() %>% ungroup() %>% unnest() %>% filter(
        !!sym(IndexField) %in% seq.Date(interval_origin[1],interval_origin[2],by="month")
      ) %>% group_by(
        across(
          .cols = names(VecFieldData)
        )
      ) %>% summarize(
        n = sum(!!sym(AmtField))
      ) %>% ungroup() %>% mutate(
        n=n/sum(n)
      ) %>% .$n
    ,
    tbl %>%
      group_by(
        across(
          .cols = IndexField
        )
      ) %>% nest() %>% ungroup() %>% unnest() %>% filter(
        !!sym(IndexField) %in% seq.Date(interval_end[1],interval_end[2],by="month")
      ) %>% group_by(
        across(
          .cols = names(VecFieldData)
        )
      ) %>% summarize(
        n = sum(!!sym(AmtField))
      ) %>% ungroup() %>% mutate(
        n=n/sum(n)
      ) %>% .$n
  )
  
  
  #generate condensed table by index and measurements only
  datatbl <- tbl %>% group_by(
    across(
      .cols = IndexField
    )
  ) %>% summarize(
    across(
      .cols = starts_with("MV_"),
      .fns = ~sum(.)
    )
  ) %>% ungroup()
  
  ##############################################################################
  #Handling Basic Time Series Layout
  ##############################################################################
  
  mintime <- datatbl %>% summarize(
    n = min(!!sym(IndexField))
  ) %>% .$n
  
  fcsttgt <- datatbl %>% arrange(
    !!sym(IndexField)
  ) %>% transmute(
    n=if_else(!!sym(IndexField) %in% seq.Date(interval_rmv[1],interval_rmv[2],by="month"),NA_real_,!!sym(AmtField)) #consider making this independent of the removal interval
  ) %>% .$n
  
  inputts <- ts(
    fcsttgt,start=c(year(mintime),month(mintime)),frequency=12
  )
  
  
  fit <- do.call(
    what=forecast::auto.arima, #I think we could parameterize this better. The real trouble is that the kalman method only works with ARIMA
    args=list(y=inputts) %>% append(modelargs)
  )
  
  timetbl <- datatbl %>% arrange(
    !!sym(IndexField)
  ) %>% bind_cols(
    tibble(
      !!paste0(AmtField,"_INTERP") := do.call(
        what = imputeTS::na_kalman,
        args = list(x=inputts,model=fit$model) %>% append(kalmanargs)
      ) %>% c()
    )
  ) %>% filter(
    !!sym(IndexField) %in% seq.Date(interval_rmv[1],interval_rmv[2],by="month")
  ) %>% mutate(
    index = row_number()
  )
  
  ############################################################################## 
  
  input_time = c(
    timetbl %>% summarize(n=min(index)) %>% .$n-1, #could set a branched path that sets the modifier to 0 if including endpoints
    timetbl %>% summarize(n=max(index)) %>% .$n+1
  )
  
  #initial return candidate
  returndat <- datatbl %>% left_join(
    timetbl %>% transmute(
      !!sym(IndexField),
      !!sym(paste0(AmtField,"_INTERP")),
      ScalePhaseIn = scales::rescale(index,from=input_time) %>% pbeta(shape1 = betashape[1], shape2 = betashape[2]),
      PropVec = pmap(
        tibble(x=ScalePhaseIn),
        .f = ~ ..1*interpvecs[[1]]+(1-..1)*interpvecs[[2]]
      )
    )
  ) %>% mutate(
    interpIND = if_else(is.na(!!sym(paste0(AmtField,"_INTERP"))),"N","Y"),
    data = list(VecFieldData)
  )
  
  
  ###Return Block
  
  switch(
    RTNMode,
    return(returndat),
    return(
      returndat %>% filter(
        interpIND == "Y"
      ) %>% mutate(
        data = pmap(
          tibble(x=PropVec,y=!!sym(paste0(AmtField,"_INTERP")),z=data),
          .f = ~bind_cols(..3,!!sym(AmtField):=..1*..2)
        )
      ) %>% select(
        -PropVec,
        -ScalePhaseIn,
        -interpIND,
        -!!sym(AmtField),
        -!!sym(paste0(AmtField,"_INTERP"))
      ) %>% unnest()
    ),
    return(
      returndat %>% select(
        c(
          IndexField,
          AmtField,
          paste0(AmtField,"_INTERP")
        )
      ) %>% pivot_longer(
        cols = c(AmtField,paste0(AmtField,"_INTERP")),
        names_to="AmtType",
        values_to="Amt"
      ) %>% filter(
        !is.na(Amt)
      ) %>% mutate(
        interpIND = if_else(str_detect(AmtType,"_INTERP$"),"Y","N"),
        AmtType = str_remove_all(AmtType,"_INTERP$")
      )
    )
  )
  
  return(returndat)
  ###
}
###