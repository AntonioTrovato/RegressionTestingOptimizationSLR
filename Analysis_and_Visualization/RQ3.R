library(readxl)
library(tidyr)
library(ggplot2)
library(ggpattern)

library(treemapify)



source("00-plot-theme.R")


#### Plot dataset distribution

data_datasets <- read_xlsx("./data/data.xlsx", sheet="RQ3_datasets")


# Compute percentage within each Category
data_datasets <- data_datasets %>%
  group_by(Category) %>%
  mutate(Percent = Count / sum(Count) * 100)




ggplot(
  data_datasets, 
  aes(area = Count, fill = Dataset, label = paste(Dataset, "\n", Count, " (", round(Percent, 1), "%)", sep=""))) +
  geom_treemap(layout = "squarified") +
  geom_treemap_text(colour = "white", place = "centre", layout = "squarified", grow = TRUE, reflow = TRUE, padding.x = unit(2, "mm"), padding.y = unit(2, "mm")) +
  facet_wrap(~Category) +
  scale_fill_viridis_d(option = "viridis", begin = .5, end=0) +
  theme_luigi() +
  theme(legend.position = "none") +
  theme(strip.text = element_text(size = 12)) +
  labs(fill = "Dataset")
  
ggsave("RQ3_dataset_treemap.pdf", width=9, height=3.5)
