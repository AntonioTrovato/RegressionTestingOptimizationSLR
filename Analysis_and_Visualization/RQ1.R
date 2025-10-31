library(readxl)
library(tidyr)
library(ggplot2)
library(ggpattern)


source("00-plot-theme.R")


#### Plot trend of category over time

data_categories_by_year <- read_xlsx("./data/data.xlsx", sheet="RQ1_trends_by_category_per_year")

data_filtered <- subset(data_categories_by_year, Anno != "Total")


# Reshape the data to long format
df_long <- pivot_longer(data_filtered, cols = c(Minimization, Selection, Prioritization),
                        names_to = "Category", values_to = "Value")



# Create the enhanced stacked barplot
ggplot(df_long, aes(x = Anno, y = Value, fill = Category, pattern = Category)) +
  geom_bar(stat = "identity") +
  geom_bar_pattern(
    alpha=1, position = 'stack', stat="identity",
    aes(fill=Category, #pattern_angle=angle_map[Category],
        pattern_fill=Category),
    #width                = .2,
    colour               = 'black',
    #pattern_aspect_ratio = 1,
    pattern_density      = 0.1,
    pattern_key_scale_factor = 0.6,
    pattern_size = 0.2,
    pattern_spacing = 0.02
  ) +
  #geom_text(aes(label = Value), position = position_stack(vjust = 0.5), size = 3) +
  

  
  geom_label(
    data = subset(df_long, Value != 0),  # Exclude zero values
    aes(label = Value),
    position = position_stack(vjust = 0.5),
    fill = "white",
    alpha = 0.85,
    size = 3,
    colour = NA, label.size = 0
  ) +
  
  geom_text(
    data = subset(df_long, Value != 0),  # Exclude zero values
    aes(label = Value),
    position = position_stack(vjust = 0.5),
    size = 3
  ) +

  theme_luigi() +
  scale_fill_viridis_d(option = "viridis", begin=0.3, end=1) +
  scale_pattern_manual(values = c("stripe", "crosshatch", "circle")) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust=1), legend.position = "top") +
  labs(x = "Year", y = "Number of papers")


ggsave("RQ1_publications_by_category_over_time.pdf", width=6, height = 4.5)





## Plot trend of replicability over time

data_replicability_by_year <- read_xlsx("./data/data.xlsx", sheet="RQ1_replicability_per_year")


# Reshape the data to long format
df_long <- pivot_longer(data_replicability_by_year, cols = c("No Replication", "Partial Replication", "Full Replication"),
                        names_to = "Replicability", values_to = "Value")

df_long$Replicability <- factor(df_long$Replicability, 
                                levels=c("No Replication", "Partial Replication", "Full Replication"),
                                ordered = TRUE)

df_long$Anno <- factor(df_long$Anno, levels = as.character(2013:2025))


df_long <- df_long %>%
  group_by(Anno) %>%
  mutate(Percent = Value / sum(Value) * 100)





# Stacked barplot (percentage filled)
ggplot(df_long, aes(x = Anno, y = Value, fill = Replicability, pattern = Replicability)) +
  geom_bar(position="fill", stat = "identity") +
  geom_bar_pattern(
    alpha=1, position = 'fill', stat="identity",
    aes(fill=Replicability, #pattern_angle=angle_map[Category],
        pattern_fill=Replicability),
    #width                = .2,
    colour               = 'black',
    #pattern_aspect_ratio = 1,
    pattern_density      = 0.1,
    pattern_key_scale_factor = 0.6,
    pattern_size = 0.2,
    pattern_spacing = 0.02
  ) +
  
  geom_label(
    data = subset(df_long, Value != 0),  # Exclude zero values
    aes(y = Value, label = paste0(round(Percent, 1), "%")),
    position = position_fill(vjust = 0.5),
    fill = "white",
    alpha = 0.85,
    size = 3,
    colour = NA, label.size = 0
  ) +
  
  geom_text(
    data = subset(df_long, Value != 0),  # Exclude zero values
    aes(y = Value, label = paste0(round(Percent, 1), "%")),
    stat = "identity",
    position = position_fill(vjust = 0.5),
    size = 3
  ) +

  
  theme_luigi() +
  scale_fill_viridis_d(option = "viridis", begin=0.3, end=1) +
  scale_pattern_manual(values = c("stripe", "crosshatch", "circle")) +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1))+
  scale_x_discrete(limits = as.character(2013:2025)) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust=1), legend.position = "top") +
  labs(x = "Year", y = "Percentage of papers")

ggsave("RQ1_replicability_percent_over_time.pdf", width=8, height = 4.5)


# Stacked bar chart (nominal values, not percentage filled)
ggplot(df_long, aes(x = Anno, y = Value, fill = Replicability, pattern = Replicability)) +
  geom_bar(position="stack", stat = "identity") +
  geom_bar_pattern(
    alpha=1, position = 'stack', stat="identity",
    aes(fill=Replicability, #pattern_angle=angle_map[Category],
        pattern_fill=Replicability),
    #width                = .2,
    colour               = 'black',
    #pattern_aspect_ratio = 1,
    pattern_density      = 0.1,
    pattern_key_scale_factor = 0.6,
    pattern_size = 0.2,
    pattern_spacing = 0.02
  ) +
  
  geom_label(
    data = subset(df_long, Value != 0),  # Exclude zero values
    aes(label = Value),
    position = position_stack(vjust = 0.5),
    fill = "white",
    alpha = 0.85,
    size = 3,
    colour = NA, label.size = 0
  ) +

  geom_text(
    data = subset(df_long, Value != 0),  # Exclude zero values
    aes(label = Value),
    position = position_stack(vjust = 0.5),
    size = 3
  ) +
  
  theme_luigi() +
  scale_fill_viridis_d(option = "viridis", begin=0.3, end=1) +
  scale_pattern_manual(values = c("stripe", "crosshatch", "circle")) +
  scale_x_discrete(limits = as.character(2013:2025)) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1, vjust=1), legend.position = "top") +
  labs(x = "Year", y = "Number of papers")

ggsave("RQ1_replicability_over_time.pdf", width=6, height = 4.5)

