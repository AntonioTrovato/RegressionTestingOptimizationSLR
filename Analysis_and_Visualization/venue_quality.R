library(readxl)
library(tidyr)
library(ggplot2)
library(ggpattern)
library(dplyr)


source("00-plot-theme.R")


#### Plot trend of category over time

data_venue_quality <- read_xlsx("./data/data.xlsx", sheet="classification_by_venue_q")

data <- data_venue_quality

data$IDQ <- as.factor(data$IDQ)


# Dodged (side-by-side) patterned barplot
ggplot(data, aes(x = pubtype, y = count, fill = IDQ, pattern = IDQ)) +
  # Bars (identity = we already have counts)
  geom_bar(
    stat = "identity",
    position = position_dodge(width = 0.9),
    colour = "black"
  ) +
  # Patterned overlay (match the same dodge so it aligns!)
  geom_bar_pattern(
    stat = "identity",
    position = position_dodge(width = 0.9),
    aes(pattern_fill = IDQ),
    alpha = 1,
    colour = "black",
    pattern_density = 0.1,
    pattern_key_scale_factor = 0.6,
    pattern_size = 0.2,
    pattern_spacing = 0.02
  ) +
  # Labels: center each label within its dodged bar
  geom_label(
    data = subset(data, count != 0),
    aes(label = count),
    position = position_dodge(width = 0.9),
    vjust = 0.5,
    fill = "white",
    alpha = 0.85,
    size = 3,
    colour = NA, label.size = 0
  ) +
  geom_text(
    data = subset(data, count != 0),
    aes(label = count),
    position = position_dodge(width = 0.9),
    vjust = 0.5,
    size = 3
  ) +
  coord_flip() +
  theme_luigi() +
  scale_fill_viridis_d(option = "viridis", begin = 0.3, end = 1) +
  scale_pattern_manual(values = c("stripe", "crosshatch", "circle", "wave")) +
  theme(
    #axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
    legend.position = "top"
  ) +
  labs(x = "Publication type", y = "Number of papers")

ggsave("IDQ_classification.pdf", width=8, height = 4.5)




















# Dodged (side-by-side) patterned barplot
ggplot(data, aes(x = IDQ, y = count, fill = IDQ, pattern = IDQ)) +
  # Bars (identity = we already have counts)
  geom_bar(
    stat = "identity",
    position = position_dodge(width = 0.9),
    colour = "black"
  ) +
  # Patterned overlay (match the same dodge so it aligns!)
  geom_bar_pattern(
    stat = "identity",
    position = position_dodge(width = 0.9),
    aes(pattern_fill = IDQ),
    alpha = 1,
    colour = "black",
    pattern_density = 0.1,
    pattern_key_scale_factor = 0.6,
    pattern_size = 0.2,
    pattern_spacing = 0.02
  ) +
  # Labels: center each label within its dodged bar
  geom_label(
    data = subset(data, count != 0),
    aes(label = count),
    position = position_dodge(width = 0.9),
    vjust = 0.5,
    fill = "white",
    alpha = 0.85,
    size = 3,
    colour = NA, label.size = 0
  ) +
  geom_text(
    data = subset(data, count != 0),
    aes(label = count),
    position = position_dodge(width = 0.9),
    vjust = 0.5,
    size = 3
  ) +
  coord_flip() +
  facet_wrap(~pubtype)+
  theme_luigi() +
  scale_fill_viridis_d(option = "viridis", begin = 0.3, end = 1) +
  scale_pattern_manual(values = c("stripe", "crosshatch", "circle", "wave")) +
  theme(
    #axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
    legend.position = "top"
  ) +
  labs(x = "Publication type", y = "Number of papers")
