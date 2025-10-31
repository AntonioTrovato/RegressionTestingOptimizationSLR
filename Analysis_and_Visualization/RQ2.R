library(readxl)
library(tidyr)
library(dplyr)
library(ggplot2)

source("00-plot-theme.R")

for(category in c("prioritization", "selection")){
  
  initial_letter <- substring(category, 1, 1)
    
  data <- read_excel("./data/data.xlsx", sheet=paste0("RQ2_",initial_letter, "_taxonomy_vs_algorithm"))
  
  data <- data %>%
    rename(`Taxonomy Class` = Taxonomy) 
    # %>%
    # mutate(across(where(is.numeric), ~na_if(., 0)))
  
  data_long <- data %>%
    pivot_longer(cols = -"Taxonomy Class", names_to = "Algorithmic Family", values_to = "Value")
  
  
  
  p <- ggplot(data_long, aes(x = `Algorithmic Family`, y = `Taxonomy Class`, fill = Value)) +
    geom_tile(color = "white", width=0.9, height=0.9) +
    geom_text(aes(label = Value), size = 3) +
    scale_fill_gradient(low = "white", high = "orange", na.value = '#ebebeb') +
    #scale_fill_viridis_c(option = "viridis", begin = 1, end = 0.1) +
    theme_luigi()+
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(x = "Algorithmic Family", y = "Taxonomy Class", fill = "Frequency")+
    coord_flip()
  
  print(p)
  
  
  ggsave(paste0("RQ2_",category,"_taxonomy_class_vs_algorithm.pdf"), width=7.2, height = 3.8)
}